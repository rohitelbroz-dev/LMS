# Cloudinary Setup Guide for LMS

## Overview

This application now uses **Cloudinary REST API with unsigned uploads** instead of the SDK. This approach:
- Works reliably on restrictive hosting environments like Render
- Uses upload presets instead of storing API credentials
- Matches the pattern used in production Next.js/React projects
- No longer requires cloudinary SDK dependency

## Environment Variables Required

### For Unsigned Uploads (Recommended)
```
STORAGE_BACKEND=cloudinary
CLOUDINARY_CLOUD_NAME=your-cloud-name
CLOUDINARY_UPLOAD_PRESET=your-preset-name
```

### Optional - For File Deletion
If you want to enable file deletion functionality, also set:
```
CLOUDINARY_API_KEY=your-api-key
CLOUDINARY_API_SECRET=your-api-secret
```

> **Note:** If these are not set, file deletion will be silently disabled, but uploads will continue to work.

## Setting Up Upload Preset in Cloudinary

### Step 1: Log in to Cloudinary Dashboard
1. Go to https://cloudinary.com/console
2. Log in to your account

### Step 2: Create an Unsigned Upload Preset
1. Navigate to **Settings** → **Upload**
2. Scroll down to **Upload presets** section
3. Click **Add upload preset** (or **Create** button)
4. Fill in:
   - **Preset Name**: Choose a memorable name (e.g., `lms-uploads`)
   - **Signing Mode**: Select **Unsigned**
   - **Folder**: Leave blank or set to desired folder (e.g., `lms-uploads`)
5. Click **Save**

Your preset name is what you'll use as `CLOUDINARY_UPLOAD_PRESET` in your environment variables.

### Step 3: Get Your Cloud Name
1. From the Cloudinary dashboard, your **Cloud Name** is shown at the top
2. Use this as `CLOUDINARY_CLOUD_NAME`

## Deploying to Render

### 1. Set Environment Variables
In your Render service settings:

```
STORAGE_BACKEND=cloudinary
CLOUDINARY_CLOUD_NAME=your-cloud-name
CLOUDINARY_UPLOAD_PRESET=your-preset-name
```

### 2. No SDK Dependency
The `cloudinary` package has been removed from `requirements.txt`. The application now uses only `requests` library for HTTP calls, which is more reliable on restricted environments.

### 3. Deploy and Test
1. Push your code to GitHub
2. Render will automatically deploy
3. Test by creating a lead with an attachment
4. Monitor logs with: `render logs <service-name>`

## How It Works

### Upload Flow
1. User selects file in form
2. Flask reads file bytes and calls `upload_file()`
3. `_cloudinary_upload()` makes HTTP POST to Cloudinary REST API
4. Sends:
   - File data
   - Upload preset (no auth needed)
   - Public ID (folder/filename)
   - Resource type (image/raw)
5. Cloudinary returns secure URL
6. URL is saved to database

### Code Example
```python
from storage_helper import upload_file

file_data = file.read()  # bytes
result = upload_file(file_data, filename, folder='uploads')

if 'error' in result:
    print(f"Upload failed: {result['error']}")
else:
    image_url = result['url']  # Save this to database
    public_id = result['public_id']  # Optional, for deletion
```

## Troubleshooting

### "CLOUDINARY_UPLOAD_PRESET must be set"
- Verify preset name is correct in Cloudinary dashboard
- Ensure env var is set without extra quotes
- Restart the application after changing env vars

### Upload fails with "HTTP 401"
- Preset may be marked as **Signed** instead of **Unsigned**
- Recreate the preset as **Unsigned**

### Upload fails with "HTTP 400"
- Check that `CLOUDINARY_CLOUD_NAME` is correct
- Verify the preset exists and is spelled correctly
- Check file size isn't exceeding limits

### Files can't be deleted
- This is expected if `CLOUDINARY_API_KEY` and `CLOUDINARY_API_SECRET` aren't set
- Uploads will still work fine
- Only deletion is disabled

## Comparison: Old vs New

### Old Method (SDK)
```python
import cloudinary
import cloudinary.uploader

cloudinary.config(
    cloud_name=name,
    api_key=key,
    api_secret=secret
)
cloudinary.uploader.upload(file_obj)  # Had RecursionError issues on Render
```

**Issues:**
- Required API key/secret on server
- SDK conflicts with urllib3 on Render
- RecursionError fallbacks were unreliable

### New Method (REST API)
```python
files = {'file': (filename, file_data)}
data = {'upload_preset': preset, 'public_id': id}
requests.post(f"https://api.cloudinary.com/v1_1/{cloud}/image/upload", 
             files=files, data=data)
```

**Benefits:**
- No authentication needed (uses unsigned preset)
- Direct HTTP calls are reliable
- Matches proven React/Next.js patterns
- Works on restrictive hosting

## API Response Format

All functions return a dictionary:

**Success:**
```python
{
    'url': 'https://res.cloudinary.com/.../image.jpg',
    'public_id': 'uploads/20240101_120000_image.jpg',
    'resource_type': 'image'  # or 'raw'
}
```

**Error:**
```python
{
    'error': 'cloudinary_upload_failed: HTTP 401',
    'trace': '...'  # optional traceback
}
```

## Security Considerations

### Unsigned Uploads
- **Safe**: Unsigned presets can only upload files to your Cloudinary account
- **Controlled**: You specify allowed file types/sizes in preset settings
- **No credentials**: No API keys exposed to frontend or logs
- Configure preset settings to restrict:
  - File types (only images, PDFs, etc.)
  - File sizes
  - Folder paths

### File Deletion
- Optional API credentials (can be omitted)
- Only used server-side if provided
- Deletion won't work without credentials, but uploads unaffected

## References

- [Cloudinary Unsigned Uploads](https://cloudinary.com/documentation/upload_widget#unsigned_uploads)
- [Cloudinary Upload Presets](https://cloudinary.com/documentation/upload_presets)
- [Cloudinary REST API](https://cloudinary.com/documentation/image_upload_api)
