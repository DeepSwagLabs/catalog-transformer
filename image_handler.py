#!/usr/bin/env python3
"""
Product Image Handler

Downloads, processes, and uploads product images to Creative Merchandise.
Handles main images and color/variant images.

Usage (once we know the server structure):
    python image_handler.py products.xlsx --download-only
    python image_handler.py products.xlsx --upload-to-server
    python image_handler.py products.xlsx --upload-to-s3

Requires SSH access to determine:
    - Where images are stored on server
    - Database schema for image references
    - Whether using S3 or local filesystem
"""

import os
import sys
import logging
import hashlib
import requests
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass
from urllib.parse import urlparse
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class ImageConfig:
    """Configuration for image handling."""
    # Local paths
    download_dir: str = "/tmp/product_images"

    # Server paths (discover via SSH)
    server_image_dir: str = "/var/www/html/images/products"  # TODO: Verify
    server_host: str = "trunk1.creativemerch.com"
    server_user: str = "pat"

    # S3 config (if using)
    s3_bucket: Optional[str] = None
    s3_prefix: str = "product-images/"
    cloudfront_domain: str = "dpbxvxue3c4z7.cloudfront.net"

    # Processing
    max_width: int = 1200
    max_height: int = 1200
    thumbnail_size: Tuple[int, int] = (300, 300)
    quality: int = 85


class ImageDownloader:
    """Downloads images from URLs."""

    def __init__(self, config: ImageConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; ProductImageBot/1.0)'
        })

        # Ensure download directory exists
        Path(config.download_dir).mkdir(parents=True, exist_ok=True)

    def download(self, url: str, item_number: str, image_type: str = "main") -> Optional[str]:
        """
        Download image from URL.

        Args:
            url: Image URL
            item_number: Product item number (for filename)
            image_type: "main", "blank", or color name like "Navy Blue"

        Returns:
            Local file path or None if failed
        """
        if not url or pd.isna(url):
            return None

        try:
            # Determine extension from URL
            parsed = urlparse(url)
            ext = Path(parsed.path).suffix or '.jpg'

            # Create safe filename
            safe_type = image_type.replace(' ', '_').replace('/', '-')
            filename = f"{item_number}_{safe_type}{ext}"
            local_path = Path(self.config.download_dir) / filename

            # Skip if already downloaded
            if local_path.exists():
                logger.debug(f"Already downloaded: {filename}")
                return str(local_path)

            # Download
            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            with open(local_path, 'wb') as f:
                f.write(response.content)

            logger.info(f"Downloaded: {filename} ({len(response.content)} bytes)")
            return str(local_path)

        except Exception as e:
            logger.error(f"Failed to download {url}: {e}")
            return None

    def download_product_images(self, row: pd.Series) -> Dict[str, str]:
        """
        Download all images for a product.

        Expects columns:
            - item_number
            - image_url (main image)
            - blank_image_url (optional)
            - colors (comma-separated, for future color-specific images)

        Returns:
            Dict mapping image_type to local_path
        """
        images = {}
        item_number = str(row.get('item_number', 'unknown'))

        # Main image
        main_url = row.get('image_url') or row.get('ImageURL') or row.get('NewPictureURL')
        if main_url:
            path = self.download(main_url, item_number, "main")
            if path:
                images['main'] = path

        # Blank image (undecorated)
        blank_url = row.get('blank_image_url') or row.get('NewBlankPictureURL')
        if blank_url:
            path = self.download(blank_url, item_number, "blank")
            if path:
                images['blank'] = path

        # Future: Color-specific images if URLs are provided
        # colors = row.get('colors', '').split(',')
        # for color in colors:
        #     color_url = row.get(f'image_url_{color.strip()}')
        #     if color_url:
        #         path = self.download(color_url, item_number, color.strip())
        #         if path:
        #             images[f'color_{color.strip()}'] = path

        return images


class ImageUploader:
    """Uploads images to server or S3."""

    def __init__(self, config: ImageConfig):
        self.config = config

    def upload_via_sftp(self, local_path: str, remote_filename: str) -> bool:
        """
        Upload image via SFTP.

        TODO: Implement once we have SSH access and know the directory structure.
        """
        # Placeholder - needs paramiko or subprocess with scp
        logger.warning("SFTP upload not implemented - need SSH access first")

        # Example implementation:
        # import paramiko
        # ssh = paramiko.SSHClient()
        # ssh.connect(self.config.server_host, username=self.config.server_user, key_filename='~/.ssh/creativemerch_key')
        # sftp = ssh.open_sftp()
        # remote_path = f"{self.config.server_image_dir}/{remote_filename}"
        # sftp.put(local_path, remote_path)
        # sftp.close()
        # ssh.close()

        return False

    def upload_to_s3(self, local_path: str, s3_key: str) -> Optional[str]:
        """
        Upload image to S3.

        TODO: Implement if they're using S3 for image storage.
        """
        if not self.config.s3_bucket:
            logger.warning("S3 bucket not configured")
            return None

        # Placeholder - needs boto3
        # import boto3
        # s3 = boto3.client('s3')
        # s3.upload_file(local_path, self.config.s3_bucket, s3_key)
        # return f"https://{self.config.cloudfront_domain}/{s3_key}"

        logger.warning("S3 upload not implemented")
        return None


class ProductImageProcessor:
    """
    Main class for processing product images.

    Workflow:
        1. Load products from Excel
        2. Download images from URLs
        3. Optionally resize/optimize
        4. Upload to server or S3
        5. Return mapping of item_number -> image_paths for DB update
    """

    def __init__(self, config: Optional[ImageConfig] = None):
        self.config = config or ImageConfig()
        self.downloader = ImageDownloader(self.config)
        self.uploader = ImageUploader(self.config)

    def process_products(
        self,
        df: pd.DataFrame,
        download_only: bool = True
    ) -> Dict[str, Dict[str, str]]:
        """
        Process images for all products.

        Args:
            df: DataFrame with product data
            download_only: If True, only download (don't upload)

        Returns:
            Dict mapping item_number to {image_type: path}
        """
        results = {}

        for idx, row in df.iterrows():
            item_number = str(row.get('item_number', f'row_{idx}'))

            # Download images
            images = self.downloader.download_product_images(row)

            if not download_only:
                # Upload to server
                for img_type, local_path in images.items():
                    filename = Path(local_path).name
                    self.uploader.upload_via_sftp(local_path, filename)

            if images:
                results[item_number] = images

        logger.info(f"Processed images for {len(results)} products")
        return results


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Download and upload product images')
    parser.add_argument('input', help='Product Excel file')
    parser.add_argument('--download-only', action='store_true', help='Only download, do not upload')
    parser.add_argument('--upload-to-server', action='store_true', help='Upload via SFTP')
    parser.add_argument('--upload-to-s3', action='store_true', help='Upload to S3')
    parser.add_argument('--download-dir', default='/tmp/product_images', help='Local download directory')

    args = parser.parse_args()

    config = ImageConfig(download_dir=args.download_dir)
    processor = ProductImageProcessor(config)

    # Load products
    df = pd.read_excel(args.input)
    logger.info(f"Loaded {len(df)} products")

    # Process
    download_only = args.download_only or not (args.upload_to_server or args.upload_to_s3)
    results = processor.process_products(df, download_only=download_only)

    # Summary
    total_images = sum(len(imgs) for imgs in results.values())
    print(f"\n=== Image Processing Summary ===")
    print(f"Products with images: {len(results)}")
    print(f"Total images downloaded: {total_images}")
    print(f"Download directory: {config.download_dir}")

    if not download_only:
        print(f"Upload destination: {'S3' if args.upload_to_s3 else 'SFTP'}")


if __name__ == '__main__':
    main()
