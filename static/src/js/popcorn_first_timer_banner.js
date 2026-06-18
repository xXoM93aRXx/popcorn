// First-Timer Grace Period Countdown Banner
function setupFirstTimerBanners() {
    var banners = document.querySelectorAll('.popcorn-first-timer-banner');
    banners.forEach(function(banner) {
        // Guard against double-setup
        if (banner.dataset.countdownInitialized) return;
        banner.dataset.countdownInitialized = '1';

        var countdownEl = banner.querySelector('.popcorn-first-timer-countdown');
        if (!countdownEl) return;

        var pendingDateStr = banner.dataset.pendingDate;
        if (!pendingDateStr) return;

        var parts = pendingDateStr.split('-');
        var midnight = new Date(
            parseInt(parts[0]),
            parseInt(parts[1]) - 1,
            parseInt(parts[2]),
            23, 59, 59, 999
        );

        // If already past midnight, hide immediately — don't reload
        if (midnight - new Date() <= 0) {
            banner.style.display = 'none';
            return;
        }

        function updateTimer() {
            var timeLeft = midnight - new Date();

            if (timeLeft <= 0) {
                banner.style.display = 'none';
                clearInterval(intervalId);
                return;
            }

            var hours = Math.floor(timeLeft / (1000 * 60 * 60));
            var minutes = Math.floor((timeLeft % (1000 * 60 * 60)) / (1000 * 60));
            var seconds = Math.floor((timeLeft % (1000 * 60)) / 1000);

            countdownEl.textContent = hours + 'h ' + minutes + 'm ' + seconds + 's';
        }

        updateTimer();
        var intervalId = setInterval(updateTimer, 1000);
    });
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupFirstTimerBanners);
} else {
    setupFirstTimerBanners();
}

window.addEventListener('load', setupFirstTimerBanners);
