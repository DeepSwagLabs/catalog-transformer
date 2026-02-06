#!/usr/bin/env python3
"""
BrandFuse Catalog Transformer

Converts Sage-format supplier exports to Creative Merchandise legacy DB schema.

Usage (CLI):
    python catalog_transformer.py input.xlsx output.xlsx
    python catalog_transformer.py input.xlsx output.xlsx --old existing_db.xlsx
    python catalog_transformer.py input.csv output.xlsx --supplier hit

Usage (HTTP - for Pipedream/Railway/Vercel):
    POST /transform
    Content-Type: multipart/form-data
    file: <supplier_export.xlsx>
    old_file: <existing_db.xlsx> (optional)
    supplier: illini (optional)

Requirements:
    pip install pandas openpyxl xlrd flask gunicorn

Author: BrandFuse Automation
"""

import pandas as pd
import numpy as np
import re
import io
import os
import sys
import logging
from pathlib import Path
from typing import Optional, Tuple, Dict, List
from dataclasses import dataclass, field

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class TransformConfig:
    """Configuration for a specific supplier's transformation."""
    supplier_name: str = "Generic"
    supplier_code: str = "generic"
    custom_mappings: Optional[Dict[str, str]] = None
    category_map: Optional[Dict[str, str]] = None
    char_limits: Dict[str, int] = field(default_factory=lambda: {
        'included_decoration': 60,
        'product': 100,
    })


# =============================================================================
# TRANSFORMER
# =============================================================================

class SageTransformer:
    """
    Transforms Sage-format supplier exports to legacy DB schema.
    """
    
    TARGET_COLUMNS = [
        'delete_product', 'product_id', 'item_number', 'product', 'categories',
        'product_desc', 'production_time', 'included_decoration', 'decoration_method',
        'imprint_location', 'colors', 'sizes', 'sizeupcharges', 'setup_charge',
        'setup_price_code', 'price_quantity_1', 'price_quantity_2', 'price_quantity_3',
        'price_quantity_4', 'price_quantity_5', 'price_quantity_6', 'price_1',
        'price_2', 'price_3', 'price_4', 'price_5', 'price_6', 'price_code_1',
        'price_code_2', 'price_code_3', 'price_code_4', 'price_code_5', 'price_code_6',
        'addcost', 'addcostprice', 'addcostpricecode', 'image_name', 'logo_style',
        'logo_scale', 'logo_rotate', 'coord_x', 'coord_y',
    ]
    
    def __init__(self, config: Optional[TransformConfig] = None):
        self.config = config or TransformConfig()
    
    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Main transformation pipeline."""
        logger.info(f"Transforming {len(df)} rows for {self.config.supplier_name}")
        
        out = pd.DataFrame()
        
        # Static fields
        out['delete_product'] = 'N'
        out['product_id'] = np.nan
        
        # Direct mappings with safe column access
        out['item_number'] = self._safe_col(df, 'ItemNum').apply(self._normalize_item_number)
        out['product'] = self._safe_col(df, 'Name').apply(lambda x: str(x)[:100] if pd.notna(x) else x)
        out['colors'] = self._safe_col(df, 'Colors')
        out['decoration_method'] = self._safe_col(df, 'DecorationMethod')
        out['imprint_location'] = self._safe_col(df, 'ImprintLoc')
        out['setup_charge'] = self._safe_col(df, 'SetupChg').replace(0, np.nan)
        out['setup_price_code'] = self._safe_col(df, 'SetupChgCode')
        
        # Computed fields
        out['categories'] = df.apply(self._build_categories, axis=1)
        out['product_desc'] = df.apply(self._build_product_desc, axis=1)
        out['production_time'] = df.apply(self._build_production_time, axis=1)
        out['included_decoration'] = df.apply(self._build_included_decoration, axis=1)
        
        # Quantity columns (0 → NaN)
        for i in range(1, 7):
            out[f'price_quantity_{i}'] = self._safe_col(df, f'Qty{i}').replace(0, np.nan)
        
        # Price columns (0 → NaN)
        for i in range(1, 7):
            out[f'price_{i}'] = self._safe_col(df, f'Prc{i}').replace(0, np.nan)
        
        # Price code split
        price_codes = self._safe_col(df, 'PrCode').apply(self._split_price_code)
        for i in range(1, 7):
            out[f'price_code_{i}'] = price_codes.apply(lambda x: x[i-1] if len(x) >= i else np.nan)
        
        # Empty/placeholder columns
        for col in ['sizes', 'sizeupcharges', 'addcost', 'addcostprice', 'addcostpricecode',
                    'image_name', 'logo_style', 'logo_scale', 'logo_rotate', 'coord_x', 'coord_y']:
            out[col] = np.nan
        
        # Reorder columns
        out = out[self.TARGET_COLUMNS]
        logger.info(f"Output: {len(out)} rows, {len(out.columns)} columns")
        
        return out
    
    def _safe_col(self, df: pd.DataFrame, col: str) -> pd.Series:
        """Safely get column or return NaN series."""
        if col in df.columns:
            return df[col]
        return pd.Series([np.nan] * len(df))
    
    def _normalize_item_number(self, value) -> str:
        """Normalize item number formatting."""
        if pd.isna(value):
            return ''
        s = str(value)
        s = re.sub(r'\s*[Xx]\s*', ' x ', s)
        s = re.sub(r'\s+', ' ', s)
        return s.strip()
    
    def _build_categories(self, row: pd.Series) -> str:
        """Build category string from Cat1Name and Cat2Name."""
        parts = []
        cat1, cat2 = row.get('Cat1Name'), row.get('Cat2Name')
        if pd.notna(cat1):
            parts.append(str(cat1))
        if pd.notna(cat2) and cat2 != cat1:
            parts.append(str(cat2))
        return ','.join(parts) if parts else np.nan
    
    def _build_product_desc(self, row: pd.Series) -> str:
        """Build enriched product description."""
        parts = []
        
        desc = row.get('Description')
        if pd.notna(desc):
            parts.append(str(desc))
        
        imprint_parts = []
        price_include_clr = row.get('PriceIncludeClr')
        if pd.notna(price_include_clr) and str(price_include_clr).lower() != 'blank':
            imprint_parts.append(f"Maximum Imprint Colors\t{str(price_include_clr).title()} Maximum")
        
        imp_size1, imp_size2 = row.get('ImprintSize1'), row.get('ImprintSize2')
        if pd.notna(imp_size1):
            if pd.notna(imp_size2):
                imprint_parts.append(f'Imprint Area\t{imp_size1}" x {imp_size2}"')
            else:
                imprint_parts.append(f'Imprint Area\t{imp_size1}"')
        
        dims = [row.get(f'Dimension{i}') for i in [1, 2, 3]]
        dims = [d for d in dims if pd.notna(d) and d != 0]
        if dims:
            dim_str = '" x "'.join([str(d) for d in dims])
            imprint_parts.append(f'Item Size\t{dim_str}"')
        
        packaging = row.get('Packaging')
        if pd.notna(packaging):
            imprint_parts.append(f'Packaging\t{packaging}')
        
        if imprint_parts:
            parts.append('\n'.join(imprint_parts))
        
        return '\n\n'.join(parts) if parts else np.nan
    
    def _build_production_time(self, row: pd.Series) -> str:
        """Build production time string."""
        lo, hi = row.get('ProdTimeLo'), row.get('ProdTimeHi')
        if pd.isna(lo) or lo == 0:
            return np.nan
        if pd.isna(hi) or hi == 0:
            hi = lo
        return f"{int(lo)} to {int(hi)} Working Days"
    
    def _build_included_decoration(self, row: pd.Series) -> str:
        """Build included decoration string."""
        parts = []

        clr = row.get('PriceIncludeClr')
        if pd.notna(clr):
            parts.append('No Imprint' if str(clr).lower() == 'blank' else str(clr).title())
        
        side = row.get('PriceIncludeSide')
        if pd.notna(side):
            parts.append(str(side).title())
        
        loc = row.get('PriceIncludeLoc')
        if pd.notna(loc):
            parts.append(str(loc).title())
        
        method = row.get('DecorationMethod')
        if pd.notna(method):
            parts.append(str(method).title())
        
        result = ' '.join(parts) if parts else np.nan
        if pd.notna(result):
            result = result[:60]
        return result
    
    def _split_price_code(self, code) -> List[str]:
        """Split price code string into individual codes."""
        if pd.isna(code):
            return []
        return list(str(code))


# =============================================================================
# RECONCILER
# =============================================================================

class CatalogReconciler:
    """Compares old vs new catalog to generate add/update/delete lists."""
    
    def __init__(self, key_column: str = 'item_number'):
        self.key_column = key_column
    
    def reconcile(
        self,
        df_old: pd.DataFrame,
        df_new: pd.DataFrame,
        compare_columns: Optional[List[str]] = None
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Compare catalogs and return (adds, updates, deletes)."""
        
        if compare_columns is None:
            compare_columns = [
                'price_1', 'price_2', 'price_3', 'price_4', 'price_5', 'price_6',
                'price_quantity_1', 'price_quantity_2', 'price_quantity_3',
                'price_quantity_4', 'price_quantity_5', 'price_quantity_6',
                'product', 'colors', 'production_time',
            ]
        
        # Normalize keys for comparison
        def norm(x):
            return str(x).lower().replace(' ', '')
        
        old_keys = {norm(x): str(x) for x in df_old[self.key_column]}
        new_keys = {norm(x): str(x) for x in df_new[self.key_column]}
        
        old_norm_set = set(old_keys.keys())
        new_norm_set = set(new_keys.keys())
        
        # Adds
        add_norms = new_norm_set - old_norm_set
        add_originals = [new_keys[n] for n in add_norms]
        adds = df_new[df_new[self.key_column].astype(str).isin(add_originals)].copy()
        
        # Deletes
        del_norms = old_norm_set - new_norm_set
        del_originals = [old_keys[n] for n in del_norms]
        deletes = df_old[df_old[self.key_column].astype(str).isin(del_originals)].copy()
        
        # Updates
        common_norms = old_norm_set & new_norm_set
        updates_list = []
        
        for norm_key in common_norms:
            old_orig = old_keys[norm_key]
            new_orig = new_keys[norm_key]
            
            old_row = df_old[df_old[self.key_column].astype(str) == old_orig].iloc[0]
            new_row = df_new[df_new[self.key_column].astype(str) == new_orig].iloc[0]
            
            changed = False
            for col in compare_columns:
                if col in old_row.index and col in new_row.index:
                    old_val, new_val = old_row[col], new_row[col]
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


# =============================================================================
# FILE I/O
# =============================================================================

def load_file(file_path_or_buffer, filename: str = None) -> pd.DataFrame:
    """Load Excel or CSV file from path or buffer."""

    # Determine format
    if filename:
        ext = Path(filename).suffix.lower()
    elif isinstance(file_path_or_buffer, (str, Path)):
        ext = Path(file_path_or_buffer).suffix.lower()
    else:
        ext = '.xlsx'  # default assumption

    if ext == '.csv':
        # Try UTF-8 first, fall back to Windows-1252 (common for Sage exports)
        for encoding in ['utf-8', 'cp1252', 'latin-1']:
            try:
                if isinstance(file_path_or_buffer, (str, Path)):
                    return pd.read_csv(file_path_or_buffer, encoding=encoding)
                else:
                    file_path_or_buffer.seek(0)
                    return pd.read_csv(file_path_or_buffer, encoding=encoding)
            except UnicodeDecodeError:
                continue
        # Last resort - ignore errors
        if isinstance(file_path_or_buffer, (str, Path)):
            return pd.read_csv(file_path_or_buffer, encoding='utf-8', errors='replace')
        else:
            file_path_or_buffer.seek(0)
            return pd.read_csv(file_path_or_buffer, encoding='utf-8', errors='replace')
    else:
        return pd.read_excel(file_path_or_buffer)


def save_to_excel_buffer(df: pd.DataFrame) -> io.BytesIO:
    """Save DataFrame to Excel buffer for HTTP response."""
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False, engine='openpyxl')
    buffer.seek(0)
    return buffer


# =============================================================================
# CLI
# =============================================================================

def run_cli():
    """Command-line interface."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Transform Sage supplier exports to legacy DB schema',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python catalog_transformer.py supplier.xlsx output.xlsx
  python catalog_transformer.py supplier.csv output.xlsx --supplier hit
  python catalog_transformer.py new.xlsx output.xlsx --old current_db.xlsx
        """
    )
    parser.add_argument('input', help='Input file (Excel or CSV)')
    parser.add_argument('output', help='Output Excel file')
    parser.add_argument('--old', help='Previous DB export for reconciliation')
    parser.add_argument('--supplier', default='generic', help='Supplier code')
    
    args = parser.parse_args()
    
    # Load and transform
    df_source = load_file(args.input)
    config = TransformConfig(supplier_name=args.supplier.title(), supplier_code=args.supplier.lower())
    transformer = SageTransformer(config)
    df_clean = transformer.transform(df_source)
    
    # Save main output
    output_path = Path(args.output)
    df_clean.to_excel(output_path, index=False)
    print(f"✅ Saved {len(df_clean)} products to {output_path}")
    
    # Reconcile if old file provided
    if args.old:
        df_old = load_file(args.old)
        reconciler = CatalogReconciler()
        adds, updates, deletes = reconciler.reconcile(df_old, df_clean)
        
        stem = output_path.stem
        parent = output_path.parent
        
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


# =============================================================================
# HTTP SERVER (Flask - for Pipedream/Railway/Vercel)
# =============================================================================

def create_app():
    """Create Flask app for HTTP deployment."""
    from flask import Flask, request, send_file, jsonify
    
    app = Flask(__name__)
    
    @app.route('/', methods=['GET'])
    def health():
        return jsonify({
            "status": "ok",
            "service": "BrandFuse Catalog Transformer",
            "endpoints": {
                "POST /transform": "Transform supplier export to DB schema",
                "POST /reconcile": "Transform and reconcile against existing DB"
            }
        })
    
    @app.route('/transform', methods=['POST'])
    def transform():
        """
        Transform supplier export.
        
        Form data:
            file: Excel or CSV file (required)
            supplier: Supplier code (optional, default: generic)
        """
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files['file']
        supplier = request.form.get('supplier', 'generic')
        
        try:
            df_source = load_file(file.stream, file.filename)
            config = TransformConfig(supplier_name=supplier.title(), supplier_code=supplier.lower())
            transformer = SageTransformer(config)
            df_clean = transformer.transform(df_source)
            
            buffer = save_to_excel_buffer(df_clean)
            
            return send_file(
                buffer,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name=f'{supplier}_transformed.xlsx'
            )
        except Exception as e:
            logger.exception("Transform failed")
            return jsonify({"error": str(e)}), 500
    
    @app.route('/reconcile', methods=['POST'])
    def reconcile():
        """
        Transform and reconcile against existing DB.
        
        Form data:
            file: New supplier export (required)
            old_file: Existing DB export (required)
            supplier: Supplier code (optional)
        
        Returns: ZIP containing transformed.xlsx, ADDS.xlsx, UPDATES.xlsx, DELETES.xlsx
        """
        import zipfile
        
        if 'file' not in request.files or 'old_file' not in request.files:
            return jsonify({"error": "Both 'file' and 'old_file' required"}), 400
        
        file = request.files['file']
        old_file = request.files['old_file']
        supplier = request.form.get('supplier', 'generic')
        
        try:
            df_source = load_file(file.stream, file.filename)
            df_old = load_file(old_file.stream, old_file.filename)
            
            config = TransformConfig(supplier_name=supplier.title(), supplier_code=supplier.lower())
            transformer = SageTransformer(config)
            df_clean = transformer.transform(df_source)
            
            reconciler = CatalogReconciler()
            adds, updates, deletes = reconciler.reconcile(df_old, df_clean)
            
            # Create ZIP with all outputs
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                # Main transformed file
                zf.writestr(f'{supplier}_transformed.xlsx', save_to_excel_buffer(df_clean).getvalue())
                
                if len(adds) > 0:
                    zf.writestr(f'{supplier}_ADDS.xlsx', save_to_excel_buffer(adds).getvalue())
                if len(updates) > 0:
                    zf.writestr(f'{supplier}_UPDATES.xlsx', save_to_excel_buffer(updates).getvalue())
                if len(deletes) > 0:
                    zf.writestr(f'{supplier}_DELETES.xlsx', save_to_excel_buffer(deletes).getvalue())
            
            zip_buffer.seek(0)
            
            return send_file(
                zip_buffer,
                mimetype='application/zip',
                as_attachment=True,
                download_name=f'{supplier}_catalog_sync.zip'
            )
        except Exception as e:
            logger.exception("Reconcile failed")
            return jsonify({"error": str(e)}), 500
    
    return app


# =============================================================================
# MAIN
# =============================================================================

if __name__ == '__main__':
    # Check if running as HTTP server or CLI
    if os.environ.get('FLASK_APP') or os.environ.get('PORT'):
        # HTTP mode (Pipedream/Railway/Vercel)
        app = create_app()
        port = int(os.environ.get('PORT', 8080))
        app.run(host='0.0.0.0', port=port)
    else:
        # CLI mode
        run_cli()
