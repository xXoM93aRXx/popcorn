/** @odoo-module **/

console.log('📱 Popcorn Phone OTP helper loaded');

function setupPhoneOtpButtons() {
    const buttons = document.querySelectorAll('.popcorn-phone-otp-btn');

    if (!buttons.length) {
        console.log('📱 Phone OTP: no buttons found, skipping setup');
        return;
    }

    console.log('📱 Phone OTP: setting up', buttons.length, 'button(s)');

    buttons.forEach((button) => {
        if (button.dataset.popcornOtpBound) {
            return;
        }
        button.dataset.popcornOtpBound = '1';

        button.addEventListener('click', (event) => {
            event.preventDefault();

            const scope = button.closest('form') || document;
            const phoneSelector = button.getAttribute('data-phone-input') || '#phone';
            const messageSelector = button.getAttribute('data-message-target') || '#event_phone_otp_message';
            const codeSelector = button.getAttribute('data-code-target') || '#phone_verification_code';

            const phoneInput = scope.querySelector(phoneSelector) || document.querySelector(phoneSelector);
            const messageEl = scope.querySelector(messageSelector) || document.querySelector(messageSelector);
            const codeInput = scope.querySelector(codeSelector) || document.querySelector(codeSelector);

            if (!phoneInput) {
                console.log('📱 Phone OTP: phone input not found for selector', phoneSelector);
                return;
            }

            const phone = (phoneInput.value || '').trim();
            console.log('📱 Phone OTP button clicked.', { selector: phoneSelector, phone });

            if (!phone) {
                if (messageEl) {
                    messageEl.textContent = 'Please enter your phone number before requesting a code.';
                    messageEl.classList.add('text-danger');
                }
                return;
            }

            button.disabled = true;
            if (messageEl) {
                messageEl.textContent = '';
                messageEl.classList.remove('text-danger');
            }

            fetch('/web/sms/send', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ phone_number: phone }),
            })
                .then((response) => response.json())
                .then((result) => {
                    const payload = result && result.result ? result.result : result;

                    if (payload && payload.success) {
                        console.log('📱 Phone OTP success:', payload.message);
                        if (messageEl) {
                            messageEl.textContent = payload.message || 'Verification code sent successfully.';
                        }
                        if (codeInput) {
                            codeInput.focus();
                        }

                        startOtpCooldown(button, messageEl);
                    } else if (messageEl) {
                        const errorMessage = (payload && payload.message) || 'Failed to send verification code.';
                        console.warn('📱 Phone OTP failed:', errorMessage);
                        messageEl.textContent = errorMessage;
                        messageEl.classList.add('text-danger');
                    }
                })
                .catch((error) => {
                    console.error('📱 Phone OTP error:', error);
                    if (messageEl) {
                        messageEl.textContent = 'Failed to send verification code.';
                        messageEl.classList.add('text-danger');
                    }
                })
                .finally(() => {
                    if (!button.dataset.popcornOtpTimerId) {
                        button.disabled = false;
                    }
                });
        });
    });
}

function startOtpCooldown(button, messageEl) {
    const originalHtml = button.dataset.popcornOtpOriginal || button.innerHTML;
    button.dataset.popcornOtpOriginal = originalHtml;

    if (button.dataset.popcornOtpTimerId) {
        clearInterval(Number(button.dataset.popcornOtpTimerId));
    }

    let remaining = 60;
    button.disabled = true;
    updateButtonLabel(button, remaining);

    if (messageEl) {
        messageEl.classList.remove('text-danger');
        messageEl.textContent = `You can request a new code in ${remaining} seconds.`;
    }

    const intervalId = setInterval(() => {
        remaining -= 1;
        if (remaining <= 0) {
            clearInterval(intervalId);
            delete button.dataset.popcornOtpTimerId;
            button.innerHTML = button.dataset.popcornOtpOriginal;
            button.disabled = false;
            if (messageEl && messageEl.textContent.includes('You can request a new code')) {
                messageEl.textContent = '';
            }
            return;
        }

        updateButtonLabel(button, remaining);
        if (messageEl) {
            messageEl.textContent = `You can request a new code in ${remaining} seconds.`;
        }
    }, 1000);

    button.dataset.popcornOtpTimerId = String(intervalId);
}

function updateButtonLabel(button, remaining) {
    button.innerHTML = `${button.dataset.popcornOtpOriginal} (${remaining}s)`;
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupPhoneOtpButtons);
} else {
    setupPhoneOtpButtons();
}

window.addEventListener('load', () => {
    setTimeout(setupPhoneOtpButtons, 200);
});
