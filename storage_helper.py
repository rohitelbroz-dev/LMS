"""storage_helper
Cloudinary-only storage helper.

This module expects Cloudinary credentials to be provided via environment variables.
It strips surrounding quotes from env values to avoid common render/GitHub UI mistakes.
All uploads are forced to Cloudinary; there is no local or Replit fallback.
"""

import os
from io import BytesIO
from typing import Dict

# Always default to Cloudinary-only mode. Allow overriding with STORAGE_BACKEND env var,
# but strip surrounding quotes if present.
def _strip_quotes(val: str | None) -> str | None:
    if val is None:
        return None
    return val.strip().strip('"').strip("'")

STORAGE_BACKEND = _strip_quotes(os.environ.get('STORAGE_BACKEND', 'cloudinary'))
IS_CLOUDINARY = False

if STORAGE_BACKEND == 'cloudinary':
    try:
        import cloudinary
        import cloudinary.uploader
        import cloudinary.api

        cloud_name = _strip_quotes(os.environ.get('CLOUDINARY_CLOUD_NAME'))
        api_key = _strip_quotes(os.environ.get('CLOUDINARY_API_KEY'))
        api_secret = _strip_quotes(os.environ.get('CLOUDINARY_API_SECRET'))
        cloudinary.config(
            cloud_name=cloud_name,
            api_key=api_key,
            api_secret=api_secret,
            secure=True,
        )
        IS_CLOUDINARY = True
        print(f"[STORAGE] Cloudinary backend configured for cloud: {cloud_name}")
    except Exception as e:
        print(f"[STORAGE] WARNING: Failed to initialize Cloudinary: {e}")
        IS_CLOUDINARY = False
else:
    print(f"[STORAGE] STORAGE_BACKEND='{STORAGE_BACKEND}' is not supported; only 'cloudinary' is allowed.")


def upload_file(file_data: bytes, filename: str, folder: str = 'uploads') -> Dict | None:
    """Upload bytes to Cloudinary and return a dict on success, or {'error':msg} on failure.

    This function does not save to local storage.
    """
    if not IS_CLOUDINARY:
        err = 'Cloudinary is not configured in this environment.'
        print(f"[STORAGE] {err}")
        return {'error': err}

    try:
        ext = filename.lower().rsplit('.', 1)[-1] if '.' in filename else ''
        image_exts = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp'}
        resource_type = 'image' if ext in image_exts else 'raw'
        public_id = f"{folder}/{filename}"
        file_obj = BytesIO(file_data)
        result = cloudinary.uploader.upload(
            file_obj,
            public_id=public_id,
            resource_type=resource_type,
            overwrite=False,
        )
        url = result.get('secure_url') or result.get('url')
        print(f"[STORAGE] Uploaded to Cloudinary: {public_id} -> {url}")
        return {'url': url, 'public_id': public_id, 'resource_type': resource_type}
    except Exception as e:
        err = str(e)
        print(f"[STORAGE] Cloudinary upload failed: {err}")
        return {'error': err}


def download_file(filename: str, folder: str = 'uploads') -> bytes | None:
    """
    Download a file from storage.
    For cloud backends that return external URLs (Cloudinary), this will return None and routes/templates should use the stored URL directly.
    Returns file bytes for local backends, or None otherwise.
    """
    # Cloudinary-served files are returned as external URLs; we don't proxy them.
    if IS_CLOUDINARY:
        return None

    # Cloudinary not configured; downloads are not supported in this environment.
    print("[STORAGE] download_file: Cloudinary not configured; cannot download.")
    return None



def file_exists(filename_or_obj: str | dict, folder: str = 'uploads') -> bool:
    """
    Check if a file exists in storage. Accepts a URL string, filename, or the dict returned by upload_file for cloudinary.
    """
    # Handle Cloudinary dict
    if isinstance(filename_or_obj, dict):
        public_id = filename_or_obj.get('public_id')
        resource_type = filename_or_obj.get('resource_type', 'raw')
        candidates = [public_id]
        if public_id and '.' in public_id:
            no_ext = '.'.join(public_id.split('.')[:-1])
            candidates.insert(0, no_ext)
            candidates.append(public_id)
        for pid in candidates:
            try:
                cloudinary.api.resource(pid, resource_type=resource_type)
                return True
            except Exception:
                continue
        return False

    # Handle URL string or public_id string
    if isinstance(filename_or_obj, str):
        if not IS_CLOUDINARY:
            return False
        if filename_or_obj.startswith('http'):
            public_id_no_ext, resource_type, ext = _cloudinary_parse_url(filename_or_obj)
            candidates = [public_id_no_ext]
            if ext:
                candidates.insert(0, f"{public_id_no_ext}.{ext}")
                candidates.append(public_id_no_ext)
        else:
            # treat the string as a public_id candidate
            candidates = [filename_or_obj]

        for pid in candidates:
            try:
                cloudinary.api.resource(pid, resource_type='raw')
                return True
            except Exception:
                continue
        return False

    return False


def delete_file(filename_or_obj: str | dict, folder: str = 'uploads') -> bool:
    """
    Delete a file from storage. Accepts a URL string, filename, or the dict returned by upload_file for cloudinary.
    """
    # Cloudinary dict case
    if isinstance(filename_or_obj, dict) and STORAGE_BACKEND == 'cloudinary' and IS_CLOUDINARY:
        public_id = filename_or_obj.get('public_id')
        resource_type = filename_or_obj.get('resource_type', 'raw')
        # Try multiple candidates for public_id (with/without extension)
        candidates = [public_id]
        if '.' in public_id:
            no_ext = '.'.join(public_id.split('.')[:-1])
            candidates.insert(0, no_ext)
            candidates.append(public_id)
        for pid in candidates:
            try:
                cloudinary.uploader.destroy(pid, resource_type=resource_type)
                print(f"[STORAGE] Deleted from Cloudinary: {pid} ({resource_type})")
                return True
            except Exception as e:
                # try next candidate
                last_exc = e
                continue
        print(f"[STORAGE] Cloudinary delete failed: {last_exc}")
        return False

    # URL string for Cloudinary
    if isinstance(filename_or_obj, str) and filename_or_obj.startswith('http') and STORAGE_BACKEND == 'cloudinary' and IS_CLOUDINARY:
        public_id_no_ext, resource_type, ext = _cloudinary_parse_url(filename_or_obj)
        candidates = [public_id_no_ext]
        if ext:
            candidates.insert(0, f"{public_id_no_ext}.{ext}")
            candidates.append(public_id_no_ext)
        for pid in candidates:
            try:
                cloudinary.uploader.destroy(pid, resource_type=resource_type)
                print(f"[STORAGE] Deleted from Cloudinary: {pid} ({resource_type})")
                return True
            except Exception as e:
                last_exc = e
                continue
        print(f"[STORAGE] Cloudinary delete failed: {last_exc}")
        return False

    # Only Cloudinary deletion is supported
    if isinstance(filename_or_obj, dict) and IS_CLOUDINARY:
        public_id = filename_or_obj.get('public_id')
        resource_type = filename_or_obj.get('resource_type', 'raw')
        candidates = [public_id]
        if public_id and '.' in public_id:
            no_ext = '.'.join(public_id.split('.')[:-1])
            candidates.insert(0, no_ext)
            candidates.append(public_id)
        for pid in candidates:
            try:
                cloudinary.uploader.destroy(pid, resource_type=resource_type)
                print(f"[STORAGE] Deleted from Cloudinary: {pid} ({resource_type})")
                return True
            except Exception as e:
                last_exc = e
                continue
        print(f"[STORAGE] Cloudinary delete failed: {last_exc}")
        return False

    if isinstance(filename_or_obj, str) and filename_or_obj.startswith('http') and IS_CLOUDINARY:
        public_id_no_ext, resource_type, ext = _cloudinary_parse_url(filename_or_obj)
        candidates = [public_id_no_ext]
        if ext:
            candidates.insert(0, f"{public_id_no_ext}.{ext}")
            candidates.append(public_id_no_ext)
        for pid in candidates:
            try:
                cloudinary.uploader.destroy(pid, resource_type=resource_type)
                print(f"[STORAGE] Deleted from Cloudinary: {pid} ({resource_type})")
                return True
            except Exception as e:
                last_exc = e
                continue
        print(f"[STORAGE] Cloudinary delete failed: {last_exc}")
        return False

    # Not a supported input or Cloudinary not configured
    print("[STORAGE] delete_file: unsupported input or Cloudinary not configured")
    return False


def _cloudinary_parse_url(url: str) -> tuple[str, str, str | None]:
    """Parse Cloudinary URL and return (public_id_no_ext, resource_type, ext).

    Example URL: https://res.cloudinary.com/<cloud>/raw/upload/v12345/folder/file.ext
    resource_type is the path segment before /upload/ (e.g., 'raw' or 'image' or 'video').
    public_id_no_ext is the path after upload/version/ with extension removed.
    ext is the lowercase extension (e.g., 'txt') or None.
    """
    try:
        parts = url.split('/upload/')
        if len(parts) < 2:
            return (url, 'raw', None)
        before = parts[0]
        rt = before.rstrip('/').split('/')[-1]
        after = parts[1]
        if after.startswith('v') and '/' in after:
            after = after.split('/', 1)[1]
        ext = None
        public_id_no_ext = after
        if '.' in after:
            ext = after.rsplit('.', 1)[1].lower()
            public_id_no_ext = after.rsplit('.', 1)[0]
        return (public_id_no_ext, rt, ext)
    except Exception:
        return (url, 'raw', None)


# Local filesystem helpers removed — Cloudinary-only storage.


def get_mime_type(filename: str) -> str:
    """Get MIME type based on file extension."""
    ext = filename.lower().split('.')[-1] if '.' in filename else ''
    mime_types = {
        'pdf': 'application/pdf',
        'png': 'image/png',
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'gif': 'image/gif',
        'webp': 'image/webp',
        'bmp': 'image/bmp',
        'doc': 'application/msword',
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'xls': 'application/vnd.ms-excel',
        'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'txt': 'text/plain',
        'csv': 'text/csv',
    }
    return mime_types.get(ext, 'application/octet-stream')
