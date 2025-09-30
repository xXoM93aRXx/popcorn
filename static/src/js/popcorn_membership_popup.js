/** @odoo-module **/

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
