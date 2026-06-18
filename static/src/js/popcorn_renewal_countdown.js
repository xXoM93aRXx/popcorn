// Renewal Banner Countdown Timer
function setupRenewalCountdown() {
    const renewalBanner = document.querySelector('.popcorn-renewal-banner-sticky');
    if (!renewalBanner) return;

    // Guard against double-setup
    if (renewalBanner.dataset.countdownInitialized) return;
    renewalBanner.dataset.countdownInitialized = '1';

    const renewalText = renewalBanner.querySelector('.popcorn-renewal-text');
    if (!renewalText) return;

    const daysLeft = parseInt(renewalBanner.dataset.daysLeft) || 0;
    const pointsLeft = parseInt(renewalBanner.dataset.pointsLeft) || 0;
    const templateText = renewalBanner.dataset.templateText || '';
    const userName = renewalBanner.dataset.userName || '';

    if (daysLeft > 0 && templateText.includes('{days_left}')) {
        setupTimeBasedCountdown(renewalText, templateText, daysLeft, userName);
    } else if (pointsLeft > 0 && templateText.includes('{points_left}')) {
        let processedText = templateText.replace(/\{points_left\}/g, pointsLeft);
        processedText = processedText.replace(/\{name\}/g, userName);
        renewalText.innerHTML = processedText;
    }
}

function setupTimeBasedCountdown(textElement, templateText, daysRemaining, userName) {
    const expirationDate = new Date();
    expirationDate.setDate(expirationDate.getDate() + daysRemaining);
    expirationDate.setHours(23, 59, 59, 999);

    function updateCountdown() {
        const timeLeft = expirationDate - new Date();

        if (timeLeft <= 0) {
            const banner = textElement.closest('.popcorn-renewal-banner-sticky');
            if (banner) banner.style.display = 'none';
            clearInterval(intervalId);
            return;
        }

        const days = Math.floor(timeLeft / (1000 * 60 * 60 * 24));
        const hours = Math.floor((timeLeft % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
        const minutes = Math.floor((timeLeft % (1000 * 60 * 60)) / (1000 * 60));
        const seconds = Math.floor((timeLeft % (1000 * 60)) / 1000);

        let countdownText = '';
        if (days > 0) {
            countdownText = days + 'd ' + hours + 'h ' + minutes + 'm ' + seconds + 's';
        } else if (hours > 0) {
            countdownText = hours + 'h ' + minutes + 'm ' + seconds + 's';
        } else if (minutes > 0) {
            countdownText = minutes + 'm ' + seconds + 's';
        } else {
            countdownText = seconds + 's';
        }

        let updatedText = templateText.replace(/\{days_left\}/g, countdownText);
        updatedText = updatedText.replace(/\{name\}/g, userName);
        textElement.innerHTML = updatedText;
    }

    updateCountdown();
    const intervalId = setInterval(updateCountdown, 1000);
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupRenewalCountdown);
} else {
    setupRenewalCountdown();
}

window.addEventListener('load', setupRenewalCountdown);
