#!/usr/bin/env python3
"""
Creative Merchandise Database Import Tool

This script imports transformed catalog data directly into the MySQL database.
Requires SSH tunnel or direct database access.

Usage:
    # First, establish SSH tunnel:
    ssh -L 3306:localhost:3306 pat@trunk1.creativemerch.com

    # Then run import:
    python db_import.py transformed_products.xlsx --dry-run
    python db_import.py transformed_products.xlsx --commit

Environment variables:
    CM_DB_HOST: Database host (default: 127.0.0.1)
    CM_DB_PORT: Database port (default: 3306)
    CM_DB_USER: Database username
    CM_DB_PASS: Database password
    CM_DB_NAME: Database name (default: cm_v3_production)
"""

import pandas as pd
import os
import sys
import logging
from typing import Optional, List, Dict, Any

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Will be populated after we discover the actual schema
PRODUCTS_TABLE = "products"  # TODO: Verify actual table name
COLUMN_MAPPING = {
    # transformed_column: database_column
    # TODO: Fill in after examining database schema
    'item_number': 'item_number',
    'product': 'name',
    'product_desc': 'description',
    'categories': 'categories',
    'production_time': 'production_time',
    'included_decoration': 'included_decoration',
    'decoration_method': 'decoration_method',
    'imprint_location': 'imprint_location',
    'colors': 'colors',
    'setup_charge': 'setup_charge',
    'setup_price_code': 'setup_price_code',
    'price_quantity_1': 'qty_1',
    'price_quantity_2': 'qty_2',
    'price_quantity_3': 'qty_3',
    'price_quantity_4': 'qty_4',
    'price_quantity_5': 'qty_5',
    'price_quantity_6': 'qty_6',
    'price_1': 'price_1',
    'price_2': 'price_2',
    'price_3': 'price_3',
    'price_4': 'price_4',
    'price_5': 'price_5',
    'price_6': 'price_6',
    'price_code_1': 'price_code_1',
    'price_code_2': 'price_code_2',
    'price_code_3': 'price_code_3',
    'price_code_4': 'price_code_4',
    'price_code_5': 'price_code_5',
    'price_code_6': 'price_code_6',
}


class DatabaseImporter:
    def __init__(
        self,
        host: str = None,
        port: int = None,
        user: str = None,
        password: str = None,
        database: str = None
    ):
        self.host = host or os.environ.get('CM_DB_HOST', '127.0.0.1')
        self.port = port or int(os.environ.get('CM_DB_PORT', 3306))
        self.user = user or os.environ.get('CM_DB_USER')
        self.password = password or os.environ.get('CM_DB_PASS')
        self.database = database or os.environ.get('CM_DB_NAME', 'cm_v3_production')
        self.connection = None

    def connect(self):
        """Establish database connection."""
        try:
            import pymysql
        except ImportError:
            logger.error("pymysql not installed. Run: pip install pymysql")
            sys.exit(1)

        logger.info(f"Connecting to {self.host}:{self.port}/{self.database}")
        self.connection = pymysql.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database=self.database,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        logger.info("Connected successfully")

    def discover_schema(self) -> Dict[str, List[str]]:
        """Discover relevant tables and columns."""
        with self.connection.cursor() as cursor:
            # Find tables that might be product-related
            cursor.execute("""
                SELECT TABLE_NAME
                FROM information_schema.TABLES
                WHERE TABLE_SCHEMA = %s
                AND TABLE_NAME LIKE '%%product%%'
            """, (self.database,))
            tables = [row['TABLE_NAME'] for row in cursor.fetchall()]

            schema = {}
            for table in tables:
                cursor.execute(f"DESCRIBE `{table}`")
                columns = [row['Field'] for row in cursor.fetchall()]
                schema[table] = columns
                logger.info(f"Table {table}: {len(columns)} columns")

            return schema

    def import_products(
        self,
        df: pd.DataFrame,
        dry_run: bool = True,
        supplier_id: int = None
    ) -> Dict[str, int]:
        """Import products from DataFrame."""
        stats = {'inserted': 0, 'updated': 0, 'skipped': 0, 'errors': 0}

        with self.connection.cursor() as cursor:
            for idx, row in df.iterrows():
                try:
                    # Check if product exists
                    cursor.execute(
                        f"SELECT id FROM `{PRODUCTS_TABLE}` WHERE item_number = %s",
                        (row['item_number'],)
                    )
                    existing = cursor.fetchone()

                    if existing:
                        if dry_run:
                            logger.debug(f"Would update: {row['item_number']}")
                        else:
                            # TODO: Build UPDATE query based on actual schema
                            pass
                        stats['updated'] += 1
                    else:
                        if dry_run:
                            logger.debug(f"Would insert: {row['item_number']}")
                        else:
                            # TODO: Build INSERT query based on actual schema
                            pass
                        stats['inserted'] += 1

                except Exception as e:
                    logger.error(f"Error processing {row.get('item_number', idx)}: {e}")
                    stats['errors'] += 1

            if not dry_run:
                self.connection.commit()

        return stats

    def close(self):
        if self.connection:
            self.connection.close()


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Import products to Creative Merchandise database')
    parser.add_argument('input', help='Transformed Excel file to import')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    parser.add_argument('--commit', action='store_true', help='Actually commit changes to database')
    parser.add_argument('--discover', action='store_true', help='Just discover and print database schema')
    parser.add_argument('--supplier-id', type=int, help='Supplier ID for the products')

    args = parser.parse_args()

    if not args.dry_run and not args.commit and not args.discover:
        parser.error("Must specify --dry-run, --commit, or --discover")

    importer = DatabaseImporter()

    try:
        importer.connect()

        if args.discover:
            schema = importer.discover_schema()
            print("\n=== Database Schema ===")
            for table, columns in schema.items():
                print(f"\n{table}:")
                for col in columns:
                    print(f"  - {col}")
            return

        df = pd.read_excel(args.input)
        logger.info(f"Loaded {len(df)} products from {args.input}")

        stats = importer.import_products(
            df,
            dry_run=not args.commit,
            supplier_id=args.supplier_id
        )

        print(f"\n=== Import {'Preview' if not args.commit else 'Results'} ===")
        print(f"Inserted: {stats['inserted']}")
        print(f"Updated:  {stats['updated']}")
        print(f"Skipped:  {stats['skipped']}")
        print(f"Errors:   {stats['errors']}")

    finally:
        importer.close()


if __name__ == '__main__':
    main()
