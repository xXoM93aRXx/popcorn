/** @odoo-module **/

/**
 * Student card and ID card upload handler for the membership checkout page.
 * Only activates when #student_card_file is present in the DOM
 * (i.e. plan.is_student_plan is True on the rendered checkout page).
 */

function wireStudentCardUpload() {
    const form = document.querySelector('.popcorn-membership-checkout-form');
    if (!form) return;

    // Resolve CSRF token using the same fallback chain as popcorn_coupon.js
    function getCsrfToken() {
        return (
            document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') ||
            document.querySelector('input[name="csrf_token"]')?.value ||
            (typeof odoo !== 'undefined' && odoo.csrf_token) ||
            ''
        );
    }

    function wireUpload(fileInputId, hiddenInputId, statusDivId, docType) {
        const fileInput   = document.getElementById(fileInputId);
        const hiddenInput = document.getElementById(hiddenInputId);
        const statusDiv   = document.getElementById(statusDivId);
        if (!fileInput || !hiddenInput || !statusDiv) return;

        function setStatus(msg, type) {
            statusDiv.style.display = 'block';
            statusDiv.className = 'alert alert-' + (type || 'info');
            statusDiv.textContent = msg;
        }

        fileInput.addEventListener('change', function () {
            const file = fileInput.files[0];
            if (!file) return;

            if (file.size > 5 * 1024 * 1024) {
                setStatus('File too large. Maximum size is 5 MB.', 'danger');
                fileInput.value = '';
                hiddenInput.value = '';
                return;
            }

            setStatus('Uploading…', 'info');

            const formData = new FormData();
            formData.append(docType, file);
            formData.append('doc_type', docType);
            formData.append('csrf_token', getCsrfToken());

            fetch('/memberships/upload_document', {
                method: 'POST',
                body: formData,
                credentials: 'same-origin',
            })
            .then(function (response) { return response.json(); })
            .then(function (data) {
                if (data.error) {
                    setStatus(data.error, 'danger');
                    hiddenInput.value = '';
                } else {
                    hiddenInput.value = data.attachment_id;
                    setStatus('✓ ' + data.filename + ' uploaded successfully.', 'success');
                }
            })
            .catch(function () {
                setStatus('Upload failed. Please try again.', 'danger');
                hiddenInput.value = '';
            });
        });
    }

    wireUpload('student_card_file', 'student_card_attachment_id', 'student-card-status', 'student_card');
    wireUpload('id_card_file', 'id_card_attachment_id', 'id-card-status', 'id_card');

    // Block form submission until both documents have been uploaded
    form.addEventListener('submit', function (e) {
        const studentCardInput = document.getElementById('student_card_attachment_id');
        const idCardInput      = document.getElementById('id_card_attachment_id');

        // Only validate if student card section is present on this page
        if (!studentCardInput) return;

        if (!studentCardInput.value) {
            e.preventDefault();
            const statusDiv = document.getElementById('student-card-status');
            if (statusDiv) {
                statusDiv.style.display = 'block';
                statusDiv.className = 'alert alert-danger';
                statusDiv.textContent = 'Please upload your student card before completing the purchase.';
            }
            const section = document.getElementById('student-card-section');
            if (section) section.scrollIntoView({ behavior: 'smooth' });
            return;
        }

        if (idCardInput && !idCardInput.value) {
            e.preventDefault();
            const statusDiv = document.getElementById('id-card-status');
            if (statusDiv) {
                statusDiv.style.display = 'block';
                statusDiv.className = 'alert alert-danger';
                statusDiv.textContent = 'Please upload your ID card before completing the purchase.';
            }
            const section = document.getElementById('student-card-section');
            if (section) section.scrollIntoView({ behavior: 'smooth' });
        }
    });
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', wireStudentCardUpload);
} else {
    wireStudentCardUpload();
}
