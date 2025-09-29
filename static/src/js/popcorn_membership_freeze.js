// Simple vanilla JavaScript approach for freeze functionality
function setupFreezeFunctionality() {
  // Setup freeze modal functionality
  const freezeModal = document.getElementById('freezeModal');
  const freezeForm = document.getElementById('freezeForm');
  const freezeDaysInput = document.getElementById('freezeDays');
  
  // Debug logging to help identify issues
  if (!freezeModal) {
    console.log('Freeze modal not found, skipping freeze functionality setup');
    return;
  }
  if (!freezeForm) {
    console.log('Freeze form not found, skipping freeze functionality setup');
    return;
  }
  if (!freezeDaysInput) {
    console.log('Freeze days input not found, skipping freeze functionality setup');
    return;
  }
  
  console.log('Setting up freeze functionality...');
  
  if (freezeModal && freezeForm && freezeDaysInput) {
    // Bootstrap modal should be available in Odoo
    
    // Setup freeze buttons
    const freezeButtons = document.querySelectorAll('.popcorn-freeze-btn');
    
    freezeButtons.forEach(btn => {
      btn.addEventListener('click', function(evt) {
        evt.preventDefault();
        
        console.log('Freeze button clicked');
        
        const membershipId = this.dataset.membershipId;
        const minDays = parseInt(this.dataset.minDays) || 7;
        const maxDays = parseInt(this.dataset.maxDays) || 30;
        
        console.log('Membership ID:', membershipId, 'Min days:', minDays, 'Max days:', maxDays);
        
        // Update form action
        freezeForm.action = `/my/cards/${membershipId}/freeze`;
        
        // Update min/max values
        freezeDaysInput.min = minDays;
        freezeDaysInput.max = maxDays;
        freezeDaysInput.value = minDays;
        
        // Update display - with null checks to prevent errors
        const minDaysElement = document.getElementById('minDays');
        const maxDaysElement = document.getElementById('maxDays');
        
        if (minDaysElement) {
            minDaysElement.textContent = minDays;
        }
        if (maxDaysElement) {
            maxDaysElement.textContent = maxDays;
        }
        
        // Initialize freeze start date to today
        const freezeStartDateInput = document.getElementById('freezeStartDate');
        if (freezeStartDateInput) {
          const today = new Date();
          freezeStartDateInput.value = today.toISOString().split('T')[0];
          freezeStartDateInput.min = today.toISOString().split('T')[0]; // Allow today and future dates
        }
        
        // Update freeze period preview
        updateFreezePeriodPreview();
        
        // Show modal
        console.log('About to show modal');
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
    
    // Setup freeze start date input change
    const freezeStartDateInput = document.getElementById('freezeStartDate');
    if (freezeStartDateInput) {
      freezeStartDateInput.addEventListener('change', updateFreezePeriodPreview);
    }
    
    // Setup form submission
    freezeForm.addEventListener('submit', function(evt) {
      evt.preventDefault();
      
      const formData = new FormData(freezeForm);
      const freezeDays = formData.get('freeze_days');
      const freezeStartDate = formData.get('freeze_start_date');
      
      if (!freezeDays || freezeDays < parseInt(freezeDaysInput.min) || freezeDays > parseInt(freezeDaysInput.max)) {
        alert('Please enter a valid freeze duration.');
        return;
      }
      
      if (!freezeStartDate) {
        alert('Please select a start date for the freeze.');
        return;
      }
      
      // Check if start date is in the future
      const selectedDate = new Date(freezeStartDate);
      const today = new Date();
      today.setHours(0, 0, 0, 0); // Reset time to start of day
      
      if (selectedDate < today) {
        alert('The freeze start date must be today or in the future.');
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
  console.log('showModal called, modal found:', !!modal);
  
  if (modal) {
    try {
      // Use Bootstrap modal show method
      const bootstrapModal = new bootstrap.Modal(modal);
      bootstrapModal.show();
      console.log('Bootstrap modal shown successfully');
    } catch (e) {
      console.log('Bootstrap modal failed, trying fallback:', e);
      // Fallback: try to show modal manually
      modal.style.display = 'block';
      modal.classList.add('show');
      document.body.classList.add('modal-open');
    }
  } else {
    console.log('Modal not found in showModal');
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
  const freezeDaysInput = document.getElementById('freezeDays');
  const freezeStartDateInput = document.getElementById('freezeStartDate');
  const freezeStartDateDisplay = document.getElementById('freezeStartDateDisplay');
  const freezeEndDateDisplay = document.getElementById('freezeEndDateDisplay');
  
  console.log('updateFreezePeriodPreview called');
  console.log('Elements found:', {
    freezeDaysInput: !!freezeDaysInput,
    freezeStartDateInput: !!freezeStartDateInput,
    freezeStartDateDisplay: !!freezeStartDateDisplay,
    freezeEndDateDisplay: !!freezeEndDateDisplay
  });
  
  if (!freezeDaysInput || !freezeStartDateInput || !freezeStartDateDisplay || !freezeEndDateDisplay) {
    console.log('Some elements not found, exiting updateFreezePeriodPreview');
    return; // Exit early if elements are not found
  }
  
  const freezeDays = parseInt(freezeDaysInput.value) || 0;
  
  // Get the selected start date from the date picker
  let startDate;
  if (freezeStartDateInput.value) {
    startDate = new Date(freezeStartDateInput.value);
  } else {
    // Default to today if no date selected
    startDate = new Date();
    freezeStartDateInput.value = startDate.toISOString().split('T')[0];
  }
  
  // Calculate end date (inclusive of the freeze duration)
  const endDate = new Date(startDate);
  endDate.setDate(endDate.getDate() + freezeDays - 1);
  
  console.log('Updating dates:', { 
    freezeDays, 
    startDate: startDate.toLocaleDateString(), 
    endDate: endDate.toLocaleDateString() 
  });
  
  // Update display elements
  freezeStartDateDisplay.textContent = startDate.toLocaleDateString();
  freezeEndDateDisplay.textContent = endDate.toLocaleDateString();
}


// Initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', setupFreezeFunctionality);
} else {
  setupFreezeFunctionality();
}

// Also initialize when page loads dynamically (for SPA-like behavior)
document.addEventListener('DOMContentLoaded', function() {
  // Small delay to ensure all elements are loaded, especially for dynamic content
  setTimeout(setupFreezeFunctionality, 100);
});

// Additional initialization for dynamic content loading
window.addEventListener('load', function() {
  setTimeout(setupFreezeFunctionality, 200);
});
