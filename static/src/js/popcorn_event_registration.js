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
