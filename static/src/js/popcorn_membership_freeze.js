// Simple vanilla JavaScript approach for freeze functionality
function setupFreezeFunctionality() {
  // Setup freeze modal functionality
  const freezeModal = document.getElementById('freezeModal');
  const freezeForm = document.getElementById('freezeForm');
  const freezeDaysInput = document.getElementById('freezeDays');
  
  if (freezeModal && freezeForm && freezeDaysInput) {
    // Create a simple custom modal if Bootstrap modal doesn't work
    if (!window.bootstrap || !window.bootstrap.Modal) {
      createCustomModal();
    }
    
    // Setup freeze buttons
    const freezeButtons = document.querySelectorAll('.popcorn-freeze-btn');
    
    freezeButtons.forEach(btn => {
      btn.addEventListener('click', function(evt) {
        evt.preventDefault();
        
        const membershipId = this.dataset.membershipId;
        const minDays = parseInt(this.dataset.minDays) || 7;
        const maxDays = parseInt(this.dataset.maxDays) || 30;
        
        // Update form action for both modals
        freezeForm.action = `/my/cards/${membershipId}/freeze`;
        
        // Update min/max values for both modals
        freezeDaysInput.min = minDays;
        freezeDaysInput.max = maxDays;
        freezeDaysInput.value = minDays;
        
        // Update display for both modals
        document.getElementById('minDays').textContent = minDays;
        document.getElementById('maxDays').textContent = maxDays;
        
        // Update custom modal values if it exists
        const customMinDays = document.getElementById('customMinDays');
        const customMaxDays = document.getElementById('customMaxDays');
        const customDaysInput = document.getElementById('customFreezeDays');
        if (customMinDays && customMaxDays && customDaysInput) {
          customMinDays.textContent = minDays;
          customMaxDays.textContent = maxDays;
          customDaysInput.min = minDays;
          customDaysInput.max = maxDays;
          customDaysInput.value = minDays;
          updateCustomFreezePeriodPreview();
        }
        
        // Update freeze period preview
        updateFreezePeriodPreview();
        
        // Show modal
        if (window.bootstrap && window.bootstrap.Modal) {
          showModal();
        } else {
          // Update custom form action
          const customForm = document.getElementById('customFreezeForm');
          if (customForm) {
            customForm.action = `/my/cards/${membershipId}/freeze`;
          }
          showCustomModal();
        }
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

function createCustomModal() {
  // Create a simple custom modal overlay
  const modalOverlay = document.createElement('div');
  modalOverlay.id = 'customFreezeModal';
  modalOverlay.style.cssText = `
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.5);
    z-index: 9999;
    display: none;
    align-items: center;
    justify-content: center;
  `;
  
  const modalContent = document.createElement('div');
  modalContent.style.cssText = `
    background: white;
    padding: 20px;
    border-radius: 8px;
    max-width: 500px;
    width: 90%;
    max-height: 80vh;
    overflow-y: auto;
  `;
  
  modalContent.innerHTML = `
    <h5><i class="fa fa-pause me-2"></i>Freeze Membership</h5>
    <form id="customFreezeForm" method="post">
      <input type="hidden" name="csrf_token" value="${document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || document.querySelector('input[name="csrf_token"]')?.value || ''}"/>
      <div class="alert alert-info">
        <i class="fa fa-info-circle me-2"></i>
        <strong>Freeze Information:</strong>
        <ul class="mb-0 mt-2">
          <li>During the freeze period, you cannot book any events</li>
          <li>Your membership duration will be extended by the freeze days</li>
          <li>You can unfreeze early if needed</li>
        </ul>
      </div>
      
      <div class="mb-3">
        <label for="customFreezeDays" class="form-label">Freeze Duration (Days)</label>
        <input type="number" class="form-control" id="customFreezeDays" name="freeze_days" 
               min="7" max="30" required="required"/>
        <div class="form-text">
          Minimum: <span id="customMinDays">7</span> days | 
          Maximum: <span id="customMaxDays">30</span> days
        </div>
      </div>
      
      <div class="mb-3">
        <label class="form-label">Freeze Period</label>
        <div class="form-control-plaintext">
          <span id="customFreezeStartDate"></span> to <span id="customFreezeEndDate"></span>
        </div>
      </div>
      
      <div class="text-end">
        <button type="button" class="btn btn-secondary me-2" onclick="hideCustomModal()">Cancel</button>
        <button type="submit" class="btn btn-warning">
          <i class="fa fa-pause me-2"></i>Freeze Membership
        </button>
      </div>
    </form>
  `;
  
  modalOverlay.appendChild(modalContent);
  document.body.appendChild(modalOverlay);
  
  // Setup custom modal functionality
  const customForm = document.getElementById('customFreezeForm');
  const customDaysInput = document.getElementById('customFreezeDays');
  
  customDaysInput.addEventListener('input', updateCustomFreezePeriodPreview);
  customForm.addEventListener('submit', handleCustomFormSubmit);
}

function showCustomModal() {
  const modal = document.getElementById('customFreezeModal');
  if (modal) {
    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';
  }
}

function hideCustomModal() {
  const modal = document.getElementById('customFreezeModal');
  if (modal) {
    modal.style.display = 'none';
    document.body.style.overflow = '';
  }
}

function updateCustomFreezePeriodPreview() {
  const freezeDays = parseInt(document.getElementById('customFreezeDays').value) || 0;
  const startDate = new Date();
  const endDate = new Date();
  endDate.setDate(endDate.getDate() + freezeDays);
  
  document.getElementById('customFreezeStartDate').textContent = startDate.toLocaleDateString();
  document.getElementById('customFreezeEndDate').textContent = endDate.toLocaleDateString();
}

function handleCustomFormSubmit(evt) {
  evt.preventDefault();
  
  const formData = new FormData(evt.target);
  const freezeDays = formData.get('freeze_days');
  const minDays = parseInt(document.getElementById('customMinDays').textContent);
  const maxDays = parseInt(document.getElementById('customMaxDays').textContent);
  
  if (!freezeDays || freezeDays < minDays || freezeDays > maxDays) {
    alert('Please enter a valid freeze duration.');
    return;
  }
  
  // Submit form normally (let it redirect)
  evt.target.submit();
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
