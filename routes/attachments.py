from flask import Blueprint, redirect, abort, jsonify, current_app, url_for
from urllib.parse import urlparse
from cloudinary import uploader
from cloudinary.utils import cloudinary_url
from flask_login import login_required

# Adjust model import to your project's layout if needed
from lms.models import Lead

bp = Blueprint('attachments', __name__, url_prefix='')

def _extract_cloudinary_public_id(url):
    parsed = urlparse(url)
    path_parts = parsed.path.lstrip('/').split('/')
    try:
        raw_idx = path_parts.index('raw')
        upload_idx = path_parts.index('upload', raw_idx)
    except ValueError:
        return None
    start = upload_idx + 1
    if start < len(path_parts) and path_parts[start].startswith('v'):
        start += 1
    public_with_ext = '/'.join(path_parts[start:])
    public_id = public_with_ext.rsplit('.', 1)[0] if '.' in public_with_ext else public_with_ext
    return public_id

@bp.route('/leads/<int:lead_id>/attachment', methods=['GET', 'HEAD'])
@login_required
def download_attachment(lead_id):
    lead = Lead.query.get_or_404(lead_id)
    if not getattr(lead, 'attachment_url', None):
        abort(404)
    url = lead.attachment_url
    parsed = urlparse(url)
    if 'res.cloudinary.com' in (parsed.netloc or ''):
        public_id = _extract_cloudinary_public_id(url)
        if public_id:
            try:
                public_url, _ = cloudinary_url(public_id, resource_type='raw', type='upload', secure=True, sign_url=False)
                return redirect(public_url)
            except Exception:
                current_app.logger.exception('cloudinary public URL generation failed, falling back to raw URL')
    return redirect(url)

@bp.route('/leads/<int:lead_id>/attachment/make_public', methods=['POST'])
@login_required
def make_public(lead_id):
    lead = Lead.query.get_or_404(lead_id)
    if not getattr(lead, 'attachment_url', None):
        return jsonify(success=False, message='No attachment'), 400
    url = lead.attachment_url
    parsed = urlparse(url)
    if 'res.cloudinary.com' not in (parsed.netloc or ''):
        return jsonify(success=False, message='Not a Cloudinary-hosted file'), 400

    public_id = _extract_cloudinary_public_id(url)
    if not public_id:
        return jsonify(success=False, message='Could not identify Cloudinary public id'), 400

    try:
        # Try to convert the resource to a public "upload" type (non-authenticated).
        uploader.explicit(public_id, resource_type='raw', type='upload')
        public_url, _ = cloudinary_url(public_id, resource_type='raw', type='upload', secure=True, sign_url=False)
        return jsonify(success=True, url=public_url)
    except Exception as e:
        current_app.logger.exception('Failed to make Cloudinary resource public via explicit')
        err_msg = str(e)
        # Try a fallback: attempt to re-upload the original file publicly
        try:
            reupload_resp = uploader.upload(url, resource_type='raw', type='upload')
            if reupload_resp and reupload_resp.get('secure_url'):
                return jsonify(success=True, url=reupload_resp['secure_url'])
        except Exception:
            current_app.logger.exception('Reupload fallback also failed')

        # If cloudinary indicates account untrusted, return 403 with helpful message
        if 'untrusted' in err_msg.lower() or 'show_original_customer_untrusted' in err_msg.lower():
            return jsonify(success=False,
                           message=('Cloudinary blocked delivery for this file because your account '
                                    'is marked as untrusted or restricted. Contact Cloudinary support or update the asset from the Cloudinary console.')), 403

        return jsonify(success=False, message='Failed to make attachment public: ' + err_msg), 500
