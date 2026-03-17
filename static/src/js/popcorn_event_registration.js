odoo.define('@popcorn/js/popcorn_event_registration', ['@web/legacy/js/public/public_widget', '@web/core/l10n/translation'], function (require) {
    'use strict';

    console.log('Popcorn Event Registration JS: Module loaded and running');

    var publicWidget = require('@web/legacy/js/public/public_widget');
    const { _t } = require('@web/core/l10n/translation');

    publicWidget.registry.PopcornEventRegistration = publicWidget.Widget.extend({
        selector: '.popcorn-checkout-form',

        events: {
            'click .popcorn-checkout-submit-btn': '_onSubmitClick',
            'change #use_popcorn_money': '_onPopcornMoneyChange',
            'click #event_send_phone_otp': '_onSendPhoneOtp',
        },

        start: function () {
            console.log('PopcornEventRegistration widget initialized for', this.el);
            // Setup OTP buttons as fallback for any dynamically added buttons
            var self = this;
            setTimeout(function() {
                self._setupOtpButtons();
            }, 100);
            return this._super.apply(this, arguments);
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

            // Block Popcorn Money if a first-timer coupon is active (mutually exclusive)
            if (isChecked && window.firstTimerCouponApplied) {
                $checkbox.prop('checked', false);
                self._showError('Popcorn Money cannot be used together with a first-timer coupon. Please remove the coupon first.');
                return;
            }
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
        },

        _onSendPhoneOtp: function (ev) {
            ev.preventDefault();
            ev.stopPropagation();
            console.log('PopcornEventRegistration: send OTP button handler triggered');
            sendPhoneOtp(ev.currentTarget, this.$el);
        },

        _setupOtpButtons: function () {
            // Fallback setup for any OTP buttons that might be added dynamically
            var self = this;
            var $button = this.$el.find('#event_send_phone_otp');
            console.log('PopcornEventRegistration: Looking for #event_send_phone_otp, found:', $button.length > 0 ? 'YES' : 'NO', $button.length);
            if ($button.length && !$button.data('popcorn-otp-bound')) {
                $button.data('popcorn-otp-bound', true);
                console.log('PopcornEventRegistration: OTP button marked as bound');
                // Widget events should handle this, but this is a safety net
            }
        }
    });

    function sendPhoneOtp(buttonElement, $scope) {
        var $button = $(buttonElement);
        var $form = $button.closest('form');
        var $context = $scope || $(document);

        var phoneSelector = $button.data('phoneInput') || '#phone';
        var messageSelector = $button.data('messageTarget') || '#event_phone_otp_message';
        var codeSelector = $button.data('codeTarget') || '#phone_verification_code';

        var $phoneInput = $form.find(phoneSelector);
        if (!$phoneInput.length) {
            $phoneInput = $context.find(phoneSelector);
        }

        var $messageEl = $form.find(messageSelector);
        if (!$messageEl.length) {
            $messageEl = $context.find(messageSelector);
        }

        var $codeInput = $form.find(codeSelector);
        if (!$codeInput.length) {
            $codeInput = $context.find(codeSelector);
        }

        if (!$phoneInput.length) {
            console.log('Phone OTP: phone input not found for selector', phoneSelector);
            return;
        }

        var phone = ($phoneInput.val() || '').trim();
        console.log('Phone OTP button clicked, selector:', phoneSelector, 'value:', phone);

        if (!phone) {
            if ($messageEl.length) {
                $messageEl.text(_t('Please enter your phone number before requesting a code.')).addClass('text-danger');
            }
            return;
        }

        $button.prop('disabled', true);
        if ($messageEl.length) {
            $messageEl.text('').removeClass('text-danger');
        }

        var payload = JSON.stringify({ phone_number: phone });

        $.ajax({
            url: '/web/sms/send',
            type: 'POST',
            contentType: 'application/json',
            dataType: 'json',
            data: payload,
            success: function (result) {
                if (result && result.success) {
                    if ($messageEl.length) {
                        $messageEl.text(result.message || _t('Verification code sent successfully.'));
                    }
                    if ($codeInput.length) {
                        $codeInput.focus();
                    }
                } else if ($messageEl.length) {
                    $messageEl.text((result && result.message) || _t('Failed to send verification code.')).addClass('text-danger');
                }
            },
            error: function (xhr) {
                if ($messageEl.length) {
                    var message = _t('Failed to send verification code.');
                    if (xhr.responseJSON && xhr.responseJSON.message) {
                        message = xhr.responseJSON.message;
                    }
                    $messageEl.text(message).addClass('text-danger');
                }
            },
            complete: function () {
                $button.prop('disabled', false);
            },
        });
    }


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

// Handle registration form button loading state
function setupRegistrationForm() {
    var form = document.getElementById('event-registration-form');
    var button = document.getElementById('register-club-btn');
    
    if (form && button) {
        form.addEventListener('submit', function(e) {
            // Disable button to prevent double submission
            button.disabled = true;
            button.classList.add('disabled');
            
            // Hide original text, show loading text
            var btnText = button.querySelector('.btn-text');
            var btnLoading = button.querySelector('.btn-loading');
            if (btnText) btnText.style.display = 'none';
            if (btnLoading) btnLoading.style.display = 'inline';
        });
    }
}

// Initialize registration form handler
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupRegistrationForm);
} else {
    setupRegistrationForm();
}