// Frontend signature functionality for membership checkout

function setupSignatureFunctionality() {
    // Only activate on membership checkout page (not event checkout)
    const checkoutForm = document.querySelector('.popcorn-membership-checkout-form');
    
    if (!checkoutForm) {
        return;
    }
    
    const termsCheckbox = document.getElementById('terms_accepted');
    
    if (!termsCheckbox) {
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
    
    // Prevent default checkbox behavior
    termsCheckbox.addEventListener('click', function(e) {
        if (!signatureData) {
            e.preventDefault();
            this.checked = false;
            showSignatureModal();
        }
    });
    
    function showSignatureModal() {
        const modal = document.getElementById('signatureModal');
        if (!modal) return;
        
        // Initialize canvas only once
        if (!canvasInitialized) {
            initCanvas();
            canvasInitialized = true;
        } else {
            // Just clear the canvas if already initialized
            clearSignature();
        }
        
        // Bind modal events (only once)
        if (!modal.dataset.initialized) {
            const closeButtons = modal.querySelectorAll('[data-bs-dismiss="modal"]');
            closeButtons.forEach(btn => {
                btn.addEventListener('click', hideSignatureModal);
            });
            
            modal.querySelector('.popcorn-clear-signature').addEventListener('click', clearSignature);
            modal.querySelector('.popcorn-confirm-signature').addEventListener('click', confirmSignature);
            
            // Close modal when clicking outside
            modal.addEventListener('click', function(e) {
                if (e.target === modal) {
                    hideSignatureModal();
                }
            });
            
            modal.dataset.initialized = 'true';
        }
        
        // Show modal
        modal.classList.add('show');
        modal.style.display = 'block';
        document.body.classList.add('modal-open');
    }
    
    function hideSignatureModal() {
        const modal = document.getElementById('signatureModal');
        if (modal) {
            modal.classList.remove('show');
            modal.style.display = 'none';
            document.body.classList.remove('modal-open');
        }
    }
    
    function initCanvas() {
        canvas = document.getElementById('popcorn-signature-canvas');
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
        
        // Start new drawing stroke
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
        }
    }
    
    function confirmSignature() {
        if (!hasDrawn) {
            alert('Please provide a signature before confirming.');
            return;
        }
        
        // Get signature as base64
        signatureData = canvas.toDataURL('image/png').replace(/^data:image\/png;base64,/, '');
        
        // Add hidden input to form
        let signatureInput = document.getElementById('customer_signature');
        if (!signatureInput) {
            signatureInput = document.createElement('input');
            signatureInput.type = 'hidden';
            signatureInput.id = 'customer_signature';
            signatureInput.name = 'customer_signature';
            checkoutForm.appendChild(signatureInput);
        }
        signatureInput.value = signatureData;
        
        // Check the terms checkbox
        termsCheckbox.checked = true;
        
        // Add visual indicator
        const checkboxLabel = document.querySelector('label[for="terms_accepted"]');
        if (checkboxLabel && !checkboxLabel.querySelector('.signature-indicator')) {
            checkboxLabel.insertAdjacentHTML('beforeend', ' <span class="signature-indicator"><i class="fa fa-check-circle text-success"></i> Signed</span>');
        }
        
        // Close modal
        hideSignatureModal();
    }
    
    // Form validation
    checkoutForm.addEventListener('submit', function(e) {
        if (!signatureData) {
            e.preventDefault();
            alert('Please sign the terms and conditions before submitting.');
            termsCheckbox.checked = false;
            return false;
        }
    });
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupSignatureFunctionality);
} else {
    setupSignatureFunctionality();
}

// Also try on page load for dynamic content
window.addEventListener('load', function() {
    setTimeout(setupSignatureFunctionality, 100);
});
