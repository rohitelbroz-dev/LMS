/**
 * Cloudinary Direct Upload Handler
 * Enables frontend-to-Cloudinary uploads without going through Python
 * Solves urllib3 SSL recursion issues on Render (Python 3.13)
 */

class CloudinaryUploader {
    constructor() {
        this.config = null;
        this.isReady = false;
    }

    /**
     * Initialize uploader by fetching Cloudinary config from backend
     */
    async init() {
        try {
            const response = await fetch('/api/cloudinary-config');
            if (!response.ok) {
                console.warn('[Cloudinary] Backend config not available, will use Python upload');
                return false;
            }
            this.config = await response.json();
            this.isReady = true;
            console.log('[Cloudinary] Direct upload ready for', this.config.cloud_name);
            return true;
        } catch (error) {
            console.warn('[Cloudinary] Failed to init:', error);
            return false;
        }
    }

    /**
     * Upload file directly to Cloudinary
     * @param {File} file - The file to upload
     * @param {string} folder - Folder path in Cloudinary (default: 'uploads')
     * @returns {Promise<{url: string, public_id: string}|null>}
     */
    async upload(file, folder = 'uploads') {
        if (!this.isReady) {
            console.log('[Cloudinary] Uploader not ready, fallback to server upload');
            return null;
        }

        try {
            // Prepare FormData
            const formData = new FormData();
            formData.append('file', file);
            formData.append('upload_preset', this.config.upload_preset);
            
            // Create public_id (path in Cloudinary)
            const timestamp = new Date().toISOString().replace(/[^0-9]/g, '').slice(0, 14);
            const filename = file.name.replace(/[^a-zA-Z0-9._-]/g, '_');
            const public_id = `${folder}/${timestamp}_${filename}`;
            formData.append('public_id', public_id);
            formData.append('resource_type', 'auto');

            console.log(`[Cloudinary] Uploading ${file.name} to ${public_id}`);

            // Send to Cloudinary
            const response = await fetch(this.config.api_url, {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const error = await response.json();
                console.error('[Cloudinary] Upload failed:', error);
                return null;
            }

            const result = await response.json();
            const url = result.secure_url || result.url;
            
            console.log('[Cloudinary] Upload successful:', url);
            return {
                url: url,
                public_id: result.public_id
            };

        } catch (error) {
            console.error('[Cloudinary] Upload error:', error);
            return null;
        }
    }
}

/**
 * Attach uploader to file input element
 * @param {HTMLInputElement} fileInput - File input element
 * @param {HTMLInputElement} urlInput - Hidden input to store result URL
 * @param {HTMLElement} progressEl - Element to show upload status (optional)
 */
async function attachCloudinaryUpload(fileInput, urlInput, progressEl = null) {
    const uploader = new CloudinaryUploader();
    const ready = await uploader.init();

    if (!ready) {
        console.log('[Cloudinary] Backend upload will be used');
        return;
    }

    fileInput.addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        // Show progress
        if (progressEl) {
            progressEl.textContent = 'Uploading...';
            progressEl.style.display = 'block';
        }

        // Upload to Cloudinary
        const result = await uploader.upload(file);

        if (result) {
            // Store URL in hidden input
            urlInput.value = result.url;
            urlInput.style.display = 'none';  // Hidden field
            
            // Show confirmation
            if (progressEl) {
                progressEl.textContent = '✓ File uploaded to cloud';
                progressEl.style.color = 'green';
                progressEl.style.display = 'block';
            }
            
            console.log('[Cloudinary] URL stored in form:', result.url);
        } else {
            // Fallback to server upload
            if (progressEl) {
                progressEl.textContent = 'Using server upload...';
                progressEl.style.color = 'orange';
            }
            // Remove the hidden URL input so server upload happens normally
            urlInput.value = '';
        }
    });
}

/**
 * Initialize all file inputs on page load
 * Looks for file inputs with data-cloudinary="true" attribute
 */
document.addEventListener('DOMContentLoaded', async () => {
    const fileInputs = document.querySelectorAll('input[type="file"][data-cloudinary="true"]');
    
    for (const fileInput of fileInputs) {
        const form = fileInput.form;
        
        // Create hidden input for URL
        let urlInput = form.querySelector(`input[name="${fileInput.name}_url"]`);
        if (!urlInput) {
            urlInput = document.createElement('input');
            urlInput.type = 'hidden';
            urlInput.name = `${fileInput.name}_url`;
            form.appendChild(urlInput);
        }
        
        // Create progress element
        const progressEl = document.createElement('small');
        progressEl.style.display = 'none';
        progressEl.style.marginLeft = '10px';
        fileInput.parentElement.appendChild(progressEl);
        
        // Attach uploader
        await attachCloudinaryUpload(fileInput, urlInput, progressEl);
    }
});

// Export for manual use
window.CloudinaryUploader = CloudinaryUploader;
window.attachCloudinaryUpload = attachCloudinaryUpload;
