// Simple vanilla JavaScript approach for freeze functionality
function setupFreezeFunctionality() {
  // Setup freeze modal functionality
  const freezeModal = document.getElementById('freezeModal');
  const freezeForm = document.getElementById('freezeForm');
  const freezeDaysInput = document.getElementById('freezeDays');
  
  if (freezeModal && freezeForm && freezeDaysInput) {
    // Bootstrap modal should be available in Odoo
    
    // Setup freeze buttons
    const freezeButtons = document.querySelectorAll('.popcorn-freeze-btn');
    
    freezeButtons.forEach(btn => {
      btn.addEventListener('click', function(evt) {
        evt.preventDefault();
        
        const membershipId = this.dataset.membershipId;
        const minDays = parseInt(this.dataset.minDays) || 7;
        const maxDays = parseInt(this.dataset.maxDays) || 30;
        
        // Update form action
        freezeForm.action = `/my/cards/${membershipId}/freeze`;
        
        // Update min/max values
        freezeDaysInput.min = minDays;
        freezeDaysInput.max = maxDays;
        freezeDaysInput.value = minDays;
        
        // Update display
        document.getElementById('minDays').textContent = minDays;
        document.getElementById('maxDays').textContent = maxDays;
        
        
        // Update freeze period preview
        updateFreezePeriodPreview();
        
        // Show modal
        showModal();
      });
    });
    
    // Setup unfreeze buttons
    const unfreezeButtons = document.querySelectorAll('.popcorn-unfreeze-btn');
    
    unfreezeButtons.forEach(btn => {
      btn.addEventListener('click', function(evt) {
        evt.preventDefault();
        
        const membershipId = this.dataset.membershipId;
        
        // Create and submit unfreeze form
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = `/my/cards/${membershipId}/unfreeze`;
        
        // Add CSRF token
        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || 
                         document.querySelector('input[name="csrf_token"]')?.value;
        if (csrfToken) {
          const csrfInput = document.createElement('input');
          csrfInput.type = 'hidden';
          csrfInput.name = 'csrf_token';
          csrfInput.value = csrfToken;
          form.appendChild(csrfInput);
        }
        
        document.body.appendChild(form);
        form.submit();
      });
    });
    
    // Setup freeze days input change
    freezeDaysInput.addEventListener('input', updateFreezePeriodPreview);
    
    // Setup form submission
    freezeForm.addEventListener('submit', function(evt) {
      evt.preventDefault();
      
      const formData = new FormData(freezeForm);
      const freezeDays = formData.get('freeze_days');
      
      if (!freezeDays || freezeDays < parseInt(freezeDaysInput.min) || freezeDays > parseInt(freezeDaysInput.max)) {
        alert('Please enter a valid freeze duration.');
        return;
      }
      
      // Ensure CSRF token is present
      let csrfToken = formData.get('csrf_token');
      
      if (!csrfToken) {
        // Try to get CSRF token from meta tag
        csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
        
        if (!csrfToken) {
          // Try to get CSRF token from input field
          csrfToken = document.querySelector('input[name="csrf_token"]')?.value;
        }
        
        if (csrfToken) {
          // Add CSRF token to form
          const csrfInput = document.createElement('input');
          csrfInput.type = 'hidden';
          csrfInput.name = 'csrf_token';
          csrfInput.value = csrfToken;
          freezeForm.appendChild(csrfInput);
        }
      }
      
      // Submit form normally (let it redirect)
      freezeForm.submit();
    });
    
    // Setup modal close buttons
    const closeButtons = freezeModal.querySelectorAll('.btn-close, .btn-secondary');
    closeButtons.forEach(btn => {
      btn.addEventListener('click', hideModal);
    });
    
    // Close modal when clicking outside
    freezeModal.addEventListener('click', function(evt) {
      if (evt.target === freezeModal) {
        hideModal();
      }
    });
  }
}

function showModal() {
  const modal = document.getElementById('freezeModal');
  if (modal) {
    try {
      // Use Bootstrap modal show method
      const bootstrapModal = new bootstrap.Modal(modal);
      bootstrapModal.show();
    } catch (e) {
      // Fallback: try to show modal manually
      modal.style.display = 'block';
      modal.classList.add('show');
      document.body.classList.add('modal-open');
    }
  }
}

function hideModal() {
  const modal = document.getElementById('freezeModal');
  if (modal) {
    try {
      // Use Bootstrap modal hide method
      const bootstrapModal = bootstrap.Modal.getInstance(modal);
      if (bootstrapModal) {
        bootstrapModal.hide();
      }
    } catch (e) {
      // Fallback: try to hide modal manually
      modal.style.display = 'none';
      modal.classList.remove('show');
      document.body.classList.remove('modal-open');
    }
  }
}

function updateFreezePeriodPreview() {
  const freezeDays = parseInt(document.getElementById('freezeDays').value) || 0;
  const startDate = new Date();
  const endDate = new Date();
  endDate.setDate(endDate.getDate() + freezeDays);
  
  document.getElementById('freezeStartDate').textContent = startDate.toLocaleDateString();
  document.getElementById('freezeEndDate').textContent = endDate.toLocaleDateString();
}


// Initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', setupFreezeFunctionality);
} else {
  setupFreezeFunctionality();
}

// Also initialize when page loads dynamically (for SPA-like behavior)
document.addEventListener('DOMContentLoaded', function() {
  // Small delay to ensure all elements are loaded
  setTimeout(setupFreezeFunctionality, 100);
});
