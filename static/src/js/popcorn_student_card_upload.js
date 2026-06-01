/** @odoo-module **/

/**
 * Student card upload handler for the membership checkout page.
 * Only activates when #student_card_file is present in the DOM
 * (i.e. plan.is_student_plan is True on the rendered checkout page).
 */
document.addEventListener('DOMContentLoaded', function () {
    const fileInput   = document.getElementById('student_card_file');
    const hiddenInput = document.getElementById('student_card_attachment_id');
    const statusDiv   = document.getElementById('student-card-status');
    const form        = document.querySelector('.popcorn-membership-checkout-form');

    // Only run on pages that have the student card upload section
    if (!fileInput || !hiddenInput || !statusDiv) return;

    function setStatus(msg, type) {
        statusDiv.style.display = 'block';
        statusDiv.className = 'alert alert-' + (type || 'info');
        statusDiv.textContent = msg;
    }

    fileInput.addEventListener('change', function () {
        const file = fileInput.files[0];
        if (!file) return;

        // Client-side size guard (5 MB)
        if (file.size > 5 * 1024 * 1024) {
            setStatus('File too large. Maximum size is 5 MB.', 'danger');
            fileInput.value = '';
            hiddenInput.value = '';
            return;
        }

        setStatus('Uploading…', 'info');

        const formData = new FormData();
        formData.append('student_card', file);
        // Odoo CSRF token is available on window.odoo.csrf_token
        formData.append('csrf_token', odoo.csrf_token);

        fetch('/memberships/upload_student_card', {
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

    // Block form submission until a student card has been uploaded
    if (form) {
        form.addEventListener('submit', function (e) {
            if (!hiddenInput.value) {
                e.preventDefault();
                setStatus('Please upload your student card before completing the purchase.', 'danger');
                const section = document.getElementById('student-card-section');
                if (section) section.scrollIntoView({ behavior: 'smooth' });
            }
        });
    }
});
