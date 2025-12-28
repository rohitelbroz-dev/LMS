# urllib3 SSL Recursion Fix for Python 3.13

## Problem
Upload on Render was failing with:
```
RecursionError: maximum recursion depth exceeded
```

In the SSL context creation during `requests.post()`:
```
File "/opt/render/project/python/Python-3.13.4/lib/python3.13/ssl.py", line 561, in options
    super(SSLContext, SSLContext).options.__set__(self, value)
    [repeated 955 more times]
```

## Root Cause
**urllib3 1.26.16 is incompatible with Python 3.13**

- urllib3 1.26.16 was released before Python 3.13 was finalized
- Python 3.13's SSL module has different behavior for SSLContext options
- This causes infinite recursion when urllib3 tries to set SSL context options
- The issue doesn't manifest locally (Python 3.12) but appears on Render (Python 3.13)

## Solution

### 1. Upgraded urllib3 to 2.x
```diff
- urllib3==1.26.16
+ urllib3>=2.0.0,<3.0.0
```

**Why:**
- urllib3 2.0+ includes proper Python 3.13 support
- urllib3 2.6.2 is now installed (verified)
- Maintains backward compatibility with requests library

### 2. Added certifi for Certificate Management
```diff
+ certifi>=2024.0.0
```

**Why:**
- Ensures proper SSL certificate bundle is available
- Prevents certificate verification issues
- Explicit certificate handling prevents SSL context problems

### 3. Updated storage_helper.py

**Added imports:**
```python
import ssl
import certifi
```

**Modified requests call:**
```python
response = requests.post(
    upload_url, 
    files=files, 
    data=data, 
    timeout=30,
    verify=certifi.where()  # Explicit SSL verification
)
```

**Why:**
- Explicitly specifies certificate bundle to use
- Removes ambiguity in SSL context creation
- Works correctly with both urllib3 1.x and 2.x

## Changes Made

### requirements.txt
```diff
- urllib3==1.26.16
+ urllib3>=2.0.0,<3.0.0
+ certifi>=2024.0.0
  requests>=2.28.0
```

### storage_helper.py
- Added imports: `ssl`, `certifi`
- Updated `requests.post()` to use `verify=certifi.where()`

## Verification

✓ Local verification:
- urllib3 version: 2.6.2 (Python 3.12 in Codespaces)
- certifi working: `/home/codespace/.local/lib/python3.12/site-packages/certifi/cacert.pem`
- storage_helper imports successfully

## Expected Behavior on Render

When Render rebuilds with the updated requirements.txt:
1. Will install urllib3 2.x (compatible with Python 3.13)
2. Will install certifi for certificate management
3. Cloudinary REST API uploads will work without SSL recursion errors
4. File uploads should complete successfully

## Testing on Render

After Render rebuilds (should happen automatically):
1. Navigate to Create Lead or Edit Lead
2. Upload an image file
3. Should see: `[STORAGE] Uploading to Cloudinary via REST API: ...`
4. Should see: `[STORAGE] Uploaded to Cloudinary: ... -> https://res.cloudinary.com/...`
5. No more `RecursionError` in logs

## Deployment

- Commit hash: d49bf10
- Branch: main
- Auto-deployed to Render on git push
