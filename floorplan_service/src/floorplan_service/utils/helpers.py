import os
from io import BytesIO
from urllib.parse import urlparse

import boto3
import httpx
from PIL import Image

from ..config import settings
from ..utils.logging_config import logger

# === Helper Constants ===
INVALID_FLOAT_VALUES = frozenset([None, "", "nan", "unknown", "Unknown"])
INVALID_DIMENSION_VALUES = frozenset([None, "", "unknown", "Unknown"])
INVALID_INT_VALUES = frozenset([None, "", "nan", "unknown", "Unknown"])
INVALID_STRING_VALUES = frozenset([None])  # Only None is truly invalid for strings

# === Helper Functions ===


def safe_float(value):
    """Safely converts a value to float, returning None for invalid inputs."""
    if isinstance(value, str):
        value = value.strip()
    if value in INVALID_FLOAT_VALUES:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def safe_int(value):
    """
    Safely attempts to convert a value to an integer.
    Handles None, empty strings, 'nan', 'unknown', and float strings like '5.0'.
    Returns None if conversion is not possible or value is invalid.
    """
    if isinstance(value, str):
        value = value.strip()
    if value in INVALID_INT_VALUES:
        return None
    try:
        # Use float conversion first to handle "5.0" etc.
        return int(float(value))
    except (ValueError, TypeError):
        return None


def convert_gif_to_jpeg_and_upload_to_s3(super_id, url, property_id):
    """
    Downloads a GIF from the URL, converts it to JPEG, uploads to S3,
    and returns the S3 URL of the uploaded JPEG.

    Args:
        super_id (str): The super_id of the GIF image
        url (str): The URL of the GIF image
        property_id (str): Property ID for S3 path construction

    Returns:
        str: S3 URL of the uploaded JPEG image or original URL if any error occurs
    """
    # Return original URL if not a GIF
    parsed_url = urlparse(url)
    base_name = os.path.basename(parsed_url.path)
    if not base_name.lower().endswith(".gif"):
        return url

    logger.info(f"Converting GIF to JPEG for URL: {url}")
    try:
        # Download the GIF
        response = httpx.get(url, stream=True, timeout=30)
        response.raise_for_status()

        # Generate a new filename (replacing .gif with .jpg)
        new_filename = os.path.splitext(base_name)[0] + ".jpg"

        # Convert using PIL
        with Image.open(BytesIO(response.content)) as img:
            # Convert to RGB (removing transparency if present)
            if img.mode in ("RGBA", "P"):
                rgb_img = img.convert("RGB")
            else:
                rgb_img = img

            # Save to a temporary buffer
            temp_buffer = BytesIO()
            rgb_img.save(temp_buffer, format="JPEG", quality=90)
            temp_buffer.seek(0)

            AWS_ACCESS_KEY_ID = settings.AWS_ACCESS_KEY_ID
            AWS_SECRET_ACCESS_KEY = settings.AWS_SECRET_ACCESS_KEY
            AWS_STORAGE_BUCKET_NAME = settings.AWS_STORAGE_BUCKET_NAME
            AWS_S3_CUSTOM_DOMAIN = settings.AWS_S3_CUSTOM_DOMAIN
            AWS_S3_REGION_NAME = settings.AWS_S3_REGION_NAME

            # Get AWS credentials from settings or environment variables
            if not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY:
                logger.error(
                    "AWS credentials not found in settings or environment variables"
                )
                return url

            # Get S3 client using boto3
            s3_client = boto3.client(
                "s3",
                aws_access_key_id=AWS_ACCESS_KEY_ID,
                aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            )

            if not AWS_STORAGE_BUCKET_NAME:
                logger.error(
                    "AWS bucket name not found in settings or environment variables"
                )
                return url
            s3_path = f"converted_images/super_id_{super_id}_property_{property_id}/{new_filename}"

            # Upload to S3
            s3_client.upload_fileobj(
                temp_buffer,
                AWS_STORAGE_BUCKET_NAME,
                s3_path,
                ExtraArgs={
                    "ContentType": "image/jpeg",
                    # ACL disabled since the bucket does not support ACLs
                },
            )

            # Construct the new URL - try multiple approaches for maximum compatibility
            if AWS_S3_CUSTOM_DOMAIN:
                s3_url = f"https://{AWS_S3_CUSTOM_DOMAIN}/{s3_path}"
            else:
                # Standard S3 URL format
                s3_url = f"https://{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.amazonaws.com/{s3_path}"

                # If region is us-east-1, there's an alternate format without region in URL that might work
                if AWS_S3_REGION_NAME == "us-east-1":
                    # Try an alternate URL format as backup in case the first one doesn't work
                    s3_url = (
                        f"https://{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/{s3_path}"
                    )
            logger.info(
                f"Successfully converted GIF to JPEG and uploaded to S3: {s3_url}"
            )
            return s3_url

    except Exception as e:
        # Log the error but return the original URL to not block the flow
        logger.error(f"Error converting GIF to JPEG: {str(e)}. Using original URL.")
        return url
