/** @odoo-module **/

// Toast notification helper function (can be used by other scripts)
function showToastNotification(message, type) {
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

// Simple vanilla JavaScript approach for error banner functionality
function setupErrorBanner() {
  // Setup error banner functionality
  const errorBanner = document.querySelector('.popcorn-error-banner');
  
  if (errorBanner) {
    // Auto-hide after 8 seconds
    setTimeout(() => {
      errorBanner.classList.add('hidden');
    }, 8000);
    
    // Setup close button functionality
    const closeBtn = errorBanner.querySelector('.popcorn-error-close');
    if (closeBtn) {
      closeBtn.addEventListener('click', function(evt) {
        evt.preventDefault();
        evt.stopPropagation();
        errorBanner.classList.add('hidden');
      });
    }
  }
  
  // Check for URL error parameters and show as toast
  const urlParams = new URLSearchParams(window.location.search);
  const errorCode = urlParams.get('error');
  
  if (errorCode) {
    const errorMessages = {
      'no_partner': 'Your account is missing required information. Please contact support.',
      'missing_fields': 'Please fill in all required fields.',
      'missing_payment_method': 'Please select a payment method.',
      'terms_not_accepted': 'Please accept the terms and conditions to continue.',
      'invalid_payment_method': 'The selected payment method is invalid.',
      'payment_access_denied': 'Unable to access payment provider. Please try again or contact support.',
      'processing_failed': 'There was an error processing your request. Please try again.',
      'session_expired': 'Your session has expired. Please try again.',
      'transaction_not_found': 'Transaction not found. Please contact support.',
      'payment_cancelled': 'Payment was cancelled.',
      'payment_failed': 'Payment failed. Please try again.',
      'gateway_unavailable': 'Payment gateway is currently unavailable. Please try again later.',
      'callback_failed': 'Payment processing failed. Please contact support.'
    };
    
    const errorMessage = errorMessages[errorCode] || 'An error occurred. Please try again.';
    
    // Show toast notification
    showToastNotification(errorMessage, 'error');
    
    // Clean URL by removing error parameter
    const url = new URL(window.location);
    url.searchParams.delete('error');
    window.history.replaceState({}, '', url);
  }
}

// Popcorn Money functionality
function setupPopcornMoney() {
  const popcornMoneyCheckbox = document.getElementById('use_popcorn_money');
  
  // Store original price globally to prevent recalculation issues
  let storedOriginalPrice = null;
  let storedOriginalPriceText = null;
  
  if (popcornMoneyCheckbox) {
    popcornMoneyCheckbox.addEventListener('change', function() {
      const isChecked = this.checked;
      const popcornMoneyRow = document.getElementById('popcorn-money-row');
      const popcornMoneyUsed = document.getElementById('popcorn-money-used');
      const totalPrice = document.getElementById('popcorn-total-price');
      const paymentMethods = document.querySelector('.popcorn-payment-methods');
      const formLabel = document.querySelector('.popcorn-form-label');
      
      console.log('Membership Popcorn Money checkbox changed:', isChecked);
      console.log('Elements found:', {
        popcornMoneyRow: !!popcornMoneyRow,
        popcornMoneyUsed: !!popcornMoneyUsed,
        totalPrice: !!totalPrice
      });
      
      // Store original price if not already stored
      if (!storedOriginalPrice) {
        // Get the original price from the first price row
        const priceRows = document.querySelectorAll('.popcorn-price-row');
        let originalPriceText = '';
        let originalPrice = 0;
      
      // Find the total price (which includes discounts) instead of base price
      for (let row of priceRows) {
        const label = row.querySelector('.popcorn-price-label');
        if (label) {
          const labelText = label.textContent.trim();
          console.log('Checking label:', labelText);
          
          // Look for the "Total" row which contains the final discounted price
          if (labelText.includes('Total') || labelText.includes('总计') || labelText.includes('合计')) {
            const priceValue = row.querySelector('.popcorn-price-value');
            if (priceValue) {
              originalPriceText = priceValue.textContent;
              originalPrice = parseFloat(priceValue.textContent.replace(/[^\d.-]/g, ''));
              console.log('Found total price (with discounts):', labelText, originalPriceText, originalPrice);
              break;
            }
          }
        }
      }
      
      // Fallback: if no total row found, look for membership fee or upgrade price
      if (!originalPriceText) {
        for (let row of priceRows) {
          const label = row.querySelector('.popcorn-price-label');
          if (label) {
            const labelText = label.textContent.trim();
            console.log('Fallback - checking label:', labelText);
            
            if (labelText.includes('Membership Fee') || labelText.includes('Upgrade Price') || 
                labelText.includes('会员费') || labelText.includes('升级价格')) {
              const priceValue = row.querySelector('.popcorn-price-value');
              if (priceValue) {
                originalPriceText = priceValue.textContent;
                originalPrice = parseFloat(priceValue.textContent.replace(/[^\d.-]/g, ''));
                console.log('Fallback to base price:', labelText, originalPriceText, originalPrice);
                break;
              }
            }
          }
        }
      }
      
      // Final fallback: use the first price row
      if (!originalPriceText && priceRows.length > 0) {
        const firstRow = priceRows[0];
        const priceValue = firstRow.querySelector('.popcorn-price-value');
        if (priceValue) {
          originalPriceText = priceValue.textContent;
          originalPrice = parseFloat(priceValue.textContent.replace(/[^\d.-]/g, ''));
          console.log('Final fallback to first row price:', originalPriceText, originalPrice);
        }
        }
        
        storedOriginalPrice = originalPrice;
        storedOriginalPriceText = originalPriceText;
        console.log('Stored original price:', originalPriceText, 'Parsed:', originalPrice);
      }
      
      const originalPrice = storedOriginalPrice;
      const originalPriceText = storedOriginalPriceText;
      console.log('Using stored original price:', originalPriceText, 'Parsed:', originalPrice);
      
      // Get popcorn money balance from the checkbox label
      const label = document.querySelector('label[for="use_popcorn_money"]');
      const balanceText = label ? label.querySelector('.popcorn-money-balance').textContent : '';
      const balance = balanceText ? parseFloat(balanceText.match(/[\d.-]+/)[0]) : 0;
      
      console.log('Balance text:', balanceText, 'Parsed:', balance);
      
      if (isChecked) {
        // Show popcorn money row
        if (popcornMoneyRow) {
          popcornMoneyRow.style.display = 'block';
        }
        
        // Calculate how much popcorn money to use (minimum of balance and price)
        const popcornMoneyToUse = Math.min(balance, originalPrice);
        const remainingPrice = originalPrice - popcornMoneyToUse;
        
        console.log('Calculations:', {
          popcornMoneyToUse: popcornMoneyToUse,
          remainingPrice: remainingPrice
        });
        
        // Update popcorn money used display
        const currencySymbol = originalPriceText.match(/[^\d.-]/)[0] || '$';
        if (popcornMoneyUsed) {
          popcornMoneyUsed.textContent = '-' + currencySymbol + popcornMoneyToUse.toFixed(2);
        }
        
        // Update total price
        if (totalPrice) {
          totalPrice.textContent = currencySymbol + remainingPrice.toFixed(2);
          console.log('Updated total price to:', currencySymbol + remainingPrice.toFixed(2));
        }
        
        // If popcorn money covers the full amount, hide payment methods
        if (remainingPrice <= 0) {
          if (paymentMethods) {
            paymentMethods.style.display = 'none';
            // Remove required attribute from payment method inputs
            const radioInputs = paymentMethods.querySelectorAll('input[type="radio"]');
            radioInputs.forEach(input => input.removeAttribute('required'));
          }
          if (formLabel) {
            formLabel.textContent = 'Payment Method (Not Required)';
          }
        } else {
          if (paymentMethods) {
            paymentMethods.style.display = 'block';
            // Add required attribute back to payment method inputs
            const radioInputs = paymentMethods.querySelectorAll('input[type="radio"]');
            radioInputs.forEach(input => input.setAttribute('required', 'required'));
          }
          if (formLabel) {
            formLabel.textContent = 'Select Payment Method *';
          }
        }
      } else {
        // Hide popcorn money row
        if (popcornMoneyRow) {
          popcornMoneyRow.style.display = 'none';
        }
        
        // Reset total price to original
        if (totalPrice) {
          totalPrice.textContent = originalPriceText;
          console.log('Reset total price to:', originalPriceText);
        }
        
        // Show payment methods
        if (paymentMethods) {
          paymentMethods.style.display = 'block';
          // Add required attribute back to payment method inputs
          const radioInputs = paymentMethods.querySelectorAll('input[type="radio"]');
          radioInputs.forEach(input => input.setAttribute('required', 'required'));
        }
        if (formLabel) {
          formLabel.textContent = 'Select Payment Method *';
        }
      }
    });
  }
}

// Try to setup immediately if DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', function() {
    setupErrorBanner();
    setupPopcornMoney();
  });
} else {
  setupErrorBanner();
  setupPopcornMoney();
}

// Global popup functionality
window.PopcornMembershipPopup = {
    showPopup(message, type = 'info') {
      const popup = document.createElement('div');
      popup.className = `popcorn-popup popcorn-popup-${type}`;
      popup.innerHTML = `
        <div class="popcorn-popup-content">
          <div class="popcorn-popup-message">${message}</div>
          <button type="button" class="popcorn-popup-close"><i class="fa fa-times"></i></button>
        </div>
      `;
      document.body.appendChild(popup);
      
      const closeBtn = popup.querySelector('.popcorn-popup-close');
      closeBtn.addEventListener('click', () => popup.remove());
      
      setTimeout(() => popup.remove(), 5000);
    },
    
    showMembershipRequired(message) {
      this.showPopup(message || 'Check out the membership plans for big savings and awesome benefits!', 'info');
    }
  };
