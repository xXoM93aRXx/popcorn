// Renewal Banner Countdown Timer
function setupRenewalCountdown() {
    const renewalBanner = document.querySelector('.popcorn-renewal-banner-sticky');
    
    if (!renewalBanner) {
        console.log('No renewal banner found, skipping countdown setup');
        return;
    }
    
    console.log('Setting up renewal countdown timer...');
    
    const renewalText = renewalBanner.querySelector('.popcorn-renewal-text');
    if (!renewalText) {
        console.log('Renewal text element not found');
        return;
    }
    
    // Get data attributes
    const daysLeft = parseInt(renewalBanner.dataset.daysLeft) || 0;
    const pointsLeft = parseInt(renewalBanner.dataset.pointsLeft) || 0;
    const templateText = renewalBanner.dataset.templateText || '';
    const userName = renewalBanner.dataset.userName || '';
    
    console.log('Banner data:', { daysLeft, pointsLeft, templateText, userName });
    
    if (daysLeft > 0 && templateText.includes('{days_left}')) {
        // Time-based countdown (for Gold/Experience cards)
        setupTimeBasedCountdown(renewalText, templateText, daysLeft, userName);
    } else if (pointsLeft > 0 && templateText.includes('{points_left}')) {
        // Points-based countdown (for Freedom card)
        // Points don't tick down automatically, so just display the value
        console.log('Points-based renewal banner (no auto-countdown needed)');
        // Still need to replace {name} placeholder for points-based banners
        let processedText = templateText.replace(/\{points_left\}/g, pointsLeft);
        processedText = processedText.replace(/\{name\}/g, userName);
        renewalText.innerHTML = processedText;
    } else {
        console.log('No valid countdown data found');
    }
}

function setupTimeBasedCountdown(textElement, templateText, daysRemaining, userName) {
    console.log('Days remaining for renewal:', daysRemaining);
    
    // Calculate the exact expiration datetime
    // Assuming end of day for the expiration
    const now = new Date();
    const expirationDate = new Date();
    expirationDate.setDate(expirationDate.getDate() + daysRemaining);
    expirationDate.setHours(23, 59, 59, 999); // End of day
    
    // Function to update the countdown
    function updateCountdown() {
        const now = new Date();
        const timeLeft = expirationDate - now;
        
        if (timeLeft <= 0) {
            // Time's up - reload page to hide banner
            console.log('Renewal window expired, reloading...');
            window.location.reload();
            return;
        }
        
        // Calculate time components
        const days = Math.floor(timeLeft / (1000 * 60 * 60 * 24));
        const hours = Math.floor((timeLeft % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
        const minutes = Math.floor((timeLeft % (1000 * 60 * 60)) / (1000 * 60));
        const seconds = Math.floor((timeLeft % (1000 * 60)) / 1000);
        
        // Format the countdown string
        let countdownText = '';
        if (days > 0) {
            countdownText = `${days}d ${hours}h ${minutes}m ${seconds}s`;
        } else if (hours > 0) {
            countdownText = `${hours}h ${minutes}m ${seconds}s`;
        } else if (minutes > 0) {
            countdownText = `${minutes}m ${seconds}s`;
        } else {
            countdownText = `${seconds}s`;
        }
        
        // Replace the days_left placeholder with live countdown and name placeholder
        // Keep the original template structure but replace the values
        let updatedText = templateText.replace(/\{days_left\}/g, countdownText);
        updatedText = updatedText.replace(/\{name\}/g, userName);
        textElement.innerHTML = updatedText;
    }
    
    // Update immediately
    updateCountdown();
    
    // Update every second
    const intervalId = setInterval(updateCountdown, 1000);
    
    // Store interval ID in case we need to clear it
    textElement.dataset.countdownInterval = intervalId;
    
    console.log('Countdown timer started');
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupRenewalCountdown);
} else {
    setupRenewalCountdown();
}

// Also initialize when page loads dynamically
document.addEventListener('DOMContentLoaded', function() {
    setTimeout(setupRenewalCountdown, 100);
});

// Additional initialization for dynamic content loading
window.addEventListener('load', function() {
    setTimeout(setupRenewalCountdown, 200);
});

