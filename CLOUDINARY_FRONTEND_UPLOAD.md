# Frontend Direct Cloudinary Uploads

## Problem Solved

The Python backend was uploading files to Cloudinary via `requests.post()`, which causes **RecursionError with Python 3.13 on Render** due to urllib3/SSL incompatibilities.

**Solution:** Upload directly from the frontend to Cloudinary's REST API, bypassing Python entirely.

## Architecture

### Previous Flow (Broken on Render)
```
Browser Form Submit
    ↓
Python Backend (app.py)
    ↓
requests.post() → urllib3 → Python 3.13 SSL
    ↓
❌ RecursionError: maximum recursion depth exceeded
```

### New Flow (Works on Render)
```
Browser JavaScript
    ↓
Fetch to Cloudinary REST API (CORS enabled)
    ↓
Get secure_url back
    ↓
Send URL to Flask API endpoint
    ↓
Flask saves URL to database
    ✓ No Python HTTP client, no urllib3, no SSL issues
```

## Implementation

### 1. Frontend: Get Cloudinary Config
```javascript
// Fetch Cloudinary configuration from backend
fetch('/api/cloudinary-config')
  .then(r => r.json())
  .then(config => {
    const cloudinaryUrl = config.api_url;
    const uploadPreset = config.upload_preset;
    // Use in upload form
  });
```

### 2. Frontend: Upload to Cloudinary Directly
```javascript
const uploadToCloudinary = async (file) => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('upload_preset', uploadPreset);
  formData.append('public_id', `uploads/${file.name}`);
  formData.append('resource_type', 'auto');
  
  const response = await fetch(cloudinaryUrl, {
    method: 'POST',
    body: formData
  });
  
  const data = await response.json();
  return data.secure_url;  // Get URL directly from Cloudinary
};
```

### 3. Backend: Accept URL from Frontend
```python
# Instead of receiving file bytes and uploading:
# POST /lead/new with attachment_url in form data
# Flask just saves the URL to database

attachment_path = request.form.get('attachment_url')  # Already from Cloudinary
db.save_lead(..., attachment_path=attachment_path)
```

## Implementation Steps

### Option A: Minimal Change (Recommended)
Keep current form structure, add JavaScript to intercept file input and upload directly:

```html
<input type="file" id="attachment" name="attachment" />
<script>
  document.getElementById('attachment').addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (file) {
      const url = await uploadToCloudinary(file);
      // Create hidden input with the URL
      const urlInput = document.createElement('input');
      urlInput.type = 'hidden';
      urlInput.name = 'cloudinary_url';
      urlInput.value = url;
      e.target.form.appendChild(urlInput);
    }
  });
</script>
```

Then in Flask:
```python
cloudinary_url = request.form.get('cloudinary_url')
if cloudinary_url:
    attachment_path = cloudinary_url
# Save to DB
```

### Option B: Full API Approach
Create dedicated upload endpoint that returns just the URL.

## Advantages

1. **No SSL Conflicts** - No Python urllib3 involved
2. **Faster Uploads** - Browser talks directly to Cloudinary
3. **Better UX** - Frontend can show real-time progress
4. **Less Backend Load** - No file streaming through Python
5. **Same Security** - Uses unsigned preset just like Python version

## Environment Variables (Unchanged)

```
CLOUDINARY_CLOUD_NAME=your-cloud-name
CLOUDINARY_UPLOAD_PRESET=lms-uploads  # Create as unsigned in Cloudinary dashboard
```

## Testing

1. Create a lead with file upload
2. Check browser Network tab - should see POST to `https://api.cloudinary.com/v1_1/{cloud}/auto/upload`
3. Check Flask logs - should NOT see `[STORAGE] Uploading to Cloudinary via REST API`
4. File should save with Cloudinary URL in `leads.attachment_path`

## Migration Path

1. **Phase 1** (Now): Add `/api/cloudinary-config` endpoint ✓
2. **Phase 2** (Next): Add JavaScript to forms for direct upload
3. **Phase 3** (Safe): Remove Python upload code from storage_helper.py or keep as fallback
4. **Phase 4** (Future): Remove urllib3 from requirements.txt

## Fallback

If JavaScript fails, form still submits to Flask normally (old behavior).
Once JavaScript upload succeeds, the hidden URL input is filled.

## Notes

- CORS is enabled by Cloudinary by default for unsigned presets
- Unsigned upload preset doesn't need API credentials - safe for frontend
- URL is immediately available in browser without waiting for backend
- Same database schema - just different source of URL

## Related Files

- [storage_helper.py](storage_helper.py) - Can keep Python fallback
- [CLOUDINARY_SETUP_GUIDE.md](CLOUDINARY_SETUP_GUIDE.md) - Original setup
- [URLLIB3_SSL_FIX.md](URLLIB3_SSL_FIX.md) - The SSL issue explained
