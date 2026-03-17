/** @odoo-module **/

/**
 * Frontend helper for Popcorn coupon/discount functionality.
 *
 * Responsibilities:
 *  - Handle coupon code validation and application on checkout pages.
 *  - Update pricing display when discounts are applied or removed.
 *  - Support first-timer discount auto-application.
 *  - Manage UI state for coupon input, apply, and remove buttons.
 *
 * Notes:
 *  - The asset is declared in the module manifest under web.assets_frontend.
 */

function wireCouponPage() {
    const couponInput = document.getElementById('coupon_code');
    const applyBtn = document.getElementById('apply_coupon_btn');
    const removeBtn = document.getElementById('remove_coupon_btn');
    
    // Save original price on page load
    const totalPriceElement = document.getElementById('popcorn-total-price');
    if (totalPriceElement && !window.popcornOriginalPrice) {
        window.popcornOriginalPrice = totalPriceElement.textContent;
    }
    
    if (!couponInput || !applyBtn) {
        return;
    }
    
    // Handle apply coupon button click
    applyBtn.addEventListener('click', function(evt) {
        evt.preventDefault();
        
        const couponCode = couponInput.value.trim();
        if (!couponCode) {
            showMessage('Please enter a coupon code', 'error');
            return;
        }
        
        // Get plan or event ID
        const planId = document.querySelector('input[name="plan_id"]')?.value;
        const eventId = document.getElementById('event_id')?.value ||
                        window.location.pathname.match(/\/popcorn\/event\/([^\/]+)\/checkout/)?.[1] ||
                        document.body.dataset.eventId ||
                        document.querySelector('form')?.dataset.eventId ||
                        document.querySelector('[data-event-id]')?.dataset.eventId;
        
        if (!planId && !eventId) {
            showMessage('Unable to determine plan or event', 'error');
            return;
        }
        
        // Show loading state
        const originalBtnText = applyBtn.innerHTML;
        applyBtn.disabled = true;
        applyBtn.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Validating...';
        
        // Prepare form data
        const formData = new FormData();
        formData.append('code', couponCode);
        if (planId) formData.append('plan_id', planId);
        if (eventId) formData.append('event_id', eventId);
        
        // Add CSRF token
        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') ||
                         document.querySelector('input[name="csrf_token"]')?.value ||
                         (typeof odoo !== 'undefined' && odoo.csrf_token);
        if (csrfToken) {
            formData.append('csrf_token', csrfToken);
        }
        
        // Make request to validate coupon
        fetch('/popcorn/discount/validate', {
            method: 'POST',
            credentials: 'same-origin',
            body: formData
        })
        .then((response) => {
            if (!response.ok) {
                throw new Error('Failed to validate coupon');
            }
            return response.json();
        })
        .then((result) => {
            if (result.success) {
                // Set the applied_discount_id hidden field
                const discountIdInput = document.getElementById('applied_discount_id');
                if (discountIdInput) {
                    discountIdInput.value = result.discount.id;
                }

                // Update UI
                showMessage(result.message, 'success');
                updateTotalPrice(result.pricing);

                // Update UI state
                applyBtn.style.display = 'none';
                if (removeBtn) removeBtn.style.display = 'inline-block';
                couponInput.disabled = true;

                // First-timer coupon: disable Popcorn Money (mutually exclusive)
                if (result.discount.is_first_timer_coupon) {
                    window.firstTimerCouponApplied = true;
                    const popcornMoneyCheckbox = document.getElementById('use_popcorn_money');
                    if (popcornMoneyCheckbox) {
                        if (popcornMoneyCheckbox.checked) {
                            popcornMoneyCheckbox.checked = false;
                            popcornMoneyCheckbox.dispatchEvent(new Event('change'));
                        }
                        popcornMoneyCheckbox.disabled = true;
                        const popcornMoneySection = popcornMoneyCheckbox.closest('.popcorn-form-section');
                        if (popcornMoneySection) {
                            let note = popcornMoneySection.querySelector('.popcorn-first-timer-money-note');
                            if (!note) {
                                note = document.createElement('p');
                                note.className = 'popcorn-first-timer-money-note text-muted';
                                note.style.fontSize = '0.85em';
                                note.style.marginTop = '4px';
                                note.textContent = 'Popcorn Money cannot be combined with a first-timer coupon.';
                                popcornMoneySection.appendChild(note);
                            }
                        }
                    }
                }

                // Update first-timer discount button if applicable
                if (window.firstTimerDiscountButton) {
                    window.firstTimerDiscountButton.innerHTML = '<i class="fa fa-check-circle"></i> Discount Applied!';
                    window.firstTimerDiscountButton.classList.remove('popcorn-btn-success');
                    window.firstTimerDiscountButton.classList.add('popcorn-btn-secondary');
                    if (window.firstTimerDiscountNotification) {
                        setTimeout(() => {
                            window.firstTimerDiscountNotification.style.display = 'none';
                        }, 2000);
                    }
                }
            } else {
                showMessage(result.message, 'error');
            }
        })
        .catch((error) => {
            console.error('Popcorn coupon: unable to validate coupon.', error);
            showMessage('Error validating coupon. Please try again.', 'error');
        })
        .finally(() => {
            // Restore button state
            applyBtn.disabled = false;
            applyBtn.innerHTML = originalBtnText;
        });
    });
    
    // Handle remove coupon button click
    if (removeBtn) {
        removeBtn.addEventListener('click', function(evt) {
            evt.preventDefault();

            // Clear the applied_discount_id
            const discountIdInput = document.getElementById('applied_discount_id');
            if (discountIdInput) {
                discountIdInput.value = '';
            }

            // Reset UI
            couponInput.value = '';
            couponInput.disabled = false;
            applyBtn.style.display = 'inline-block';
            removeBtn.style.display = 'none';

            // Update total price
            updateTotalPrice();

            // Re-enable Popcorn Money if it was disabled by a first-timer coupon
            if (window.firstTimerCouponApplied) {
                window.firstTimerCouponApplied = false;
                const popcornMoneyCheckbox = document.getElementById('use_popcorn_money');
                if (popcornMoneyCheckbox) {
                    popcornMoneyCheckbox.disabled = false;
                    const popcornMoneySection = popcornMoneyCheckbox.closest('.popcorn-form-section');
                    if (popcornMoneySection) {
                        const note = popcornMoneySection.querySelector('.popcorn-first-timer-money-note');
                        if (note) note.remove();
                    }
                }
            }

            // Reset first-timer discount button if applicable
            if (window.firstTimerDiscountButton) {
                window.firstTimerDiscountButton.innerHTML = '<i class="fa fa-check"></i> Use My Discount';
                window.firstTimerDiscountButton.classList.remove('popcorn-btn-secondary');
                window.firstTimerDiscountButton.classList.add('popcorn-btn-success');
                window.firstTimerDiscountButton.disabled = false;
                if (window.firstTimerDiscountNotification) {
                    window.firstTimerDiscountNotification.style.display = 'block';
                }
            }

            showMessage('Coupon removed', 'success');
        });
    }
    
    // Handle "Use My Discount" button for first-timer customers
    document.addEventListener('click', function(evt) {
        const button = evt.target.closest('.popcorn-use-discount-btn');
        if (!button) return;
        
        evt.preventDefault();
        
        const discountCode = button.dataset.discountCode;
        if (!discountCode || !couponInput || !applyBtn) return;
        
        couponInput.value = discountCode;
        button.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Applying...';
        button.disabled = true;
        
        window.firstTimerDiscountButton = button;
        window.firstTimerDiscountNotification = document.querySelector('.popcorn-first-timer-discount-notification');
        applyBtn.click();
    });
}

// Helper function to display toast notifications
function showMessage(message, type) {
    // Remove any existing toasts
    const existingToast = document.querySelector('.popcorn-toast-notification');
    if (existingToast) {
        existingToast.remove();
    }
    
    // Create toast container if it doesn't exist
    let toastContainer = document.querySelector('.popcorn-toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.className = 'popcorn-toast-container';
        document.body.appendChild(toastContainer);
    }
    
    // Map type to banner style
    const styleMap = {
        'success': 'popcorn-banner-success',
        'error': 'popcorn-banner-danger',
        'warning': 'popcorn-banner-warning',
        'info': 'popcorn-banner-info'
    };
    
    const iconMap = {
        'success': 'fa-check-circle',
        'error': 'fa-exclamation-circle',
        'warning': 'fa-exclamation-triangle',
        'info': 'fa-info-circle'
    };
    
    const bannerStyle = styleMap[type] || 'popcorn-banner-info';
    const icon = iconMap[type] || 'fa-info-circle';
    
    // Create toast element
    const toast = document.createElement('div');
    toast.className = `popcorn-banner ${bannerStyle} popcorn-toast-notification`;
    toast.innerHTML = `
        <div class="popcorn-banner-content">
            <div class="popcorn-banner-header">
                <i class="fa ${icon}"></i>
                <span style="flex: 1; margin-left: 10px;">${message}</span>
                <button class="popcorn-banner-close" aria-label="Close">
                    <i class="fa fa-times"></i>
                </button>
            </div>
        </div>
    `;
    
    // Add to container
    toastContainer.appendChild(toast);
    
    // Animate in
    setTimeout(() => {
        toast.classList.add('popcorn-banner-show');
    }, 10);
    
    // Auto-dismiss after 5 seconds
    const autoDismissTimer = setTimeout(() => {
        dismissToast(toast);
    }, 5000);
    
    // Close button handler
    const closeBtn = toast.querySelector('.popcorn-banner-close');
    closeBtn.addEventListener('click', () => {
        clearTimeout(autoDismissTimer);
        dismissToast(toast);
    });
    
    function dismissToast(toastElement) {
        toastElement.classList.remove('popcorn-banner-show');
        setTimeout(() => {
            if (toastElement.parentNode) {
                toastElement.remove();
            }
        }, 300);
    }
}

// Helper function to update total price display
function updateTotalPrice(pricingData = null) {
    const totalPriceElement = document.getElementById('popcorn-total-price');
    const discountRow = document.getElementById('popcorn-discount-row');
    const discountAmountElement = document.getElementById('popcorn-discount-amount');
    
    if (!totalPriceElement) {
        return;
    }
    
    if (pricingData && pricingData.discount_amount > 0) {
        if (discountRow) discountRow.style.display = 'flex';
        if (discountAmountElement) {
            discountAmountElement.textContent = `-${pricingData.currency_symbol}${pricingData.discount_amount.toFixed(2)}`;
        }
        totalPriceElement.textContent = `${pricingData.currency_symbol}${pricingData.discounted_price.toFixed(2)}`;
    } else {
        if (discountRow) discountRow.style.display = 'none';
        if (!window.popcornOriginalPrice) {
            window.popcornOriginalPrice = totalPriceElement.textContent;
        }
        totalPriceElement.textContent = window.popcornOriginalPrice;
    }
}

// Wait for the page to be ready before wiring events
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', wireCouponPage);
} else {
    wireCouponPage();
}
