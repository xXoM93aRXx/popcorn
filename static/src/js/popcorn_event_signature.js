// Event registration signature functionality - reuses signature logic from membership checkout

function setupEventSignatureFunctionality() {
    // Only activate on event registration page
    const registrationForm = document.getElementById('event-registration-form');
    
    if (!registrationForm) {
        return;
    }
    
    // Check if signature is needed (contract_id exists)
    const contractIdInput = document.getElementById('contract_id');
    if (!contractIdInput || !contractIdInput.value) {
        // No contract or already signed, proceed normally
        return;
    }
    
    const contractId = parseInt(contractIdInput.value);
    if (!contractId) {
        return;
    }
    
    let signatureData = null;
    let canvas = null;
    let ctx = null;
    let isDrawing = false;
    let lastX = 0;
    let lastY = 0;
    let hasDrawn = false;
    let canvasInitialized = false;
    let isSubmitting = false;
    
    const modal = document.getElementById('eventSignatureModal');
    if (!modal) {
        // Modal not present, no signature needed
        return;
    }
    
    // Initialize canvas
    function initCanvas() {
        canvas = document.getElementById('event-signature-canvas');
        if (!canvas) {
            return;
        }
        
        ctx = canvas.getContext('2d');
        ctx.strokeStyle = '#000000';
        ctx.lineWidth = 2;
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';
        
        // Mouse events
        canvas.addEventListener('mousedown', startDrawing);
        canvas.addEventListener('mousemove', draw);
        canvas.addEventListener('mouseup', stopDrawing);
        canvas.addEventListener('mouseout', stopDrawing);
        
        // Touch events
        canvas.addEventListener('touchstart', handleTouchStart);
        canvas.addEventListener('touchmove', handleTouchMove);
        canvas.addEventListener('touchend', handleTouchEnd);
        canvas.addEventListener('touchcancel', handleTouchEnd);
    }
    
    function getCanvasCoordinates(clientX, clientY) {
        const rect = canvas.getBoundingClientRect();
        const scaleX = canvas.width / rect.width;
        const scaleY = canvas.height / rect.height;
        
        return {
            x: (clientX - rect.left) * scaleX,
            y: (clientY - rect.top) * scaleY
        };
    }
    
    function startDrawing(e) {
        isDrawing = true;
        const coords = getCanvasCoordinates(e.clientX, e.clientY);
        lastX = coords.x;
        lastY = coords.y;
        hasDrawn = true;
    }
    
    function draw(e) {
        if (!isDrawing) return;
        
        const coords = getCanvasCoordinates(e.clientX, e.clientY);
        
        ctx.beginPath();
        ctx.moveTo(lastX, lastY);
        ctx.lineTo(coords.x, coords.y);
        ctx.stroke();
        
        lastX = coords.x;
        lastY = coords.y;
    }
    
    function stopDrawing() {
        isDrawing = false;
    }
    
    function handleTouchStart(e) {
        e.preventDefault();
        const touch = e.touches[0];
        const coords = getCanvasCoordinates(touch.clientX, touch.clientY);
        
        isDrawing = true;
        lastX = coords.x;
        lastY = coords.y;
        hasDrawn = true;
        
        // Draw a small dot at the starting point
        ctx.beginPath();
        ctx.arc(coords.x, coords.y, 0.5, 0, 2 * Math.PI);
        ctx.fill();
    }
    
    function handleTouchMove(e) {
        if (!isDrawing) return;
        e.preventDefault();
        
        const touch = e.touches[0];
        const coords = getCanvasCoordinates(touch.clientX, touch.clientY);
        
        ctx.beginPath();
        ctx.moveTo(lastX, lastY);
        ctx.lineTo(coords.x, coords.y);
        ctx.stroke();
        
        lastX = coords.x;
        lastY = coords.y;
    }
    
    function handleTouchEnd(e) {
        e.preventDefault();
        stopDrawing();
    }
    
    function clearSignature() {
        if (canvas && ctx) {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            hasDrawn = false;
            signatureData = null;
        }
    }
    
    function showSignatureModal() {
        // Initialize canvas only once
        if (!canvasInitialized) {
            initCanvas();
            canvasInitialized = true;
        } else {
            clearSignature();
        }
        
        // Show modal
        modal.classList.add('show');
        modal.style.display = 'block';
        document.body.classList.add('modal-open');
    }
    
    function hideSignatureModal() {
        if (modal) {
            modal.classList.remove('show');
            modal.style.display = 'none';
            document.body.classList.remove('modal-open');
        }
    }
    
    // Bind modal events
    if (!modal.dataset.initialized) {
        const closeButtons = modal.querySelectorAll('[data-bs-dismiss="modal"]');
        closeButtons.forEach(btn => {
            btn.addEventListener('click', hideSignatureModal);
        });
        
        const clearBtn = modal.querySelector('.event-clear-signature');
        if (clearBtn) {
            clearBtn.addEventListener('click', clearSignature);
        }
        
        const confirmBtn = modal.querySelector('.event-confirm-signature');
        if (confirmBtn) {
            confirmBtn.addEventListener('click', confirmSignature);
        }
        
        // Close modal when clicking outside
        modal.addEventListener('click', function(e) {
            if (e.target === modal) {
                hideSignatureModal();
            }
        });
        
        modal.dataset.initialized = 'true';
    }
    
    function confirmSignature() {
        if (!hasDrawn) {
            alert('Please provide a signature before confirming.');
            return;
        }
        
        // Get signature as base64
        signatureData = canvas.toDataURL('image/png').replace(/^data:image\/png;base64,/, '');
        
        // Disable confirm button
        const confirmBtn = modal.querySelector('.event-confirm-signature');
        if (confirmBtn) {
            confirmBtn.disabled = true;
            confirmBtn.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Saving...';
        }
        
        // Save signature to contract via AJAX
        // Use Odoo's JSON-RPC format
        const rpcPayload = {
            jsonrpc: '2.0',
            method: 'call',
            params: {
                contract_id: contractId,
                signature_data: signatureData
            },
            id: Math.floor(Math.random() * 1000000000)
        };
        
        fetch('/popcorn/contract/sign_from_event', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest',
            },
            credentials: 'same-origin',
            body: JSON.stringify(rpcPayload)
        })
        .then(response => response.json())
        .then(result => {
            const response = result.result || result;
            if (response && response.success) {
                hideSignatureModal();
                submitRegistrationForm();
            } else {
                alert('Error signing contract: ' + (response?.error || result.error?.message || 'Unknown error'));
                if (confirmBtn) {
                    confirmBtn.disabled = false;
                    confirmBtn.innerHTML = '<i class="fa fa-check"></i> <span t-translation="on">Confirm Signature</span>';
                }
            }
        })
        .catch(error => {
            console.error('Error signing contract:', error);
            alert('An error occurred while saving the signature. Please try again.');
            if (confirmBtn) {
                confirmBtn.disabled = false;
                confirmBtn.innerHTML = '<i class="fa fa-check"></i> <span t-translation="on">Confirm Signature</span>';
            }
        });
    }
    
    function submitRegistrationForm() {
        if (isSubmitting) {
            return;
        }
        
        isSubmitting = true;
        const submitBtn = document.getElementById('register-club-btn');
        if (submitBtn) {
            submitBtn.disabled = true;
            const loadingSpan = submitBtn.querySelector('.btn-loading');
            const textSpan = submitBtn.querySelector('.btn-text');
            if (loadingSpan) loadingSpan.style.display = 'inline';
            if (textSpan) textSpan.style.display = 'none';
        }
        
        // Submit the form
        registrationForm.submit();
    }
    
    // Intercept form submission
    registrationForm.addEventListener('submit', function(e) {
        // If signature is needed and not yet signed, show modal and prevent submission
        if (!signatureData) {
            e.preventDefault();
            showSignatureModal();
            return false;
        }
        
        // Signature already saved, allow normal submission
    });
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupEventSignatureFunctionality);
} else {
    setupEventSignatureFunctionality();
}

// Also try on page load for dynamic content
window.addEventListener('load', function() {
    setTimeout(setupEventSignatureFunctionality, 100);
});
