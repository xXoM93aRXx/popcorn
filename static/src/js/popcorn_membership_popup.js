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

// Try to setup immediately if DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', setupErrorBanner);
} else {
  setupErrorBanner();
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
