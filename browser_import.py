#!/usr/bin/env python3
"""
Browser-based Product Import (Fallback)

Uses Playwright to automate the admin UI when direct database access isn't possible.

Usage:
    pip install playwright pandas openpyxl
    playwright install chromium

    python browser_import.py products.xlsx --headless
    python browser_import.py products.xlsx --visible  # Debug mode

Environment variables:
    CM_ADMIN_URL: Admin panel URL (default: https://admin.creativemerch.com)
    CM_ADMIN_USER: Admin email
    CM_ADMIN_PASS: Admin password
"""

import pandas as pd
import os
import sys
import time
import logging
from typing import Optional, Dict, Any

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BrowserImporter:
    def __init__(
        self,
        admin_url: str = None,
        username: str = None,
        password: str = None,
        headless: bool = True
    ):
        self.admin_url = admin_url or os.environ.get('CM_ADMIN_URL', 'https://admin.creativemerch.com')
        self.username = username or os.environ.get('CM_ADMIN_USER')
        self.password = password or os.environ.get('CM_ADMIN_PASS')
        self.headless = headless
        self.browser = None
        self.page = None

    def start(self):
        """Start browser and login."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.error("Playwright not installed. Run: pip install playwright && playwright install chromium")
            sys.exit(1)

        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=self.headless)
        self.context = self.browser.new_context()
        self.page = self.context.new_page()

        self._login()

    def _login(self):
        """Login to admin panel."""
        logger.info(f"Navigating to {self.admin_url}")
        self.page.goto(self.admin_url)

        # Fill login form
        logger.info("Logging in...")
        self.page.fill('input[name="username"]', self.username)
        self.page.fill('input[name="password"]', self.password)
        self.page.click('input[type="submit"]')

        # Wait for dashboard to load
        self.page.wait_for_load_state('networkidle')

        # Check if login succeeded
        if 'login' in self.page.url.lower():
            raise Exception("Login failed - check credentials")

        logger.info("Login successful")

    def navigate_to_products(self):
        """Navigate to product management section."""
        # TODO: Update selectors based on actual admin UI
        # This is a placeholder - we need to discover the actual navigation
        logger.info("Navigating to product management...")

        # Try common navigation patterns
        possible_selectors = [
            'a:has-text("Products")',
            'a:has-text("Catalog")',
            'a[href*="product"]',
            '#nav-products',
            '.menu-products',
        ]

        for selector in possible_selectors:
            try:
                if self.page.locator(selector).count() > 0:
                    self.page.click(selector)
                    self.page.wait_for_load_state('networkidle')
                    logger.info(f"Found navigation via: {selector}")
                    return
            except:
                continue

        logger.warning("Could not find product navigation - may need manual discovery")

    def add_product(self, product: Dict[str, Any]) -> bool:
        """Add a single product via the UI."""
        # TODO: Implement actual form filling based on discovered UI
        # This is a placeholder

        logger.info(f"Adding product: {product.get('item_number', 'unknown')}")

        # Example form filling (needs real selectors):
        # self.page.click('a:has-text("Add Product")')
        # self.page.fill('input[name="item_number"]', product['item_number'])
        # self.page.fill('input[name="name"]', product['product'])
        # ... etc

        # For now, just log what we would do
        logger.info(f"  Would fill: item_number = {product.get('item_number')}")
        logger.info(f"  Would fill: product = {product.get('product')}")
        logger.info(f"  Would fill: price_1 = {product.get('price_1')}")

        return True

    def import_products(self, df: pd.DataFrame, dry_run: bool = True) -> Dict[str, int]:
        """Import all products from DataFrame."""
        stats = {'added': 0, 'skipped': 0, 'errors': 0}

        self.navigate_to_products()

        for idx, row in df.iterrows():
            product = row.to_dict()

            if dry_run:
                logger.info(f"[DRY RUN] Would add: {product.get('item_number')}")
                stats['added'] += 1
                continue

            try:
                if self.add_product(product):
                    stats['added'] += 1
                else:
                    stats['skipped'] += 1
            except Exception as e:
                logger.error(f"Error adding {product.get('item_number')}: {e}")
                stats['errors'] += 1

            # Be nice to the server
            time.sleep(0.5)

        return stats

    def discover_ui(self):
        """Interactive mode to discover the admin UI structure."""
        logger.info("=== UI Discovery Mode ===")
        logger.info("Navigate manually in the browser. Press Ctrl+C when done.")
        logger.info(f"Current URL: {self.page.url}")

        # Print all links on current page
        links = self.page.locator('a').all()
        logger.info(f"\nFound {len(links)} links on page:")
        for link in links[:30]:  # First 30
            try:
                href = link.get_attribute('href')
                text = link.inner_text().strip()[:50]
                if href and text:
                    logger.info(f"  [{text}] -> {href}")
            except:
                pass

        # Print all forms
        forms = self.page.locator('form').all()
        logger.info(f"\nFound {len(forms)} forms on page:")
        for form in forms:
            try:
                action = form.get_attribute('action')
                logger.info(f"  Form action: {action}")
            except:
                pass

        # Keep browser open for manual exploration
        input("\nPress Enter to close browser...")

    def close(self):
        if self.browser:
            self.browser.close()
        if hasattr(self, 'playwright'):
            self.playwright.stop()


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Import products via browser automation')
    parser.add_argument('input', nargs='?', help='Transformed Excel file to import')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done')
    parser.add_argument('--commit', action='store_true', help='Actually add products')
    parser.add_argument('--discover', action='store_true', help='Explore the admin UI')
    parser.add_argument('--visible', action='store_true', help='Show browser window')
    parser.add_argument('--headless', action='store_true', help='Run headless (default)')

    args = parser.parse_args()

    if not args.discover and not args.input:
        parser.error("Must provide input file or use --discover")

    headless = not args.visible

    importer = BrowserImporter(headless=headless)

    try:
        importer.start()

        if args.discover:
            importer.discover_ui()
            return

        df = pd.read_excel(args.input)
        logger.info(f"Loaded {len(df)} products from {args.input}")

        stats = importer.import_products(df, dry_run=not args.commit)

        print(f"\n=== Import {'Preview' if not args.commit else 'Results'} ===")
        print(f"Added:   {stats['added']}")
        print(f"Skipped: {stats['skipped']}")
        print(f"Errors:  {stats['errors']}")

    finally:
        importer.close()


if __name__ == '__main__':
    main()
