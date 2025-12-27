"""
Storage Helper Module
Handles file storage for lead attachments and profile pictures.
Supports Cloudinary and local filesystem backends. The legacy Replit Object Storage backend has been removed and is treated as an alias for the local filesystem.
"""

import os
from io import BytesIO
from typing import Union, Dict, Any

# Supported backends: 'cloudinary', 's3', 'local'
STORAGE_BACKEND = os.environ.get('STORAGE_BACKEND', 'local')
IS_CLOUDINARY = False

# Legacy handling: if someone still has the old 'replit' value, warn and fall back to local
if STORAGE_BACKEND == 'replit':
    print("[STORAGE] WARNING: 'replit' backend support has been removed. Falling back to 'local' backend.")
    STORAGE_BACKEND = 'local'

# Cloudinary backend
if STORAGE_BACKEND == 'cloudinary':
    try:
        import cloudinary
        import cloudinary.uploader
        import cloudinary.api
        # If CLOUDINARY_URL is provided it will be used; otherwise use components
        cloudinary.config( 
            cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME'), 
            api_key = os.environ.get('CLOUDINARY_API_KEY'), 
            api_secret = os.environ.get('CLOUDINARY_API_SECRET'), 
            secure = True
        )
        IS_CLOUDINARY = True
        print(f"[STORAGE] Cloudinary backend configured for cloud: {os.environ.get('CLOUDINARY_CLOUD_NAME')}")
    except Exception as e:
        print(f"[STORAGE] WARNING: Failed to initialize Cloudinary: {e}")
        IS_CLOUDINARY = False

else:
    print(f"[STORAGE] Using '{STORAGE_BACKEND}' backend (local filesystem by default)")



def upload_file(file_data: bytes, filename: str, folder: str = 'uploads') -> dict | str | None:
    """
    Upload a file to storage.
    For cloud backends, returns a dict: {'url','public_id','resource_type'} on success.
    For local filesystem, returns the storage path string.
    Returns None on failure.
    """
    storage_path = f"{folder}/{filename}"

    # Force Cloudinary: if Cloudinary is initialized (IS_CLOUDINARY True) always upload there.
    # Do NOT fall back to local filesystem — return an explicit error when Cloudinary is not configured.
    if IS_CLOUDINARY:
        try:
            # Determine resource type (image vs raw)
            ext = filename.lower().rsplit('.', 1)[-1] if '.' in filename else ''
            image_exts = {'png','jpg','jpeg','gif','webp','bmp'}
            resource_type = 'image' if ext in image_exts else 'raw'
            public_id = f"{folder}/{filename}"
            # Upload bytes via BytesIO
            from io import BytesIO
            file_obj = BytesIO(file_data)
            result = cloudinary.uploader.upload(
                file_obj,
                public_id=public_id,
                resource_type=resource_type,
                overwrite=False
            )
            url = result.get('secure_url') or result.get('url')
            print(f"[STORAGE] Uploaded to Cloudinary: {public_id} -> {url}")
            return {'url': url, 'public_id': public_id, 'resource_type': resource_type}
        except Exception as e:
            err = str(e)
            print(f"[STORAGE] Cloudinary upload failed: {err}")
            return {'error': err}

    # Cloudinary not configured — in forced mode we reject the upload and return an explicit error.
    err = 'Cloudinary is not configured on this environment; uploads are required to go to Cloudinary.'
    print(f"[STORAGE] {err}")
    return {'error': err}


def download_file(filename: str, folder: str = 'uploads') -> bytes | None:
    """
    Download a file from storage.
    For cloud backends that return external URLs (Cloudinary), this will return None and routes/templates should use the stored URL directly.
    Returns file bytes for local backends, or None otherwise.
    """
    storage_path = f"{folder}/{filename}"

    if STORAGE_BACKEND == 'cloudinary' and IS_CLOUDINARY:
        # Files are served via external URLs; do not proxy by default
        return None

    return _load_local(filename, folder)



def file_exists(filename_or_obj: str | dict, folder: str = 'uploads') -> bool:
    """
    Check if a file exists in storage. Accepts a URL string, filename, or the dict returned by upload_file for cloudinary.
    """
    # Handle Cloudinary dict
    if isinstance(filename_or_obj, dict):
        public_id = filename_or_obj.get('public_id')
        resource_type = filename_or_obj.get('resource_type', 'raw')
        # Try both with and without extension
        candidates = [public_id]
        if '.' in public_id:
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

    # Handle URL string
    if isinstance(filename_or_obj, str) and filename_or_obj.startswith('http') and STORAGE_BACKEND == 'cloudinary' and IS_CLOUDINARY:
        public_id_no_ext, resource_type, ext = _cloudinary_parse_url(filename_or_obj)
        candidates = [public_id_no_ext]
        if ext:
            candidates.insert(0, f"{public_id_no_ext}.{ext}")
            candidates.append(public_id_no_ext)
        for pid in candidates:
            try:
                cloudinary.api.resource(pid, resource_type=resource_type)
                return True
            except Exception:
                continue
        return False

    # Fallbacks for Replit/local
    filename = filename_or_obj if isinstance(filename_or_obj, str) and not filename_or_obj.startswith('http') else filename_or_obj
    storage_path = f"{folder}/{filename}"

    return _exists_local(filename, folder)


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

    # Replit/local fallbacks
    filename = filename_or_obj if isinstance(filename_or_obj, str) else ''
    storage_path = f"{folder}/{filename}"

    return _delete_local(filename, folder)


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


def _save_local(file_data: bytes, filename: str, folder: str) -> bool:
    """Save file to local filesystem."""
    try:
        os.makedirs(folder, exist_ok=True)
        filepath = os.path.join(folder, filename)
        with open(filepath, 'wb') as f:
            f.write(file_data)
        print(f"[STORAGE] Saved locally: {filepath}")
        return True
    except Exception as e:
        print(f"[STORAGE] Local save failed: {e}")
        return False


def _load_local(filename: str, folder: str) -> bytes | None:
    """Load file from local filesystem."""
    try:
        filepath = os.path.join(folder, filename)
        with open(filepath, 'rb') as f:
            return f.read()
    except Exception as e:
        print(f"[STORAGE] Local load failed: {e}")
        return None


def _exists_local(filename: str, folder: str) -> bool:
    """Check if file exists locally."""
    filepath = os.path.join(folder, filename)
    return os.path.exists(filepath)


def _delete_local(filename: str, folder: str) -> bool:
    """Delete file from local filesystem."""
    try:
        filepath = os.path.join(folder, filename)
        if os.path.exists(filepath):
            os.remove(filepath)
            print(f"[STORAGE] Deleted locally: {filepath}")
            return True
        return False
    except Exception as e:
        print(f"[STORAGE] Local delete failed: {e}")
        return False


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
