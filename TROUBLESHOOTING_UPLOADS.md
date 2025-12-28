# Quick Troubleshooting Guide

## Issue: "Still Getting RecursionError"

This should **not** happen with the new code. If it does:

1. **Verify the code is deployed:**
   ```bash
   # Check if cloudinary-upload.js exists
   ls -la /opt/render/project/src/static/js/cloudinary-upload.js
   
   # Check if API endpoint exists
   curl https://your-app.onrender.com/api/cloudinary-config
   # Should return: {"cloud_name":"...", "upload_preset":"..."}
   ```

2. **Check browser console:**
   - Open DevTools (F12) → Console
   - Try uploading file
   - Should see: `[Cloudinary] Direct upload ready for {your-cloud-name}`
   - If not, something with JavaScript failed

3. **Check Network tab:**
   - Open DevTools (F12) → Network
   - Select file
   - Should see POST to `https://api.cloudinary.com/v1_1/...`
   - If you see POST to `/lead/new`, JavaScript failed (using fallback)

---

## Issue: "Upload Button Doesn't Do Anything"

1. **Check if JavaScript loaded:**
   ```javascript
   // Open browser console and run:
   typeof CloudinaryUploader
   // Should print: "function"
   // If "undefined", the script didn't load
   ```

2. **Check script tag in template:**
   ```html
   <!-- Should be present at bottom of lead_form.html and lead_edit.html -->
   <script src="{{ url_for('static', filename='js/cloudinary-upload.js') }}"></script>
   ```

3. **Check if endpoint is working:**
   ```javascript
   // In browser console:
   fetch('/api/cloudinary-config').then(r => r.json()).then(console.log)
   // Should show cloud_name, upload_preset, api_url
   ```

---

## Issue: "File Uploaded but URL Not Saved"

1. **Check form has attachment_url field:**
   ```html
   <!-- Should appear in browser DevTools → Elements -->
   <input type="hidden" name="attachment_url" value="https://...">
   ```

2. **Check Flask is receiving the URL:**
   - Look at Render logs for: `[STORAGE] Using frontend-uploaded Cloudinary URL:`
   - If not there, attachment_url wasn't sent

3. **Check database:**
   ```sql
   SELECT attachment_path FROM leads WHERE id = (
     SELECT MAX(id) FROM leads
   );
   -- Should show Cloudinary URL like: https://res.cloudinary.com/...
   ```

---

## Issue: "Upload Works Locally But Not on Render"

1. **Check environment variables on Render:**
   - Dashboard → Service → Environment
   - Verify: CLOUDINARY_CLOUD_NAME is set
   - Verify: CLOUDINARY_UPLOAD_PRESET is set
   - Verify: STORAGE_BACKEND = cloudinary

2. **Check CORS:**
   - Cloudinary CORS should be enabled by default for unsigned presets
   - In browser Network tab, check response headers:
     ```
     Access-Control-Allow-Origin: *
     ```

3. **Check Python version:**
   ```bash
   # In Render deploy logs, look for:
   # "python/Python-3.13.x"
   # If it's 3.12 or lower, that's fine (issue only on 3.13)
   ```

---

## Issue: "CORS Error When Uploading"

If you see in browser console:
```
Access to XMLHttpRequest blocked by CORS policy
```

1. **Verify unsigned preset:**
   - Cloudinary Dashboard → Settings → Upload
   - Find your `lms-uploads` preset
   - Check: "Unsigned" is enabled

2. **Verify cloud name:**
   - Ensure CLOUDINARY_CLOUD_NAME matches exactly
   - Check for typos or extra spaces

3. **Verify API URL:**
   - Should be: `https://api.cloudinary.com/v1_1/{cloud_name}/auto/upload`
   - Not: `image/upload` or `raw/upload` (should be `auto/upload`)

---

## Issue: "RecursionError in Flask Logs"

If you still see RecursionError in Render logs:

1. **Check what triggered it:**
   ```
   [STORAGE] Uploading to Cloudinary via REST API:
   [STORAGE] Cloudinary upload failed: maximum recursion depth exceeded
   ```
   
   This means **Python fallback was triggered**. Why?
   - JavaScript failed to upload
   - File was submitted without cloudinary_url
   - Flask fell back to Python requests → urllib3 → error

2. **Fix JavaScript:**
   - Check browser console for errors
   - Verify API endpoint returns valid JSON
   - Verify Cloudinary config env vars are set

3. **Or disable fallback:**
   - Edit `new_lead()` and `edit_lead()` in app.py
   - Remove the fallback upload logic
   - Only accept attachment_url from frontend
   - This forces everyone to use JavaScript

---

## Success Indicators

✅ **You'll know it's working when:**

1. Browser Console shows:
   ```
   [Cloudinary] Direct upload ready for {your-cloud-name}
   [Cloudinary] Uploading ...
   [Cloudinary] Upload successful: https://res.cloudinary.com/...
   ```

2. Network tab shows:
   - POST to `https://api.cloudinary.com/v1_1/...` → 200 OK
   - Response: `{secure_url: "...", public_id: "...", ...}`

3. Flask logs show:
   ```
   [STORAGE] Using frontend-uploaded Cloudinary URL: https://res.cloudinary.com/...
   ```
   (NOT "Uploading to Cloudinary via REST API")

4. Database has:
   ```
   leads.attachment_path = "https://res.cloudinary.com/..."
   ```

5. **No RecursionError anywhere**

---

## Debugging Checklist

When something doesn't work:

- [ ] Render logs show successful deploy (no build errors)
- [ ] Browser Network tab shows POST to `api.cloudinary.com`
- [ ] Cloudinary response is 200 OK with `secure_url`
- [ ] Browser console shows `[Cloudinary] Upload successful`
- [ ] Hidden form field `attachment_url` is populated
- [ ] Flask logs show `Using frontend-uploaded Cloudinary URL`
- [ ] Database has Cloudinary HTTPS URL in `attachment_path`
- [ ] No Python error logs about urllib3 or SSL

---

## Contact Support

If still broken after checking everything above:

1. Collect these details:
   - Browser console output (Ctrl+Shift+K)
   - Network tab HAR file (right-click → Save as HAR)
   - Render deploy logs (last 50 lines)
   - Flask application logs
   - Cloudinary upload preset settings

2. Check in this order:
   - Is JavaScript enabled? (Ctrl+Shift+K)
   - Is /api/cloudinary-config accessible?
   - Does Cloudinary respond to POST from your domain?
   - Are environment variables correct?

3. Last resort:
   - Disable JavaScript uploader and use Python fallback
   - Downgrade to Python 3.12 on Render (may take time)
   - Contact Cloudinary support about CORS issues
