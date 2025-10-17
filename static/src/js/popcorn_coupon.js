// Simple vanilla JavaScript approach for coupon functionality
console.log('🎟️ Popcorn Coupon JS file loaded');

function setupCouponFunctionality() {
    console.log('=== Setting up Coupon Functionality ===');
    
    // Check if we're on a page that should have coupon functionality
    const isEventCheckout = window.location.pathname.includes('/popcorn/event/') && window.location.pathname.includes('/checkout');
    const isMembershipCheckout = window.location.pathname.includes('/memberships/') && window.location.pathname.includes('/checkout');
    
    if (!isEventCheckout && !isMembershipCheckout) {
        console.log('Not on a checkout page, skipping coupon functionality');
        return;
    }
    
    console.log('On checkout page:', { isEventCheckout, isMembershipCheckout });
    
    const couponInput = document.getElementById('coupon_code');
    const applyBtn = document.getElementById('apply_coupon_btn');
    const removeBtn = document.getElementById('remove_coupon_btn');
    
    // Save original price on page load
    const totalPriceElement = document.getElementById('popcorn-total-price');
    if (totalPriceElement && !window.popcornOriginalPrice) {
        window.popcornOriginalPrice = totalPriceElement.textContent;
        console.log('💰 Saved original price:', window.popcornOriginalPrice);
    }
    
    console.log('Coupon elements found:', {
        couponInput: !!couponInput,
        applyBtn: !!applyBtn,
        removeBtn: !!removeBtn
    });
    
    if (!couponInput || !applyBtn) {
        console.log('❌ Coupon elements not found, skipping coupon functionality setup');
        return;
    }
    
    console.log('✅ Setting up coupon event listeners...');
    
    // Handle apply coupon button click
    applyBtn.addEventListener('click', function(evt) {
        evt.preventDefault();
        console.log('=== Apply Coupon Button Clicked ===');
        
        const couponCode = couponInput.value.trim();
        console.log('Coupon code entered:', couponCode);
        
        if (!couponCode) {
            console.log('❌ No coupon code entered');
            showMessage('Please enter a coupon code', 'error');
            return;
        }
        
        // Get plan or event ID
        let planId = document.querySelector('input[name="plan_id"]')?.value;
        let eventId = document.getElementById('event_id')?.value;
        
        // If not found in inputs, try to get from URL or data attributes
        if (!eventId && isEventCheckout) {
            // Extract event ID from URL like /popcorn/event/123/checkout
            console.log('Current URL:', window.location.pathname);
            const urlMatch = window.location.pathname.match(/\/popcorn\/event\/([^\/]+)\/checkout/);
            console.log('URL match result:', urlMatch);
            if (urlMatch) {
                eventId = urlMatch[1];
                console.log('Extracted event ID from URL:', eventId);
            } else {
                console.log('❌ Could not extract event ID from URL');
                // Try alternative methods
                // Check if there's a data attribute on the body or form
                const eventIdFromData = document.body.dataset.eventId || 
                                      document.querySelector('form')?.dataset.eventId ||
                                      document.querySelector('[data-event-id]')?.dataset.eventId;
                if (eventIdFromData) {
                    eventId = eventIdFromData;
                    console.log('Found event ID from data attribute:', eventId);
                }
            }
        }
        
        console.log('Plan ID:', planId, 'Event ID:', eventId);
        
        if (!planId && !eventId) {
            console.log('❌ No plan or event ID found');
            showMessage('Unable to determine plan or event', 'error');
            return;
        }
        
        // Show loading state
        const originalBtnText = applyBtn.innerHTML;
        applyBtn.disabled = true;
        applyBtn.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Validating...';
        
        console.log('Sending validation request to server...');
        
        // Make AJAX request to validate coupon
        fetch('/popcorn/discount/validate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({
                jsonrpc: '2.0',
                method: 'call',
                params: {
                    code: couponCode,
                    plan_id: planId,
                    event_id: eventId
                }
            })
        })
        .then(response => response.json())
        .then(data => {
            console.log('Response received:', data);
            
            // Handle Odoo JSON-RPC error response
            if (data.error) {
                console.log('❌ Server error:', data.error);
                showMessage('Server error: ' + (data.error.message || 'Unknown error'), 'error');
                return;
            }
            
            const result = data.result;
            
            if (result.success) {
                console.log('✅ Coupon validation successful!');
                console.log('Discount details:', result.discount);
                console.log('Pricing details:', result.pricing);
                
                // CRITICAL: Set the applied_discount_id hidden field
                const discountIdInput = document.getElementById('applied_discount_id');
                if (discountIdInput) {
                    discountIdInput.value = result.discount.id;
                    console.log('✅ Set applied_discount_id to:', result.discount.id);
                } else {
                    console.log('❌ applied_discount_id field not found!');
                }
                
                // Update UI
                showMessage(result.message, 'success');
                updateTotalPrice(result.pricing);
                
                // Hide apply button, show remove button
                applyBtn.style.display = 'none';
                if (removeBtn) {
                    removeBtn.style.display = 'inline-block';
                }
                
                // Disable input
                couponInput.disabled = true;
                
                // If this was triggered by "Use My Discount" button, update it
                if (window.firstTimerDiscountButton) {
                    window.firstTimerDiscountButton.innerHTML = '<i class="fa fa-check-circle"></i> Discount Applied!';
                    window.firstTimerDiscountButton.classList.remove('popcorn-btn-success');
                    window.firstTimerDiscountButton.classList.add('popcorn-btn-secondary');
                    
                    // Hide the notification after a short delay
                    if (window.firstTimerDiscountNotification) {
                        setTimeout(() => {
                            window.firstTimerDiscountNotification.style.display = 'none';
                        }, 2000);
                    }
                }
                
            } else {
                console.log('❌ Coupon validation failed:', result.message);
                showMessage(result.message, 'error');
            }
        })
        .catch(error => {
            console.log('❌ AJAX error:', error);
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
            console.log('=== Remove Coupon Button Clicked ===');
            
            // Clear the applied_discount_id
            const discountIdInput = document.getElementById('applied_discount_id');
            if (discountIdInput) {
                discountIdInput.value = '';
                console.log('✅ Cleared applied_discount_id');
            }
            
            // Reset UI
            couponInput.value = '';
            couponInput.disabled = false;
            applyBtn.style.display = 'inline-block';
            removeBtn.style.display = 'none';
            
            // Update total price
            updateTotalPrice();
            
            // Reset first-timer discount button if it exists
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
        if (evt.target.classList.contains('popcorn-use-discount-btn') || 
            evt.target.closest('.popcorn-use-discount-btn')) {
            
            evt.preventDefault();
            console.log('=== Use My Discount Button Clicked ===');
            
            const button = evt.target.classList.contains('popcorn-use-discount-btn') ? 
                          evt.target : evt.target.closest('.popcorn-use-discount-btn');
            
            const discountCode = button.dataset.discountCode;
            console.log('First-timer discount code:', discountCode);
            
            if (discountCode && couponInput && applyBtn) {
                // Fill the coupon input with the discount code
                couponInput.value = discountCode;
                console.log('Filled coupon input with:', discountCode);
                
                // Change button text and disable it
                const originalHTML = button.innerHTML;
                button.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Applying...';
                button.disabled = true;
                
                // Store the button and notification for later use
                window.firstTimerDiscountButton = button;
                window.firstTimerDiscountNotification = document.querySelector('.popcorn-first-timer-discount-notification');
                
                // Automatically apply the discount
                console.log('Auto-applying first-timer discount...');
                applyBtn.click();
            } else {
                console.log('Missing required elements:', {
                    discountCode: !!discountCode,
                    couponInput: !!couponInput,
                    applyBtn: !!applyBtn
                });
            }
        }
    });
    
    console.log('✅ Coupon functionality setup complete');
}

// Helper functions
function showMessage(message, type) {
    console.log(`${type.toUpperCase()}: ${message}`);
    // You can add visual message display here if needed
}

function updateTotalPrice(pricingData = null) {
    console.log('Updating total price...', pricingData);
    
    const totalPriceElement = document.getElementById('popcorn-total-price');
    const discountRow = document.getElementById('popcorn-discount-row');
    const discountAmountElement = document.getElementById('popcorn-discount-amount');
    
    if (!totalPriceElement) {
        console.log('❌ Total price element not found');
        return;
    }
    
    if (pricingData && pricingData.discount_amount > 0) {
        // Show discount row
        if (discountRow) {
            discountRow.style.display = 'flex';
        }
        
        // Update discount amount display
        if (discountAmountElement) {
            discountAmountElement.textContent = `-${pricingData.currency_symbol}${pricingData.discount_amount.toFixed(2)}`;
        }
        
        // Update total price
        totalPriceElement.textContent = `${pricingData.currency_symbol}${pricingData.discounted_price.toFixed(2)}`;
        
        console.log('✅ Discount applied:', {
            discount: `-${pricingData.currency_symbol}${pricingData.discount_amount.toFixed(2)}`,
            newTotal: `${pricingData.currency_symbol}${pricingData.discounted_price.toFixed(2)}`
        });
    } else {
        // Hide discount row
        if (discountRow) {
            discountRow.style.display = 'none';
        }
        
        // Reset total price to original
        if (!window.popcornOriginalPrice) {
            window.popcornOriginalPrice = totalPriceElement.textContent;
        }
        totalPriceElement.textContent = window.popcornOriginalPrice;
        
        console.log('✅ Reset to original price:', window.popcornOriginalPrice);
    }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupCouponFunctionality);
} else {
    setupCouponFunctionality();
}

// Also initialize when page loads dynamically
document.addEventListener('DOMContentLoaded', function() {
    setTimeout(setupCouponFunctionality, 100);
});

// Additional initialization for dynamic content loading
window.addEventListener('load', function() {
    setTimeout(setupCouponFunctionality, 200);
});
