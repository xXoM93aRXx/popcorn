// Popcorn Registration Cancellation - Vanilla JavaScript
(function() {
    'use strict';

    // Get CSRF token using the same method as freeze.js
    function getCsrfToken() {
        // Try multiple sources for CSRF token
        var csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || 
                       document.querySelector('input[name="csrf_token"]')?.value || '';
        
        // Debug: log if token is found
        if (!csrfToken) {
            console.warn('CSRF token not found in meta tag or input field');
        }
        
        return csrfToken;
    }

    // Handle cancellation button clicks
    function handleCancelClick(event) {
        event.preventDefault();
        
        var button = event.currentTarget;
        var registrationId = button.getAttribute('data-registration-id');
        var eventName = button.getAttribute('data-event-name');
        
        // Store button reference for later use
        window.currentCancelButton = button;
        window.currentRegistrationId = registrationId;
        
        // Update modal content
        document.getElementById('cancelEventName').textContent = eventName;
        
        // Reset form
        document.getElementById('cancelForm').reset();
        document.getElementById('confirmCancelBtn').disabled = true;
        
        // Show modal
        showCancelModal();
    }

    // Show cancel modal
    function showCancelModal() {
        const modal = document.getElementById('cancelModal');
        if (modal) {
            try {
                // Use Bootstrap modal show method
                const bootstrapModal = new bootstrap.Modal(modal);
                bootstrapModal.show();
            } catch (e) {
                // Fallback: try to show modal manually
                modal.style.display = 'block';
                modal.classList.add('show');
                document.body.classList.add('modal-open');
            }
        }
    }

    // Hide cancel modal
    function hideCancelModal() {
        const modal = document.getElementById('cancelModal');
        if (modal) {
            try {
                // Use Bootstrap modal hide method
                const bootstrapModal = bootstrap.Modal.getInstance(modal);
                if (bootstrapModal) {
                    bootstrapModal.hide();
                }
            } catch (e) {
                // Fallback: try to hide modal manually
                modal.style.display = 'none';
                modal.classList.remove('show');
                document.body.classList.remove('modal-open');
            }
        }
    }

    // Handle alert dismissal
    function handleAlertDismiss(event) {
        var alert = event.target.closest('.alert');
        if (alert) {
            alert.style.transition = 'opacity 0.5s ease-out';
            alert.style.opacity = '0';
            setTimeout(function() {
                if (alert.parentNode) {
                    alert.parentNode.removeChild(alert);
                }
            }, 500);
        }
    }

    // Auto-hide alerts after 5 seconds
    function autoHideAlerts() {
        setTimeout(function() {
            var alerts = document.querySelectorAll('.alert');
            alerts.forEach(function(alert) {
                if (alert.style) {
                    alert.style.transition = 'opacity 0.5s ease-out';
                    alert.style.opacity = '0';
                    setTimeout(function() {
                        if (alert.parentNode) {
                            alert.parentNode.removeChild(alert);
                        }
                    }, 500);
                }
            });
        }, 5000);
    }

    // Initialize when DOM is ready
    function init() {
        // Add event listeners to cancel buttons
        var cancelButtons = document.querySelectorAll('.btn-cancel-registration');
        cancelButtons.forEach(function(button) {
            button.addEventListener('click', handleCancelClick);
        });

        // Add event listeners to alert close buttons
        var closeButtons = document.querySelectorAll('.btn-close');
        closeButtons.forEach(function(button) {
            button.addEventListener('click', handleAlertDismiss);
        });

        // Setup cancel modal functionality
        setupCancelModal();

        // Auto-hide alerts
        autoHideAlerts();
    }

    // Setup cancel modal functionality
    function setupCancelModal() {
        const cancelForm = document.getElementById('cancelForm');
        const confirmCheckbox = document.getElementById('confirmCancel');
        const confirmBtn = document.getElementById('confirmCancelBtn');
        const modal = document.getElementById('cancelModal');

        if (cancelForm && confirmCheckbox && confirmBtn && modal) {
            // Handle checkbox change
            confirmCheckbox.addEventListener('change', function() {
                confirmBtn.disabled = !this.checked;
            });

            // Handle form submission
            cancelForm.addEventListener('submit', function(evt) {
                evt.preventDefault();
                
                if (!confirmCheckbox.checked) {
                    return;
                }

                // Disable button to prevent double-click
                var button = window.currentCancelButton;
                var registrationId = window.currentRegistrationId;
                
                if (button && registrationId) {
                    button.disabled = true;
                    button.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Cancelling...';
                }

                // Update form action
                cancelForm.action = '/my/clubs/' + registrationId + '/cancel';
                
                // Ensure CSRF token is present
                let csrfToken = cancelForm.querySelector('input[name="csrf_token"]').value;
                
                if (!csrfToken) {
                    // Try to get CSRF token from page
                    csrfToken = getCsrfToken();
                    
                    if (csrfToken) {
                        // Add CSRF token to form
                        const csrfInput = document.createElement('input');
                        csrfInput.type = 'hidden';
                        csrfInput.name = 'csrf_token';
                        csrfInput.value = csrfToken;
                        cancelForm.appendChild(csrfInput);
                    } else {
                        console.error('No CSRF token available');
                        // Re-enable button and show error
                        if (button) {
                            button.disabled = false;
                            button.innerHTML = '<i class="fa fa-times"></i> Cancel';
                        }
                        alert('Security token not found. Please refresh the page and try again.');
                        hideCancelModal();
                        return;
                    }
                }
                
                // Submit form
                console.log('Submitting cancel form to:', cancelForm.action);
                cancelForm.submit();
            });

            // Setup modal close buttons
            const closeButtons = modal.querySelectorAll('.btn-close, .btn-secondary');
            closeButtons.forEach(btn => {
                btn.addEventListener('click', hideCancelModal);
            });
            
            // Close modal when clicking outside
            modal.addEventListener('click', function(evt) {
                if (evt.target === modal) {
                    hideCancelModal();
                }
            });
        }
    }

    // Initialize when DOM is loaded
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
