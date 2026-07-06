"""Aliyun OSS upload service for question images."""
import os
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


def get_oss_client():
    """Create and return an OSS Bucket object."""
    import oss2

    access_key_id = settings.ALIYUN_OSS_ACCESS_KEY_ID
    access_key_secret = settings.ALIYUN_OSS_ACCESS_KEY_SECRET
    endpoint = settings.ALIYUN_OSS_ENDPOINT
    bucket_name = settings.ALIYUN_OSS_BUCKET

    if not all([access_key_id, access_key_secret, bucket_name]):
        raise OSError('OSS credentials not configured.')

    auth = oss2.Auth(access_key_id, access_key_secret)
    bucket = oss2.Bucket(auth, endpoint, bucket_name)
    return bucket


def upload_crop_image(local_path: str, prefix: str = 'question_crops') -> str:
    """Upload a cropped image to OSS and return the public URL."""
    import oss2

    bucket = get_oss_client()
    filename = os.path.basename(local_path)
    oss_key = f'{prefix}/{filename}'

    try:
        with open(local_path, 'rb') as f:
            bucket.put_object(oss_key, f)
    except oss2.exceptions.OssError as e:
        logger.error(f'OSS upload failed for {local_path}: {e}')
        raise OSError(f'OSS upload failed: {e}')

    url = f'https://{bucket.bucket_name}.{bucket.endpoint.replace("https://", "")}/{oss_key}'
    logger.info(f'Uploaded to OSS: {url}')
    return url


def upload_crop_image_safe(local_path: str, prefix: str = 'question_crops') -> str | None:
    """Upload to OSS, returning None on failure (non-raising wrapper)."""
    try:
        return upload_crop_image(local_path, prefix)
    except OSError as e:
        logger.warning(f'OSS upload skipped (non-fatal): {e}')
        return None
