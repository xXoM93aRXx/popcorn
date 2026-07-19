/** @odoo-module **/

import { _t } from '@web/core/l10n/translation';

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
        return;
    }

    var phone = ($phoneInput.val() || '').trim();
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
            var response = result && result.result ? result.result : result;
            var success =
                (response && response.success === true) ||
                (response && response.status === 'success') ||
                (response && response.sent === true) ||
                (result && !result.error && result.result);
            var message =
                (response && response.message) ||
                (result && result.error && result.error.message);

            if (success) {
                if ($messageEl.length) {
                    $messageEl.text(message || _t('Verification code sent successfully.'));
                }
                if ($codeInput.length) {
                    $codeInput.focus();
                }
            } else if ($messageEl.length) {
                $messageEl.text(message || _t('Failed to send verification code.')).addClass('text-danger');
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

function onSendPhoneOtp(ev) {
    ev.preventDefault();
    ev.stopPropagation();
    sendPhoneOtp(ev.currentTarget, $(document));
}

function setupOtpButtons() {
    $('#event_send_phone_otp, .popcorn-send-phone-otp').each(function () {
        var $button = $(this);
        if (!$button.data('popcorn-otp-bound')) {
            $button.data('popcorn-otp-bound', true);
            $button.on('click', onSendPhoneOtp);
        }
    });
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
        setTimeout(setupOtpButtons, 100);
    });
} else {
    setTimeout(setupOtpButtons, 100);
}
