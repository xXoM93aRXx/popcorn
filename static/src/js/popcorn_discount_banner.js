// Public Discount Banner Countdown Timer
function setupDiscountBanners() {
    const banners = document.querySelectorAll('.popcorn-discount-banner');
    banners.forEach(function(banner) {
        const textEl = banner.querySelector('.popcorn-discount-banner-text');
        if (!textEl) return;

        const dateToStr = banner.dataset.discountDateTo;
        const templateText = banner.dataset.bannerText;

        if (!templateText || !templateText.includes('{timer}')) return;
        if (!dateToStr) return;

        // Parse date_to as end of that day in local time
        const parts = dateToStr.split('-');
        const expiration = new Date(
            parseInt(parts[0]),
            parseInt(parts[1]) - 1,
            parseInt(parts[2]),
            23, 59, 59, 999
        );

        // If already expired at page load, hide immediately — don't reload
        if (expiration - new Date() <= 0) {
            banner.style.display = 'none';
            return;
        }

        function updateTimer() {
            const now = new Date();
            const timeLeft = expiration - now;

            if (timeLeft <= 0) {
                banner.style.display = 'none';
                clearInterval(intervalId);
                return;
            }

            const days = Math.floor(timeLeft / (1000 * 60 * 60 * 24));
            const hours = Math.floor((timeLeft % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
            const minutes = Math.floor((timeLeft % (1000 * 60 * 60)) / (1000 * 60));
            const seconds = Math.floor((timeLeft % (1000 * 60)) / 1000);

            let countdown = '';
            if (days > 0) {
                countdown = days + 'd ' + hours + 'h ' + minutes + 'm ' + seconds + 's';
            } else if (hours > 0) {
                countdown = hours + 'h ' + minutes + 'm ' + seconds + 's';
            } else if (minutes > 0) {
                countdown = minutes + 'm ' + seconds + 's';
            } else {
                countdown = seconds + 's';
            }

            textEl.innerHTML = templateText.replace(/\{timer\}/g, '<strong>' + countdown + '</strong>');
        }

        updateTimer();
        const intervalId = setInterval(updateTimer, 1000);
        textEl.dataset.countdownInterval = intervalId;
    });
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupDiscountBanners);
} else {
    setupDiscountBanners();
}

window.addEventListener('load', function() {
    setTimeout(setupDiscountBanners, 200);
});
