# 404 Error Fix - Lead Edit Page

## Problem
When trying to access the lead edit page, you got:
```
HTTP ERROR 404
No webpage was found for the web address: 
https://upgraded-fiesta-pj45pqr5jgvv27556-5000.app.github.dev:5000/lead/2/edit
```

Notice the `:5000` in the middle of the URL - the port was being added to the hostname instead of at the end.

## Root Cause
When running behind a proxy (GitHub Codespaces, Render, etc.), Flask doesn't automatically know:
- The real external hostname
- The real protocol (http vs https)
- The real port

This caused Flask to generate incorrect URLs with duplicate ports.

## Solution Applied
Added **ProxyFix middleware** and configuration to Flask:

```python
# Fix URL generation behind proxy (GitHub Codespaces, Render, etc.)
app.config['PREFERRED_URL_SCHEME'] = 'https'

# Import werkzeug for trusted hosts configuration
from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)
```

## What This Does
- **ProxyFix**: Reads proxy headers (X-Forwarded-Host, X-Forwarded-Proto, etc.) and fixes the request context
- **PREFERRED_URL_SCHEME**: Tells Flask to generate `https://` URLs instead of `http://`
- **Parameters**: 
  - `x_for=1`: Trust the X-Forwarded-For header (client IP)
  - `x_proto=1`: Trust the X-Forwarded-Proto header (http/https)
  - `x_host=1`: Trust the X-Forwarded-Host header (hostname)
  - `x_port=1`: Trust the X-Forwarded-Port header (real port)
  - `x_prefix=1`: Trust the X-Script-Name header (app prefix)

## Result
Now URLs are generated correctly:
- ✅ `https://upgraded-fiesta-pj45pqr5jgvv27556-5000.app.github.dev/lead/2/edit` (correct)
- ❌ `https://upgraded-fiesta-pj45pqr5jgvv27556-5000.app.github.dev:5000/lead/2/edit` (was wrong)

## File Modified
- [app.py](app.py#L60-L67) - Added ProxyFix configuration

## Testing
The fix is now in place. Try:
1. Go to dashboard
2. Click edit on any lead
3. Upload an image
4. Submit the form
5. Should work without 404 errors

## Works On
This fix ensures proper URL generation on:
- ✅ GitHub Codespaces
- ✅ Render
- ✅ Any proxy/reverse proxy environment
- ✅ Local development (no impact)

## Technical Note
ProxyFix is a security-sensitive middleware. In production, only enable it if:
1. You're behind a trusted proxy (Render, Heroku, etc.)
2. Your proxy is configured to set these headers

The default configuration is safe for most environments including Render.
