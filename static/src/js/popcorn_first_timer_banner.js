// First-Timer Grace Period Countdown Banner
function setupFirstTimerBanners() {
    var banners = document.querySelectorAll('.popcorn-first-timer-banner');
    banners.forEach(function(banner) {
        var countdownEl = banner.querySelector('.popcorn-first-timer-countdown');
        if (!countdownEl) return;

        var pendingDateStr = banner.dataset.pendingDate;
        if (!pendingDateStr) return;

        // Countdown target: midnight (end of day) of the pending date
        var parts = pendingDateStr.split('-');
        var midnight = new Date(
            parseInt(parts[0]),
            parseInt(parts[1]) - 1,
            parseInt(parts[2]),
            23, 59, 59, 999
        );

        function updateTimer() {
            var now = new Date();
            var timeLeft = midnight - now;

            if (timeLeft <= 0) {
                window.location.reload();
                return;
            }

            var hours = Math.floor(timeLeft / (1000 * 60 * 60));
            var minutes = Math.floor((timeLeft % (1000 * 60 * 60)) / (1000 * 60));
            var seconds = Math.floor((timeLeft % (1000 * 60)) / 1000);

            countdownEl.textContent = hours + 'h ' + minutes + 'm ' + seconds + 's';
        }

        updateTimer();
        setInterval(updateTimer, 1000);
    });
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupFirstTimerBanners);
} else {
    setupFirstTimerBanners();
}

window.addEventListener('load', function() {
    setTimeout(setupFirstTimerBanners, 200);
});
