odoo.define('popcorn.badge_animation', [], function () {
    'use strict';

    // ─── Confetti ────────────────────────────────────────────────────────────────

    var CONFETTI_COLORS = [
        '#e63946', '#ff6b6b', '#fff', '#ff8fa3',
        '#c9184a', '#ffb3c1', '#ff4d6d', '#ff0a54',
    ];

    function launchConfetti() {
        var canvas = document.createElement('canvas');
        canvas.className = 'popcorn-badge-confetti-canvas';
        canvas.width  = window.innerWidth;
        canvas.height = window.innerHeight;
        document.body.appendChild(canvas);
        var ctx = canvas.getContext('2d');

        var particles = [];
        var count = 120;
        var cx = canvas.width  / 2;
        var cy = canvas.height / 2;

        for (var i = 0; i < count; i++) {
            var angle = (Math.random() * Math.PI * 2);
            var speed = 4 + Math.random() * 8;
            particles.push({
                x:    cx,
                y:    cy,
                vx:   Math.cos(angle) * speed,
                vy:   Math.sin(angle) * speed - (4 + Math.random() * 4),
                w:    6  + Math.random() * 6,
                h:    10 + Math.random() * 6,
                rot:  Math.random() * 360,
                drot: (Math.random() - 0.5) * 12,
                color: CONFETTI_COLORS[Math.floor(Math.random() * CONFETTI_COLORS.length)],
                alpha: 1,
            });
        }

        var start = null;
        var duration = 2600;

        function step(ts) {
            if (!start) start = ts;
            var elapsed = ts - start;
            ctx.clearRect(0, 0, canvas.width, canvas.height);

            particles.forEach(function (p) {
                p.x   += p.vx;
                p.y   += p.vy;
                p.vy  += 0.25;           // gravity
                p.vx  *= 0.99;           // air drag
                p.rot += p.drot;
                p.alpha = Math.max(0, 1 - elapsed / duration);

                ctx.save();
                ctx.globalAlpha = p.alpha;
                ctx.translate(p.x, p.y);
                ctx.rotate((p.rot * Math.PI) / 180);
                ctx.fillStyle = p.color;
                ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h);
                ctx.restore();
            });

            if (elapsed < duration) {
                requestAnimationFrame(step);
            } else {
                canvas.remove();
            }
        }

        requestAnimationFrame(step);
    }

    // ─── Sparkles ────────────────────────────────────────────────────────────────

    var SPARKLE_COLORS = ['#e63946', '#ff6b6b', '#fff', '#ff8fa3', '#c9184a', '#ffb3c1'];

    function launchSparkles(popup) {
        // Sparkles radiate from the image centre — offset from popup top
        var cx = popup.offsetWidth / 2;
        var cy = 40 + 90; // label height approx + half of 180px image

        for (var i = 0; i < 18; i++) {
            var angle  = (i / 18) * Math.PI * 2;
            var dist   = 80 + Math.random() * 80;
            var sx     = Math.round(Math.cos(angle) * dist);
            var sy     = Math.round(Math.sin(angle) * dist);

            var sp = document.createElement('div');
            sp.className = 'popcorn-badge-sparkle';
            sp.style.left   = (cx - 4) + 'px';
            sp.style.top    = (cy - 4) + 'px';
            sp.style.background = SPARKLE_COLORS[i % SPARKLE_COLORS.length];
            sp.style.setProperty('--sx', sx + 'px');
            sp.style.setProperty('--sy', sy + 'px');
            sp.style.animationDelay = (Math.random() * 0.12) + 's';
            popup.appendChild(sp);

            sp.addEventListener('animationend', function () { this.remove(); });
        }
    }

    function launchRings(popup) {
        [0, 220].forEach(function (delay) {
            var ring = document.createElement('div');
            ring.className = 'popcorn-badge-ring';
            // Centre vertically on the image (label ~32px + half image 90px)
            ring.style.top  = (32 + 40 + 90) + 'px';  // padding-top + label + half-img
            ring.style.animationDelay = delay + 'ms';
            popup.appendChild(ring);
            ring.addEventListener('animationend', function () { this.remove(); });
        });
    }

    // ─── Popup ───────────────────────────────────────────────────────────────────

    var SPIN_DURATION = 2200; // ms — must match CSS animation duration

    function showBadgePopup(badge, onDone) {
        // Overlay
        var overlay = document.createElement('div');
        overlay.className = 'popcorn-badge-overlay';

        // Popup
        var popup = document.createElement('div');
        popup.className = 'popcorn-badge-popup';

        // Label
        var label = document.createElement('div');
        label.className = 'popcorn-badge-popup-label';
        label.textContent = '🏅 Badge Unlocked!';
        popup.appendChild(label);

        // Image wrapper
        var imgWrap = document.createElement('div');
        imgWrap.className = 'popcorn-badge-popup-img-wrap';

        if (badge.image_url) {
            var img = document.createElement('img');
            img.className = 'popcorn-badge-popup-img';
            img.src = badge.image_url;
            img.alt = badge.name;

            // After spin settles: switch to gentle breathe animation
            img.addEventListener('animationend', function () {
                img.style.animation = 'badgeBreathe 2.4s ease-in-out infinite';
            });

            // Shimmer sweep
            var shimmer = document.createElement('div');
            shimmer.className = 'popcorn-badge-shimmer';
            imgWrap.appendChild(shimmer);

            imgWrap.appendChild(img);
        }
        popup.appendChild(imgWrap);

        // Badge name
        var name = document.createElement('div');
        name.className = 'popcorn-badge-popup-name';
        name.textContent = badge.name;
        popup.appendChild(name);

        // Sub-text
        var sub = document.createElement('div');
        sub.className = 'popcorn-badge-popup-sub';
        sub.textContent = 'You\'ve earned this badge. Keep it up!';
        popup.appendChild(sub);

        // Button
        var btn = document.createElement('button');
        btn.className = 'popcorn-badge-popup-btn';
        btn.textContent = 'Awesome!';
        btn.addEventListener('click', function () {
            overlay.remove();
            onDone();
        });
        popup.appendChild(btn);

        overlay.appendChild(popup);
        document.body.appendChild(overlay);

        // Confetti mid-spin
        setTimeout(launchConfetti, SPIN_DURATION * 0.45);

        // Sparkles + rings as spin settles
        setTimeout(function () {
            launchSparkles(popup);
            launchRings(popup);
        }, SPIN_DURATION * 0.85);
    }

    function showBadgesSequentially(badges) {
        if (!badges || badges.length === 0) return;
        var index = 0;

        function next() {
            if (index >= badges.length) return;
            showBadgePopup(badges[index], function () {
                index++;
                // Small pause between badges if there are multiple
                setTimeout(next, 400);
            });
        }

        next();
    }

    // ─── Page-load check ─────────────────────────────────────────────────────────

    function checkNewBadges() {
        fetch('/popcorn/badges/check-new', {
            method: 'GET',
            credentials: 'same-origin',
        })
        .then(function (resp) {
            if (!resp.ok) {
                console.warn('[BadgeAnim] check-new returned', resp.status);
                return null;
            }
            return resp.json();
        })
        .then(function (data) {
            if (!data) return;
            console.log('[BadgeAnim] new badges:', data.badges);
            if (data.badges && data.badges.length > 0) {
                setTimeout(function () {
                    showBadgesSequentially(data.badges);
                }, 800);
            }
        })
        .catch(function (err) {
            console.warn('[BadgeAnim] fetch error:', err);
        });
    }

    // Run immediately — Odoo loads assets at the bottom of <body> so the DOM
    // is already ready.  Fall back to DOMContentLoaded only if somehow not yet loaded.
    function init() {
        // Guard: only run on portal pages.  Odoo adds o_portal to <body> on
        // all portal / /my/* pages, and also adds data-logged-in on the html tag.
        var isPortal = document.body.classList.contains('o_portal');
        var isLoggedIn = document.documentElement.dataset.loggedIn === '1'
                      || document.querySelector('a[href="/web/login"]') === null;

        if (isPortal || isLoggedIn) {
            checkNewBadges();
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
});
