odoo.define('@popcorn/js/popcorn_event_registration', ['@web/legacy/js/public/public_widget'], function (require) {
    'use strict';

    var publicWidget = require('@web/legacy/js/public/public_widget');

    publicWidget.registry.PopcornEventRegistration = publicWidget.Widget.extend({
        selector: '.o_wevent_registration_form',
        
        events: {
            'click .o_wevent_registration_submit': '_onSubmitClick',
        },

        _onSubmitClick: function (ev) {
            var self = this;
            var $form = this.$el.find('form');
            var $submitBtn = this.$el.find('.o_wevent_registration_submit');
            
            // Disable submit button to prevent double submission
            $submitBtn.prop('disabled', true);
            
            // Get form data
            var formData = new FormData($form[0]);
            
            // Make AJAX request to registration endpoint
            $.ajax({
                url: $form.attr('action'),
                type: 'POST',
                data: formData,
                processData: false,
                contentType: false,
                success: function (response) {
                    if (response.redirect) {
                        // Redirect to specified URL
                        window.location.href = response.redirect;
                    } else if (response.error) {
                        // Show error message
                        self._showError(response.error);
                        $submitBtn.prop('disabled', false);
                    } else {
                        // Success - redirect to event page
                        window.location.reload();
                    }
                },
                error: function (xhr, status, error) {
                    // Handle error
                    self._showError('An error occurred during registration. Please try again.');
                    $submitBtn.prop('disabled', false);
                }
            });
        },

        _showError: function (message) {
            // Remove existing error messages
            this.$el.find('.alert-danger').remove();
            
            // Create and show error message
            var $errorDiv = $('<div class="alert alert-danger alert-dismissible fade show" role="alert">' +
                '<i class="fa fa-exclamation-circle"></i> ' + message +
                '<button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>' +
                '</div>');
            
            this.$el.prepend($errorDiv);
            
            // Auto-hide after 5 seconds
            setTimeout(function() {
                $errorDiv.fadeOut();
            }, 5000);
        }
    });

    return publicWidget.registry.PopcornEventRegistration;
});

// Global function for confirming cancellation of conflicting registration
window.confirmCancelConflictingRegistration = function(button) {
    var eventId = $(button).data('conflicting-event-id');
    var eventName = $(button).text().replace('Cancel Registration: ', '').trim();
    
    // Show custom confirmation popup
    showConfirmationPopup(eventName, function(confirmed) {
        if (confirmed) {
            // Make AJAX request to cancel registration
            $.ajax({
                url: '/my/clubs/cancel-conflicting',
                type: 'POST',
                data: {
                    'event_id': eventId,
                    'csrf_token': odoo.csrf_token
                },
                success: function(response) {
                    if (response.success) {
                        // Show success message and reload page after a short delay
                        showSuccessPopup('Registration cancelled successfully!');
                        setTimeout(function() {
                            window.location.reload();
                        }, 2000); // Wait 2 seconds to show the popup
                    } else {
                        showErrorPopup('Error cancelling registration: ' + (response.message || 'Unknown error'));
                    }
                },
                error: function(xhr, status, error) {
                    showErrorPopup('Error cancelling registration. Please try again.');
                }
            });
        }
    });
};

// Popup functions using XML templates - following membership freeze pattern
function setupPopupFunctionality() {
    // Check if popup elements exist
    const confirmationPopup = document.getElementById('popcorn_confirmation_popup');
    const successPopup = document.getElementById('popcorn_success_popup');
    const errorPopup = document.getElementById('popcorn_error_popup');
    
    if (!confirmationPopup || !successPopup || !errorPopup) {
        return;
    }
}

function showConfirmationPopup(eventName, callback) {
    // Hide any existing modals
    $('.modal').modal('hide');
    
    // Store callback globally for template buttons to access
    window.confirmationCallback = callback;
    
    // Update the event name in the template
    const eventNameElement = document.getElementById('confirmation-event-name');
    if (eventNameElement) {
        eventNameElement.textContent = '"' + eventName + '"';
    }
    
    // Show the confirmation popup modal using Bootstrap
    const confirmationPopup = document.getElementById('popcorn_confirmation_popup');
    if (confirmationPopup) {
        $(confirmationPopup).modal('show');
    }
}

// Global function for hiding confirmation popup
window.hideConfirmationPopup = function(confirmed) {
    const confirmationPopup = document.getElementById('popcorn_confirmation_popup');
    if (confirmationPopup) {
        $(confirmationPopup).modal('hide');
    }
    
    if (window.confirmationCallback) {
        window.confirmationCallback(confirmed);
        window.confirmationCallback = null;
    }
}

function showSuccessPopup(message) {
    // Hide any existing modals
    $('.modal').modal('hide');
    
    // Update the message in the template
    const messageElement = document.getElementById('success-message');
    if (messageElement) {
        messageElement.textContent = message;
    }
    
    // Show the success popup modal using Bootstrap
    const successPopup = document.getElementById('popcorn_success_popup');
    if (successPopup) {
        $(successPopup).modal('show');
        
        // Auto-hide after 2 seconds
        setTimeout(function() {
            $(successPopup).modal('hide');
        }, 2000);
    }
}

function showErrorPopup(message) {
    // Hide any existing modals
    $('.modal').modal('hide');
    
    // Update the message in the template
    const messageElement = document.getElementById('error-message');
    if (messageElement) {
        messageElement.textContent = message;
    }
    
    // Show the error popup modal using Bootstrap
    const errorPopup = document.getElementById('popcorn_error_popup');
    if (errorPopup) {
        $(errorPopup).modal('show');
        
        // Auto-hide after 2 seconds
        setTimeout(function() {
            $(errorPopup).modal('hide');
        }, 2000);
    }
}

// Initialize when DOM is ready - following membership freeze pattern
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupPopupFunctionality);
} else {
    setupPopupFunctionality();
}

// Also initialize when page loads dynamically (for SPA-like behavior)
document.addEventListener('DOMContentLoaded', function() {
    // Small delay to ensure all elements are loaded, especially for dynamic content
    setTimeout(setupPopupFunctionality, 100);
});

// Additional initialization for dynamic content loading
window.addEventListener('load', function() {
    setTimeout(setupPopupFunctionality, 200);
});