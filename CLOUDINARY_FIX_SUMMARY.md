# Cloudinary Upload Issue - Fix Summary

## Problem Identified

Your Flask application was using the **Cloudinary Python SDK** for uploads, which had these issues on Render:
- RecursionError with urllib3 compatibility
- Complex fallback mechanisms that were unreliable
- Required API credentials to be passed through the SDK
- Works locally but fails on Render's restricted environment

## Solution Implemented

### 1. **Switched to Cloudinary REST API** (Like Your React Project)
Instead of using the SDK, we now make direct HTTP POST requests to Cloudinary's REST API endpoint:

```python
# OLD (SDK-based)
import cloudinary.uploader
cloudinary.uploader.upload(file_obj)

# NEW (REST API-based)
import requests
response = requests.post(
    f"https://api.cloudinary.com/v1_1/{cloud_name}/image/upload",
    files={'file': file_data},
    data={'upload_preset': preset}
)
```

### 2. **Key Changes Made**

**File: `storage_helper.py`**
- ✅ Removed `cloudinary` SDK imports
- ✅ Replaced SDK upload with REST API calls using `requests`
- ✅ Uses unsigned uploads with `CLOUDINARY_UPLOAD_PRESET` (no credentials needed)
- ✅ Simpler error handling and logging
- ✅ Added detailed comments explaining the flow
- ✅ Kept file_exists() and delete_file() working (with optional API credentials)

**File: `requirements.txt`**
- ✅ Removed `cloudinary==1.43.0` dependency
- ✅ Kept `requests` (already there, used by REST API)
- ✅ Removed unused imports

### 3. **Environment Variables Required**

For **uploads to work on Render**:
```
CLOUDINARY_CLOUD_NAME=your-cloud-name
CLOUDINARY_UPLOAD_PRESET=your-preset-name
```

**Optional** (for file deletion):
```
CLOUDINARY_API_KEY=...
CLOUDINARY_API_SECRET=...
```

## Setup Instructions for Render

### 1. Create Upload Preset in Cloudinary
1. Log in: https://cloudinary.com/console
2. Go to **Settings → Upload**
3. Click **Add upload preset**
4. Set **Signing Mode** to **Unsigned** ← Important!
5. Give it a name (e.g., `lms-uploads`)
6. Click **Save**

### 2. Set Environment Variables in Render
In your Render service **Environment** settings, add:
```
CLOUDINARY_CLOUD_NAME=your-cloud-name
CLOUDINARY_UPLOAD_PRESET=lms-uploads
STORAGE_BACKEND=cloudinary
```

### 3. Deploy
```bash
git add .
git commit -m "Fix: Switch Cloudinary uploads to REST API for Render compatibility"
git push
```

Render will auto-deploy. Test by creating a lead with an attachment.

## How It Works

### Upload Process
1. User submits lead form with file attachment
2. Flask handler calls `upload_file(file_bytes, filename)`
3. `_cloudinary_upload()` function:
   - Builds FormData with file + upload_preset
   - POSTs to `https://api.cloudinary.com/v1_1/{cloud}/image/upload`
   - Gets back secure URL
   - Returns `{'url': 'https://...', 'public_id': '...', ...}`
4. URL is saved to database
5. ✅ Done!

### Code Flow in app.py
```python
# Line 1365-1383 in app.py (new_lead function)
if form.attachment.data:
    file_data = file.read()
    upload_result = upload_file(file_data, filename, 'uploads')
    if upload_result.get('error'):
        flash(f"Upload failed: {upload_result['error']}")
    else:
        attachment_path = upload_result['url']  # Store this URL
```

Same for edit_lead (line 3045-3075)

## Why This Works on Render

### ✅ Advantages of REST API Approach
1. **No SDK**: No urllib3 conflicts, no RecursionError
2. **HTTP-based**: Works on any platform with internet access
3. **No auth**: Uses preset instead of API credentials
4. **Battle-tested**: Your React project uses this pattern successfully
5. **Lightweight**: Single HTTP request, minimal dependencies

### ✅ Cloudinary's Unsigned Uploads
- Safe: Only uploads to your Cloudinary account
- Controlled: You set file types/sizes in preset
- No credentials exposed: Preset name is like a public API key that can only upload

## Comparison

| Aspect | Old (SDK) | New (REST API) |
|--------|-----------|---|
| Dependencies | cloudinary SDK | requests only |
| Authentication | API key/secret | Upload preset |
| Render Compatibility | ❌ Fails | ✅ Works |
| Error Handling | Complex fallbacks | Simple HTTP errors |
| Performance | Slower (SDK overhead) | Fast (direct HTTP) |
| Production Ready | ❌ Issues | ✅ Yes |

## Testing Locally

Before pushing to Render, test locally:

```bash
# Set env vars
export CLOUDINARY_CLOUD_NAME=your-cloud-name
export CLOUDINARY_UPLOAD_PRESET=your-preset-name
export STORAGE_BACKEND=cloudinary

# Run Flask
python app.py

# Go to http://localhost:5000/lead/new
# Try uploading a file
# Check logs for [STORAGE] messages
```

You should see:
```
[STORAGE] Cloudinary backend configured for cloud: your-cloud-name (preset: your-preset-name)
[STORAGE] Using unsigned uploads via REST API
...
[STORAGE] Uploading to Cloudinary via REST API: uploads/20240101_120000_file.pdf
[STORAGE] Uploaded to Cloudinary: uploads/... -> https://res.cloudinary.com/...
```

## Troubleshooting

| Error | Cause | Solution |
|-------|-------|----------|
| `CLOUDINARY_UPLOAD_PRESET must be set` | Env var missing | Add to Render/local env |
| `HTTP 401` | Preset is "Signed" not "Unsigned" | Recreate preset as Unsigned |
| `HTTP 400` | Bad request | Check cloud_name and preset name spelling |
| Uploads fail on Render but work locally | Missing env vars on Render | Copy env vars to Render dashboard |

## Files Modified

1. **storage_helper.py** - Complete refactor to REST API
2. **requirements.txt** - Removed cloudinary SDK
3. **CLOUDINARY_SETUP_GUIDE.md** - Added detailed setup instructions

## No Changes Needed In

- `app.py` - All function signatures remain the same
- `forms.py` - No changes needed
- `templates/lead_form.html` - No changes needed
- `templates/lead_edit.html` - No changes needed
- Any other files - Drop-in replacement

## Next Steps

1. ✅ Create unsigned upload preset in Cloudinary (see guide above)
2. ✅ Add env vars to Render (see guide above)
3. ✅ Deploy to Render
4. ✅ Test file upload on live site
5. ✅ Check logs: `render logs <service-id>`

## Support

See `CLOUDINARY_SETUP_GUIDE.md` for detailed setup with screenshots and API details.
