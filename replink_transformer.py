#!/usr/bin/env python3
"""
Replink Feed Transformer

Transforms Replink daily product feeds into Creative Merchandise format.
Handles the enable/disable logic based on inventory levels.

Usage:
    python replink_transformer.py replink_catalog.txt output.xlsx
    python replink_transformer.py replink_catalog.txt output.xlsx --old existing_products.xlsx

The Replink feed is pipe-delimited with these key columns:
    - BrandName, ItemNumber, ShortName, SalesCopy
    - MSRP, MAP, UserPrice, JobberPrice, DistributorPrice
    - QtyAvailable, ItemStatus
    - ImageURL
    - Features 1-18

Output includes:
    - enabled_products.xlsx: Products with inventory > 0
    - disabled_products.xlsx: Products with inventory = 0
    - adds/updates/deletes if --old provided
"""

import pandas as pd
import numpy as np
import csv
import io
import os
import sys
import logging
from pathlib import Path
from typing import Optional, Tuple, Dict, List
from dataclasses import dataclass

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class ReplinkConfig:
    """Configuration for Replink transformation."""
    user_account_id: Optional[int] = None
    enable_threshold: int = 0  # Products with qty > this are enabled
    price_column: str = 'DistributorPrice'  # Which price to use


class ReplinkTransformer:
    """Transforms Replink feeds to Creative Merchandise format."""

    # Map Replink columns to CM columns
    COLUMN_MAP = {
        'ItemNumber': 'item_number',
        'ShortName': 'product',
        'SalesCopy': 'product_desc',
        'BrandName': 'brand',
        'ImageURL': 'image_url',
        'QtyAvailable': 'qty_available',
        'ItemStatus': 'item_status',
        'MSRP': 'msrp',
        'MAP': 'map_price',
        'UserPrice': 'user_price',
        'JobberPrice': 'jobber_price',
        'DistributorPrice': 'distributor_price',
        'RepLinkCategoryID': 'category_id',
        'Keywords': 'keywords',
        'UPC': 'upc',
        'Freight': 'freight',
        'FOBCity': 'fob_city',
        'FOBState': 'fob_state',
        'FOBZip': 'fob_zip',
    }

    def __init__(self, config: Optional[ReplinkConfig] = None):
        self.config = config or ReplinkConfig()

    def load_feed(self, file_path: str) -> pd.DataFrame:
        """Load pipe-delimited Replink feed."""
        logger.info(f"Loading Replink feed: {file_path}")

        # Try different encodings
        for encoding in ['utf-8', 'cp1252', 'latin-1']:
            try:
                df = pd.read_csv(file_path, delimiter='|', encoding=encoding)
                logger.info(f"Loaded {len(df)} products (encoding: {encoding})")
                return df
            except UnicodeDecodeError:
                continue

        # Fallback
        df = pd.read_csv(file_path, delimiter='|', encoding='utf-8', errors='replace')
        logger.info(f"Loaded {len(df)} products (with replacement)")
        return df

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Transform Replink format to CM format."""
        logger.info(f"Transforming {len(df)} products")

        out = pd.DataFrame()

        # Map columns
        for replink_col, cm_col in self.COLUMN_MAP.items():
            if replink_col in df.columns:
                out[cm_col] = df[replink_col]
            else:
                out[cm_col] = np.nan

        # Build features/description
        out['features'] = df.apply(self._build_features, axis=1)

        # Combine description with features
        out['product_desc'] = out.apply(
            lambda r: f"{r['product_desc']}\n\n{r['features']}"
            if pd.notna(r['features']) and r['features']
            else r['product_desc'],
            axis=1
        )

        # Determine enabled/disabled based on inventory
        out['qty_available'] = pd.to_numeric(out['qty_available'], errors='coerce').fillna(0)
        out['enabled'] = out['qty_available'] > self.config.enable_threshold

        # Select price column
        out['price'] = pd.to_numeric(out.get(self.config.price_column.lower().replace('price', '_price'), out.get('distributor_price')), errors='coerce')

        # Add metadata
        out['source'] = 'replink'
        out['import_date'] = pd.Timestamp.now()

        if self.config.user_account_id:
            out['user_account_id'] = self.config.user_account_id

        enabled_count = out['enabled'].sum()
        disabled_count = (~out['enabled']).sum()
        logger.info(f"Output: {len(out)} products ({enabled_count} enabled, {disabled_count} disabled)")

        return out

    def _build_features(self, row: pd.Series) -> str:
        """Combine Feature1-Feature18 into a bullet list."""
        features = []
        for i in range(1, 19):
            feat = row.get(f'Feature{i}')
            if pd.notna(feat) and str(feat).strip():
                features.append(f"• {str(feat).strip()}")
        return '\n'.join(features) if features else ''

    def split_by_status(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Split into enabled and disabled products."""
        enabled = df[df['enabled'] == True].copy()
        disabled = df[df['enabled'] == False].copy()
        return enabled, disabled


class FeedReconciler:
    """Compare old vs new feed to find adds/updates/deletes."""

    def __init__(self, key_column: str = 'item_number'):
        self.key_column = key_column

    def reconcile(
        self,
        df_old: pd.DataFrame,
        df_new: pd.DataFrame
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Compare feeds and return (adds, updates, deletes)."""

        old_keys = set(df_old[self.key_column].astype(str))
        new_keys = set(df_new[self.key_column].astype(str))

        # New products
        add_keys = new_keys - old_keys
        adds = df_new[df_new[self.key_column].astype(str).isin(add_keys)].copy()

        # Removed products
        del_keys = old_keys - new_keys
        deletes = df_old[df_old[self.key_column].astype(str).isin(del_keys)].copy()

        # Products in both (potential updates)
        common_keys = old_keys & new_keys

        # Check for changes in common products
        updates_list = []
        compare_cols = ['product', 'price', 'qty_available', 'enabled']

        for key in common_keys:
            old_row = df_old[df_old[self.key_column].astype(str) == key].iloc[0]
            new_row = df_new[df_new[self.key_column].astype(str) == key].iloc[0]

            changed = False
            for col in compare_cols:
                if col in old_row.index and col in new_row.index:
                    old_val = old_row[col]
                    new_val = new_row[col]
                    if pd.isna(old_val) and pd.isna(new_val):
                        continue
                    if old_val != new_val:
                        changed = True
                        break

            if changed:
                updates_list.append(new_row)

        updates = pd.DataFrame(updates_list) if updates_list else pd.DataFrame(columns=df_new.columns)

        logger.info(f"Reconciliation: {len(adds)} adds, {len(updates)} updates, {len(deletes)} deletes")
        return adds, updates, deletes


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Transform Replink feed to CM format')
    parser.add_argument('input', help='Input Replink feed (pipe-delimited)')
    parser.add_argument('output', help='Output Excel file')
    parser.add_argument('--old', help='Previous feed for reconciliation')
    parser.add_argument('--user-id', type=int, help='User account ID for import')
    parser.add_argument('--price-col', default='DistributorPrice',
                       choices=['MSRP', 'MAP', 'UserPrice', 'JobberPrice', 'DistributorPrice'],
                       help='Which price column to use')

    args = parser.parse_args()

    config = ReplinkConfig(
        user_account_id=args.user_id,
        price_column=args.price_col
    )

    transformer = ReplinkTransformer(config)

    # Load and transform
    df_raw = transformer.load_feed(args.input)
    df_transformed = transformer.transform(df_raw)

    # Split by status
    enabled, disabled = transformer.split_by_status(df_transformed)

    # Save outputs
    output_path = Path(args.output)
    stem = output_path.stem
    parent = output_path.parent

    # Main output
    df_transformed.to_excel(output_path, index=False)
    print(f"✅ Saved {len(df_transformed)} products to {output_path}")

    # Enabled products
    enabled_path = parent / f"{stem}_ENABLED.xlsx"
    enabled.to_excel(enabled_path, index=False)
    print(f"✅ {len(enabled)} enabled products → {enabled_path}")

    # Disabled products
    disabled_path = parent / f"{stem}_DISABLED.xlsx"
    disabled.to_excel(disabled_path, index=False)
    print(f"⏸️  {len(disabled)} disabled products → {disabled_path}")

    # Reconcile if old file provided
    if args.old:
        df_old = pd.read_excel(args.old) if args.old.endswith('.xlsx') else transformer.load_feed(args.old)

        # Transform old if it's raw Replink format
        if 'ItemNumber' in df_old.columns:
            df_old = transformer.transform(df_old)

        reconciler = FeedReconciler()
        adds, updates, deletes = reconciler.reconcile(df_old, df_transformed)

        if len(adds) > 0:
            adds_path = parent / f"{stem}_ADDS.xlsx"
            adds.to_excel(adds_path, index=False)
            print(f"📥 {len(adds)} new products → {adds_path}")

        if len(updates) > 0:
            updates_path = parent / f"{stem}_UPDATES.xlsx"
            updates.to_excel(updates_path, index=False)
            print(f"🔄 {len(updates)} updated products → {updates_path}")

        if len(deletes) > 0:
            deletes_path = parent / f"{stem}_DELETES.xlsx"
            deletes.to_excel(deletes_path, index=False)
            print(f"🗑️  {len(deletes)} removed products → {deletes_path}")


if __name__ == '__main__':
    main()
