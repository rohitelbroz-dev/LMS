"""storage_helper
Supports Cloudinary and Supabase Storage backends with a unified API.

Environment variables:
- STORAGE_BACKEND = 'cloudinary' (default) or 'supabase'

Cloudinary (unsigned REST API):
  CLOUDINARY_CLOUD_NAME, CLOUDINARY_UPLOAD_PRESET
  (Optional for deletion: CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET)

Supabase: SUPABASE_URL (https://<project>.supabase.co), SUPABASE_KEY, SUPABASE_BUCKET

Exports:
- upload_file(file_bytes, filename, folder='uploads') -> dict or {'error':...}
- download_file(...) -> bytes|None
- delete_file(...)
- file_exists(...)
- get_storage_debug() -> dict
"""

import os
import sys
import traceback
from typing import Dict
import time
import hashlib
import requests
import ssl
import certifi


def _strip_quotes(val: str | None) -> str | None:
    if val is None:
        return None
    return val.strip().strip('"').strip("'")


STORAGE_BACKEND = _strip_quotes(os.environ.get('STORAGE_BACKEND', 'cloudinary'))

# Cloudinary state - using REST API approach (unsigned uploads with preset)
IS_CLOUDINARY = False
cloud_name: str | None = None
upload_preset: str | None = None
api_key: str | None = None  # optional, for file deletion only
api_secret: str | None = None  # optional, for file deletion only

# Supabase state
IS_SUPABASE = False
SUPABASE_URL: str | None = None
SUPABASE_KEY: str | None = None
SUPABASE_BUCKET: str = _strip_quotes(os.environ.get('SUPABASE_BUCKET', 'uploads'))


# Initialize selected backend
if STORAGE_BACKEND == 'cloudinary':
    try:
        cloud_name = _strip_quotes(os.environ.get('CLOUDINARY_CLOUD_NAME'))
        upload_preset = _strip_quotes(os.environ.get('CLOUDINARY_UPLOAD_PRESET'))
        api_key = _strip_quotes(os.environ.get('CLOUDINARY_API_KEY'))
        api_secret = _strip_quotes(os.environ.get('CLOUDINARY_API_SECRET'))
        
        if not cloud_name:
            raise ValueError('CLOUDINARY_CLOUD_NAME must be set')
        if not upload_preset:
            raise ValueError('CLOUDINARY_UPLOAD_PRESET must be set (create an unsigned preset in Cloudinary dashboard)')
        
        IS_CLOUDINARY = True
        print(f"[STORAGE] Cloudinary backend configured for cloud: {cloud_name} (preset: {upload_preset})")
        print(f"[STORAGE] Using unsigned uploads via REST API; Python: {sys.version.splitlines()[0]}")
    except Exception as e:
        print(f"[STORAGE] WARNING: Failed to initialize Cloudinary: {e}")
        IS_CLOUDINARY = False

elif STORAGE_BACKEND == 'supabase':
    try:
        SUPABASE_URL = _strip_quotes(os.environ.get('SUPABASE_URL'))
        SUPABASE_KEY = _strip_quotes(os.environ.get('SUPABASE_KEY'))
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise RuntimeError('SUPABASE_URL and SUPABASE_KEY must be set for supabase backend')
        IS_SUPABASE = True
        print(f"[STORAGE] Supabase backend configured: {SUPABASE_URL} (bucket={SUPABASE_BUCKET})")
    except Exception as e:
        print(f"[STORAGE] WARNING: Failed to initialize Supabase backend: {e}")
        IS_SUPABASE = False

else:
    print(f"[STORAGE] STORAGE_BACKEND='{STORAGE_BACKEND}' is not supported; use 'cloudinary' or 'supabase'.")


def get_mime_type(filename: str) -> str:
    """Determine MIME type based on file extension."""
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


def upload_file(file_data: bytes, filename: str, folder: str = 'uploads') -> Dict:
    """Dispatch upload to the configured backend.

    Returns a dict with keys: 'url','public_id','resource_type' on success or
    {'error':..., 'trace':...} on failure.
    """
    if STORAGE_BACKEND == 'supabase':
        return _supabase_upload(file_data, filename, folder)
    return _cloudinary_upload(file_data, filename, folder)


def _supabase_upload(file_data: bytes, filename: str, folder: str = 'uploads') -> Dict:
    if not IS_SUPABASE:
        return {'error': 'supabase_not_configured'}
    try:
        path = f"{folder}/{filename}"
        # Supabase Storage upload endpoint for objects
        url = f"{SUPABASE_URL.rstrip('/')}/storage/v1/object/{SUPABASE_BUCKET}"
        headers = {
            'Authorization': f'Bearer {SUPABASE_KEY}',
            'apikey': SUPABASE_KEY,
        }
        files = {
            'file': (filename, file_data, get_mime_type(filename))
        }
        data = {'path': path}
        resp = requests.post(url, headers=headers, files=files, data=data, timeout=30)
        if resp.status_code not in (200, 201):
            return {'error': 'supabase_upload_failed', 'status': resp.status_code, 'body': resp.text}
        public_url = f"{SUPABASE_URL.rstrip('/')}/storage/v1/object/public/{SUPABASE_BUCKET}/{path}"
        print(f"[STORAGE] Uploaded to Supabase: {path} -> {public_url}")
        ext = filename.lower().rsplit('.', 1)[-1] if '.' in filename else ''
        resource_type = 'image' if ext in {'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp'} else 'raw'
        return {'url': public_url, 'public_id': path, 'resource_type': resource_type}
    except Exception as e:
        tb = traceback.format_exc()
        print(f"[STORAGE] Supabase upload failed: {e}\n{tb}")
        return {'error': str(e), 'trace': tb}


def _cloudinary_upload(file_data: bytes, filename: str, folder: str = 'uploads') -> Dict:
    """Upload to Cloudinary using REST API (unsigned uploads with preset).
    
    This matches the pattern used in React/Next.js and works better on 
    restrictive environments like Render.
    """
    if not IS_CLOUDINARY:
        return {'error': 'cloudinary_not_configured'}
    
    try:
        # Determine resource type
        ext = filename.lower().rsplit('.', 1)[-1] if '.' in filename else ''
        image_exts = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp'}
        resource_type = 'image' if ext in image_exts else 'raw'
        
        # Build public_id (path in Cloudinary)
        public_id = f"{folder}/{filename}"
        
        # Prepare the FormData payload (matching React example)
        files = {
            'file': (filename, file_data, get_mime_type(filename))
        }
        data = {
            'upload_preset': upload_preset,
            'public_id': public_id,
            'resource_type': resource_type,
        }
        
        # REST API endpoint
        upload_url = f"https://api.cloudinary.com/v1_1/{cloud_name}/{resource_type}/upload"
        
        print(f"[STORAGE] Uploading to Cloudinary via REST API: {public_id}")
        
        # Make the request with proper SSL/certificate handling
        response = requests.post(
            upload_url, 
            files=files, 
            data=data, 
            timeout=30,
            verify=certifi.where()  # Use certifi's certificate bundle for SSL verification
        )
        
        if response.status_code not in (200, 201):
            error_msg = f"HTTP {response.status_code}"
            try:
                error_data = response.json()
                if 'error' in error_data:
                    error_msg += f": {error_data['error'].get('message', str(error_data['error']))}"
            except Exception:
                error_msg += f": {response.text[:200]}"
            
            print(f"[STORAGE] Cloudinary upload failed: {error_msg}")
            return {'error': f'cloudinary_upload_failed: {error_msg}'}
        
        # Parse response
        result = response.json()
        url = result.get('secure_url') or result.get('url')
        
        if not url:
            print(f"[STORAGE] Cloudinary upload: no URL in response")
            return {'error': 'no_url_in_response', 'response': result}
        
        print(f"[STORAGE] Uploaded to Cloudinary: {public_id} -> {url}")
        return {'url': url, 'public_id': public_id, 'resource_type': resource_type}
        
    except requests.RequestException as e:
        tb = traceback.format_exc()
        print(f"[STORAGE] Cloudinary REST API request failed: {e}\n{tb}")
        return {'error': f'request_failed: {str(e)}', 'trace': tb}
    except Exception as e:
        tb = traceback.format_exc()
        print(f"[STORAGE] Cloudinary upload failed: {e}\n{tb}")
        return {'error': str(e), 'trace': tb}


def download_file(filename: str, folder: str = 'uploads') -> bytes | None:
    """For cloud backends we return None and expect callers to use public URLs."""
    return None


def file_exists(filename_or_obj: str | dict, folder: str = 'uploads') -> bool:
    """Check if a file exists in the configured storage backend."""
    # Supabase path
    if STORAGE_BACKEND == 'supabase' and IS_SUPABASE:
        if isinstance(filename_or_obj, dict):
            pid = filename_or_obj.get('public_id')
        else:
            pid = filename_or_obj
        if not pid:
            return False
        if pid.startswith('http'):
            try:
                r = requests.head(pid, timeout=10)
                return r.status_code == 200
            except Exception:
                return False
        url = f"{SUPABASE_URL.rstrip('/')}/storage/v1/object/public/{SUPABASE_BUCKET}/{pid}"
        try:
            r = requests.head(url, timeout=10)
            return r.status_code == 200
        except Exception:
            return False

    # Cloudinary path
    if STORAGE_BACKEND == 'cloudinary' and IS_CLOUDINARY:
        try:
            if isinstance(filename_or_obj, dict):
                url = filename_or_obj.get('url')
            elif isinstance(filename_or_obj, str) and filename_or_obj.startswith('http'):
                url = filename_or_obj
            else:
                # For non-URL paths, we can't easily check existence
                return False
            
            # Check if the URL is accessible
            if url:
                r = requests.head(url, timeout=10)
                return r.status_code == 200
            return False
        except Exception:
            return False

    return False


def delete_file(filename_or_obj: str | dict, folder: str = 'uploads') -> bool:
    """Delete a file from the configured storage backend."""
    # Supabase delete
    if STORAGE_BACKEND == 'supabase' and IS_SUPABASE:
        if isinstance(filename_or_obj, dict):
            path = filename_or_obj.get('public_id')
        else:
            path = filename_or_obj
        if not path:
            return False
        if path.startswith('http'):
            try:
                parts = path.split('/storage/v1/object/public/')
                if len(parts) == 2:
                    bucket_and_path = parts[1]
                    if '/' in bucket_and_path:
                        _, obj_path = bucket_and_path.split('/', 1)
                        path = obj_path
            except Exception:
                pass
        url = f"{SUPABASE_URL.rstrip('/')}/storage/v1/object/{SUPABASE_BUCKET}/{path}"
        headers = {'Authorization': f'Bearer {SUPABASE_KEY}', 'apikey': SUPABASE_KEY}
        try:
            r = requests.delete(url, headers=headers, timeout=10)
            return r.status_code in (200, 204)
        except Exception as e:
            print(f"[STORAGE] Supabase delete failed: {e}")
            return False

    # Cloudinary delete
    if STORAGE_BACKEND == 'cloudinary' and IS_CLOUDINARY:
        try:
            if isinstance(filename_or_obj, dict):
                public_id = filename_or_obj.get('public_id')
                resource_type = filename_or_obj.get('resource_type', 'raw')
            elif isinstance(filename_or_obj, str) and filename_or_obj.startswith('http'):
                # Extract public_id from URL if needed
                public_id = filename_or_obj
                resource_type = 'raw'
            else:
                public_id = filename_or_obj
                resource_type = 'raw'
            
            # Only attempt deletion if we have API credentials
            if api_key and api_secret:
                timestamp = str(int(time.time()))
                params_to_sign = {'public_id': public_id, 'timestamp': timestamp}
                pieces = []
                for k in sorted(params_to_sign.keys()):
                    pieces.append(f"{k}={params_to_sign[k]}")
                to_sign = '&'.join(pieces) + api_secret
                signature = hashlib.sha1(to_sign.encode('utf-8')).hexdigest()
                
                delete_url = f"https://api.cloudinary.com/v1_1/{cloud_name}/{resource_type}/destroy"
                response = requests.post(
                    delete_url,
                    data={
                        'public_id': public_id,
                        'api_key': api_key,
                        'timestamp': timestamp,
                        'signature': signature
                    },
                    timeout=10
                )
                
                if response.status_code in (200, 204):
                    print(f"[STORAGE] Deleted from Cloudinary: {public_id} ({resource_type})")
                    return True
                else:
                    print(f"[STORAGE] Cloudinary delete failed: HTTP {response.status_code}")
                    return False
            else:
                print(f"[STORAGE] Cannot delete from Cloudinary without API credentials")
                return False
        except Exception as e:
            print(f"[STORAGE] Cloudinary delete failed: {e}")
            return False

    print("[STORAGE] delete_file: unsupported input or storage not configured")
    return False


def get_storage_debug() -> Dict:
    """Return debug information about the storage configuration."""
    try:
        return {
            'IS_CLOUDINARY': IS_CLOUDINARY,
            'IS_SUPABASE': IS_SUPABASE,
            'STORAGE_BACKEND': STORAGE_BACKEND,
            'cloud_name': cloud_name,
            'upload_preset': upload_preset,
            'has_api_credentials': bool(api_key and api_secret),
            'supabase_url': SUPABASE_URL,
            'supabase_bucket': SUPABASE_BUCKET,
            'python_version': sys.version.splitlines()[0]
        }
    except Exception as e:
        return {'error': str(e)}
