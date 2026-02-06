#!/usr/bin/env python3
"""
Supplier Website Image Scraper

Uses Crawl4AI + local LLM inference to scrape product images from supplier websites.
Given an item number, finds and downloads all product images (main, colors, angles).

This integrates with the deepswag crawl4ai infrastructure.

Usage:
    # Single product
    python supplier_scraper.py --item-number ALB-AL23 --supplier ariel

    # Batch from feed file
    python supplier_scraper.py --input products.xlsx --supplier ariel

    # Discover supplier URL patterns
    python supplier_scraper.py --discover --supplier ariel

Requirements:
    - Crawl4AI running at localhost:11235
    - Ollama running at localhost:11434 (or workstation:11434)
    - Model: qwen3:30b-a3b-instruct-2507 or similar

Environment:
    CRAWL4AI_URL: Crawl4AI endpoint (default: http://localhost:11235)
    OLLAMA_URL: Ollama endpoint (default: http://localhost:11434)
    OLLAMA_MODEL: Model to use (default: qwen3:30b-a3b-instruct-2507)
"""

import os
import sys
import json
import logging
import httpx
import pandas as pd
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from urllib.parse import urljoin, quote

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# SUPPLIER CONFIGURATIONS
# =============================================================================

@dataclass
class SupplierConfig:
    """Configuration for scraping a specific supplier."""
    name: str
    code: str

    # URL patterns - {item_number} will be replaced
    product_url_pattern: Optional[str] = None
    search_url_pattern: Optional[str] = None
    catalog_base_url: Optional[str] = None

    # Selectors (CSS or XPath) for image extraction
    main_image_selector: str = "img.product-image, img.main-image, #product-image img"
    gallery_selector: str = ".product-gallery img, .color-swatches img, .thumbnail img"
    color_name_selector: str = ".color-name, .swatch-name, [data-color]"

    # Request settings
    render_js: bool = True
    delay_ms: int = 500


# Known supplier configurations
SUPPLIERS: Dict[str, SupplierConfig] = {
    "ariel": SupplierConfig(
        name="Ariel Premium Supply",
        code="ariel",
        product_url_pattern="https://www.arielweb.com/product/{item_number}",
        search_url_pattern="https://www.arielweb.com/search?q={item_number}",
        catalog_base_url="https://www.arielweb.com",
    ),
    "hit": SupplierConfig(
        name="HIT Promotional Products",
        code="hit",
        product_url_pattern="https://www.hitpromo.net/product/{item_number}",
        search_url_pattern="https://www.hitpromo.net/search/{item_number}",
        catalog_base_url="https://www.hitpromo.net",
    ),
    "illini": SupplierConfig(
        name="Illini",
        code="illini",
        # URL pattern TBD - need to discover
        search_url_pattern="https://www.illini.net/search?keywords={item_number}",
        catalog_base_url="https://www.illini.net",
    ),
    "gemline": SupplierConfig(
        name="Gemline",
        code="gemline",
        product_url_pattern="https://www.gemline.com/product/{item_number}",
        catalog_base_url="https://www.gemline.com",
    ),
    "leeds": SupplierConfig(
        name="Leeds",
        code="leeds",
        product_url_pattern="https://www.leedsworld.com/product/{item_number}",
        catalog_base_url="https://www.leedsworld.com",
    ),
    # Add more suppliers as discovered
}


# =============================================================================
# CRAWL4AI CLIENT
# =============================================================================

class Crawl4AIClient:
    """Client for Crawl4AI service."""

    def __init__(self, base_url: str = None):
        self.base_url = base_url or os.environ.get('CRAWL4AI_URL', 'http://localhost:11235')
        self.client = httpx.Client(timeout=60.0)

    def crawl(
        self,
        url: str,
        render_js: bool = True,
        extract_links: bool = True,
        screenshot: bool = True
    ) -> Dict[str, Any]:
        """Crawl a URL and return results."""
        try:
            response = self.client.post(
                f"{self.base_url}/crawl",
                json={
                    "url": url,
                    "render_js": render_js,
                    "extract_links": extract_links,
                    "screenshot": screenshot
                }
            )
            response.raise_for_status()
            return response.json()
        except httpx.ConnectError:
            logger.error(f"Cannot connect to Crawl4AI at {self.base_url}")
            logger.error("Start Crawl4AI: docker compose -f infra/docker-compose.crawl.yml up -d")
            return {"error": "Crawl4AI not available"}
        except Exception as e:
            logger.error(f"Crawl failed: {e}")
            return {"error": str(e)}

    def health(self) -> bool:
        """Check if Crawl4AI is healthy."""
        try:
            response = self.client.get(f"{self.base_url}/health")
            return response.status_code == 200
        except:
            return False


# =============================================================================
# LOCAL LLM CLIENT (OLLAMA)
# =============================================================================

class OllamaClient:
    """Client for local Ollama inference."""

    def __init__(self, base_url: str = None, model: str = None):
        self.base_url = base_url or os.environ.get('OLLAMA_URL', 'http://localhost:11434')
        self.model = model or os.environ.get('OLLAMA_MODEL', 'qwen3:30b-a3b-instruct-2507')
        self.client = httpx.Client(timeout=120.0)

    def extract_images(self, html: str, item_number: str) -> Dict[str, Any]:
        """
        Use LLM to extract image URLs from HTML.

        Returns:
            {
                "main_image": "url",
                "color_images": [{"color": "Navy Blue", "url": "..."}, ...],
                "gallery_images": ["url1", "url2", ...]
            }
        """
        prompt = f"""Analyze this HTML and extract all product image URLs for item number: {item_number}

Find:
1. The main product image URL
2. Color variant images with their color names
3. Any additional gallery/angle images

Return ONLY valid JSON in this exact format:
{{
    "main_image": "url or null",
    "color_images": [
        {{"color": "Color Name", "url": "image_url"}},
        ...
    ],
    "gallery_images": ["url1", "url2", ...]
}}

HTML content (truncated to relevant parts):
{html[:15000]}

JSON response:"""

        try:
            response = self.client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json"
                }
            )
            response.raise_for_status()
            result = response.json()

            # Parse the LLM response
            llm_response = result.get("response", "{}")
            try:
                return json.loads(llm_response)
            except json.JSONDecodeError:
                # Try to extract JSON from response
                import re
                json_match = re.search(r'\{[\s\S]*\}', llm_response)
                if json_match:
                    return json.loads(json_match.group())
                return {"error": "Could not parse LLM response", "raw": llm_response}

        except httpx.ConnectError:
            logger.warning(f"Cannot connect to Ollama at {self.base_url}")
            return {"error": "Ollama not available"}
        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
            return {"error": str(e)}

    def health(self) -> bool:
        """Check if Ollama is healthy."""
        try:
            response = self.client.get(f"{self.base_url}/api/tags")
            return response.status_code == 200
        except:
            return False


# =============================================================================
# IMAGE SCRAPER
# =============================================================================

class SupplierImageScraper:
    """Main scraper class that coordinates Crawl4AI and Ollama."""

    def __init__(
        self,
        supplier: SupplierConfig,
        crawl4ai: Crawl4AIClient = None,
        ollama: OllamaClient = None,
        output_dir: str = "/tmp/scraped_images"
    ):
        self.supplier = supplier
        self.crawl4ai = crawl4ai or Crawl4AIClient()
        self.ollama = ollama or OllamaClient()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def build_product_url(self, item_number: str) -> Optional[str]:
        """Build product page URL from item number."""
        if self.supplier.product_url_pattern:
            return self.supplier.product_url_pattern.format(
                item_number=quote(item_number)
            )
        elif self.supplier.search_url_pattern:
            return self.supplier.search_url_pattern.format(
                item_number=quote(item_number)
            )
        return None

    def scrape_product_images(self, item_number: str) -> Dict[str, Any]:
        """
        Scrape all images for a product.

        Returns:
            {
                "item_number": "...",
                "supplier": "...",
                "url": "...",
                "main_image": "url or None",
                "color_images": [{"color": "...", "url": "..."}],
                "gallery_images": ["url", ...],
                "downloaded": {"main": "local_path", "colors": {...}},
                "error": "if any"
            }
        """
        result = {
            "item_number": item_number,
            "supplier": self.supplier.code,
            "url": None,
            "main_image": None,
            "color_images": [],
            "gallery_images": [],
            "downloaded": {},
            "error": None
        }

        # Build URL
        url = self.build_product_url(item_number)
        if not url:
            result["error"] = f"No URL pattern for supplier {self.supplier.code}"
            return result

        result["url"] = url
        logger.info(f"Scraping {item_number} from {url}")

        # Crawl the page
        crawl_result = self.crawl4ai.crawl(
            url,
            render_js=self.supplier.render_js,
            screenshot=True
        )

        if "error" in crawl_result:
            result["error"] = crawl_result["error"]
            return result

        html = crawl_result.get("html", "")
        if not html:
            result["error"] = "No HTML content returned"
            return result

        # Extract images using LLM
        extracted = self.ollama.extract_images(html, item_number)

        if "error" in extracted:
            # Fallback: try regex extraction
            logger.warning(f"LLM extraction failed, trying regex fallback")
            extracted = self._regex_extract_images(html)

        result["main_image"] = extracted.get("main_image")
        result["color_images"] = extracted.get("color_images", [])
        result["gallery_images"] = extracted.get("gallery_images", [])

        # Download images
        result["downloaded"] = self._download_images(item_number, extracted)

        return result

    def _regex_extract_images(self, html: str) -> Dict[str, Any]:
        """Fallback regex-based image extraction."""
        import re

        # Find all image URLs
        img_pattern = r'<img[^>]+src=["\']([^"\']+)["\']'
        all_images = re.findall(img_pattern, html, re.IGNORECASE)

        # Filter for likely product images
        product_images = [
            img for img in all_images
            if any(kw in img.lower() for kw in ['product', 'item', 'large', 'main', 'hero'])
            and not any(skip in img.lower() for skip in ['logo', 'icon', 'banner', 'ad'])
        ]

        return {
            "main_image": product_images[0] if product_images else None,
            "color_images": [],
            "gallery_images": product_images[1:] if len(product_images) > 1 else []
        }

    def _download_images(self, item_number: str, extracted: Dict) -> Dict[str, str]:
        """Download extracted images to local filesystem."""
        downloaded = {}

        # Download main image
        main_url = extracted.get("main_image")
        if main_url:
            path = self._download_single(main_url, item_number, "main")
            if path:
                downloaded["main"] = path

        # Download color images
        color_images = {}
        for color_info in extracted.get("color_images", []):
            color = color_info.get("color", "unknown")
            url = color_info.get("url")
            if url:
                path = self._download_single(url, item_number, f"color_{color}")
                if path:
                    color_images[color] = path
        if color_images:
            downloaded["colors"] = color_images

        # Download gallery images
        gallery_paths = []
        for i, url in enumerate(extracted.get("gallery_images", [])[:5]):  # Limit to 5
            path = self._download_single(url, item_number, f"gallery_{i}")
            if path:
                gallery_paths.append(path)
        if gallery_paths:
            downloaded["gallery"] = gallery_paths

        return downloaded

    def _download_single(self, url: str, item_number: str, suffix: str) -> Optional[str]:
        """Download a single image."""
        if not url:
            return None

        try:
            # Make URL absolute if needed
            if url.startswith("//"):
                url = "https:" + url
            elif url.startswith("/"):
                url = urljoin(self.supplier.catalog_base_url, url)

            # Determine extension
            ext = Path(url.split("?")[0]).suffix or ".jpg"
            safe_suffix = suffix.replace(" ", "_").replace("/", "-")
            filename = f"{item_number}_{safe_suffix}{ext}"
            local_path = self.output_dir / filename

            # Download
            response = httpx.get(url, timeout=30.0, follow_redirects=True)
            response.raise_for_status()

            local_path.write_bytes(response.content)
            logger.info(f"Downloaded: {filename} ({len(response.content)} bytes)")

            return str(local_path)

        except Exception as e:
            logger.warning(f"Failed to download {url}: {e}")
            return None

    def scrape_batch(self, item_numbers: List[str]) -> List[Dict[str, Any]]:
        """Scrape images for multiple products."""
        results = []
        for item_number in item_numbers:
            result = self.scrape_product_images(item_number)
            results.append(result)
        return results


# =============================================================================
# CLI
# =============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description='Scrape product images from supplier websites')
    parser.add_argument('--item-number', '-i', help='Single item number to scrape')
    parser.add_argument('--input', help='Excel/CSV file with item_number column')
    parser.add_argument('--supplier', '-s', required=True, choices=list(SUPPLIERS.keys()),
                       help='Supplier code')
    parser.add_argument('--output-dir', default='/tmp/scraped_images',
                       help='Directory to save images')
    parser.add_argument('--discover', action='store_true',
                       help='Discover supplier URL patterns (interactive)')
    parser.add_argument('--check-services', action='store_true',
                       help='Check if Crawl4AI and Ollama are running')

    args = parser.parse_args()

    # Get supplier config
    supplier = SUPPLIERS[args.supplier]

    # Initialize clients
    crawl4ai = Crawl4AIClient()
    ollama = OllamaClient()

    # Check services
    if args.check_services:
        print("Checking services...")
        print(f"  Crawl4AI ({crawl4ai.base_url}): {'✅ OK' if crawl4ai.health() else '❌ Not available'}")
        print(f"  Ollama ({ollama.base_url}): {'✅ OK' if ollama.health() else '❌ Not available'}")
        return

    # Initialize scraper
    scraper = SupplierImageScraper(
        supplier=supplier,
        crawl4ai=crawl4ai,
        ollama=ollama,
        output_dir=args.output_dir
    )

    if args.discover:
        print(f"Discovering URL patterns for {supplier.name}...")
        print(f"Current patterns:")
        print(f"  Product URL: {supplier.product_url_pattern}")
        print(f"  Search URL: {supplier.search_url_pattern}")
        print(f"\nTry visiting the supplier website and finding a product page.")
        print(f"Then update SUPPLIERS dict in this file with the correct pattern.")
        return

    # Scrape single item
    if args.item_number:
        result = scraper.scrape_product_images(args.item_number)
        print(json.dumps(result, indent=2))
        return

    # Scrape from file
    if args.input:
        if args.input.endswith('.xlsx'):
            df = pd.read_excel(args.input)
        else:
            df = pd.read_csv(args.input)

        item_numbers = df['item_number'].dropna().astype(str).tolist()
        logger.info(f"Scraping {len(item_numbers)} products...")

        results = scraper.scrape_batch(item_numbers)

        # Summary
        success = sum(1 for r in results if r.get('downloaded'))
        failed = sum(1 for r in results if r.get('error'))
        print(f"\n=== Scrape Summary ===")
        print(f"Total: {len(results)}")
        print(f"Success: {success}")
        print(f"Failed: {failed}")
        print(f"Images saved to: {args.output_dir}")

        # Save results
        results_path = Path(args.output_dir) / "scrape_results.json"
        results_path.write_text(json.dumps(results, indent=2))
        print(f"Results saved to: {results_path}")
        return

    parser.error("Must specify --item-number or --input")


if __name__ == '__main__':
    main()
