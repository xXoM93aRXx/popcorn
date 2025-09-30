odoo.define('@popcorn/js/popcorn_event_registration', ['@web/legacy/js/public/public_widget'], function (require) {
    'use strict';

    var publicWidget = require('@web/legacy/js/public/public_widget');

    publicWidget.registry.PopcornEventRegistration = publicWidget.Widget.extend({
        selector: '.popcorn-checkout-form',
        
        events: {
            'click .popcorn-checkout-submit-btn': '_onSubmitClick',
            'change #use_popcorn_money': '_onPopcornMoneyChange',
        },

        _onSubmitClick: function (ev) {
            var self = this;
            var $form = this.$el.find('form');
            var $submitBtn = this.$el.find('.popcorn-checkout-submit-btn');
            
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
        },

        _onPopcornMoneyChange: function (ev) {
            var self = this;
            var $checkbox = $(ev.currentTarget);
            var isChecked = $checkbox.is(':checked');
            var $popcornMoneyRow = $('#popcorn-money-row');
            var $popcornMoneyUsed = $('#popcorn-money-used');
            var $totalPrice = $('#popcorn-total-price');
            
            console.log('Popcorn Money checkbox changed:', isChecked);
            console.log('Elements found:', {
                popcornMoneyRow: $popcornMoneyRow.length,
                popcornMoneyUsed: $popcornMoneyUsed.length,
                totalPrice: $totalPrice.length
            });
            
            // Store original price if not already stored
            if (!self.originalPrice) {
                // Get the original event price from the registration fee row
                var $registrationFeeRow = $('.popcorn-price-row').first();
                var originalPriceText = $registrationFeeRow.find('.popcorn-price-value').text();
                var originalPrice = parseFloat(originalPriceText.replace(/[^\d.-]/g, ''));
                
                // Fallback: if no price found in first row, look for "Registration Fee" row
                if (!originalPriceText || originalPrice === 0) {
                    $('.popcorn-price-row').each(function() {
                        var $label = $(this).find('.popcorn-price-label');
                        if ($label.text().includes('Registration Fee')) {
                            originalPriceText = $(this).find('.popcorn-price-value').text();
                            originalPrice = parseFloat(originalPriceText.replace(/[^\d.-]/g, ''));
                            return false; // break the loop
                        }
                    });
                }
                
                self.originalPrice = originalPrice;
                self.originalPriceText = originalPriceText;
                console.log('Stored original price:', originalPriceText, 'Parsed:', originalPrice);
            }
            
            var originalPrice = self.originalPrice;
            var originalPriceText = self.originalPriceText;
            console.log('Using stored original price:', originalPriceText, 'Parsed:', originalPrice);
            
            // Get popcorn money balance from the checkbox label
            var $label = $('label[for="use_popcorn_money"]');
            var balanceText = $label.find('.popcorn-money-balance').text();
            var balance = balanceText ? parseFloat(balanceText.match(/[\d.-]+/)[0]) : 0;
            
            console.log('Balance text:', balanceText, 'Parsed:', balance);
            
            if (isChecked) {
                // Show popcorn money row
                $popcornMoneyRow.show();
                
                // Calculate how much popcorn money to use (minimum of balance and price)
                var popcornMoneyToUse = Math.min(balance, originalPrice);
                var remainingPrice = originalPrice - popcornMoneyToUse;
                
                console.log('Calculations:', {
                    popcornMoneyToUse: popcornMoneyToUse,
                    remainingPrice: remainingPrice
                });
                
                // Update popcorn money used display
                var currencySymbol = originalPriceText.match(/[^\d.-]/)[0] || '$';
                $popcornMoneyUsed.text('-' + currencySymbol + popcornMoneyToUse.toFixed(2));
                
                // Update total price
                $totalPrice.text(currencySymbol + remainingPrice.toFixed(2));
                
                console.log('Updated total price to:', currencySymbol + remainingPrice.toFixed(2));
                
                // If popcorn money covers the full amount, hide payment methods
                if (remainingPrice <= 0) {
                    $('.popcorn-payment-methods').hide();
                    $('.popcorn-form-label').text('Payment Method (Not Required)');
                    // Remove required attribute from payment method inputs
                    $('.popcorn-payment-methods input[type="radio"]').removeAttr('required');
                } else {
                    $('.popcorn-payment-methods').show();
                    $('.popcorn-form-label').text('Select Payment Method *');
                    // Add required attribute back to payment method inputs
                    $('.popcorn-payment-methods input[type="radio"]').attr('required', 'required');
                }
            } else {
                // Hide popcorn money row
                $popcornMoneyRow.hide();
                
                // Reset total price to original
                $totalPrice.text(originalPriceText);
                
                console.log('Reset total price to:', originalPriceText);
                
                // Show payment methods
                $('.popcorn-payment-methods').show();
                $('.popcorn-form-label').text('Select Payment Method *');
                // Add required attribute back to payment method inputs
                $('.popcorn-payment-methods input[type="radio"]').attr('required', 'required');
            }
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