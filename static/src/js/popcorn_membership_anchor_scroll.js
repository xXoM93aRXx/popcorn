odoo.define('popcorn.membership_anchor_scroll', [], function () {
    'use strict';

    // Membership Anchor Scroll Functionality
    $(document).ready(function() {
        function scrollToAnchor(hash) {
            // Check if hash is valid (not empty or just '#')
            if (!hash || hash === '#' || hash.length <= 1) {
                return;
            }
            
            const target = document.querySelector(hash);
            if (target) {
                // Get the exact position of the target element
                const rect = target.getBoundingClientRect();
                const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
                const targetPosition = rect.top + scrollTop - 100; // 100px offset from top
                
                // Scroll to the exact position
                window.scrollTo({
                    top: targetPosition,
                    behavior: 'smooth'
                });
            }
        }

        function initializeAnchorScroll() {
            if (window.location.hash && window.location.hash !== '#') {
                // Wait for elements to be available
                setTimeout(function() {
                    scrollToAnchor(window.location.hash);
                }, 1000);
            }
        }

        // Prevent default browser anchor scrolling
        $(document).on('click', 'a[href*="#"]', function(e) {
            const href = $(this).attr('href');
            if (href.startsWith('#') && href !== '#') {
                e.preventDefault();
                e.stopPropagation();
                const hash = href;
                // Update URL without triggering browser scroll
                history.pushState(null, null, hash);
                // Use our custom scroll
                setTimeout(function() {
                    scrollToAnchor(hash);
                }, 100);
            }
        });

        // Handle hashchange event with our custom scroll
        $(window).on('hashchange', function(e) {
            if (window.location.hash && window.location.hash !== '#') {
                setTimeout(function() {
                    scrollToAnchor(window.location.hash);
                }, 100);
            }
        });

        // Initialize when DOM is ready
        initializeAnchorScroll();
        
        // Re-initialize on window load (for dynamic content)
        $(window).on('load', function() {
            setTimeout(function() {
                initializeAnchorScroll();
            }, 500);
        });
        
        // Re-initialize when language switcher is clicked
        $(document).on('click', '.popcorn-lang-option', function() {
            setTimeout(function() {
                initializeAnchorScroll();
            }, 1500);
        });
        
        // Listen for custom language switching event
        $(document).on('popcorn:language-switching', function(e, data) {
            setTimeout(function() {
                initializeAnchorScroll();
            }, 1500);
        });
        
        // Additional check for when page content is fully loaded
        var checkInterval = setInterval(function() {
            if ($('.popcorn-membership-plans-page').length && $('.popcorn-membership-plan-card[id]').length) {
                initializeAnchorScroll();
                clearInterval(checkInterval);
            }
        }, 500);
        
        // Clear interval after 10 seconds to prevent infinite checking
        setTimeout(function() {
            clearInterval(checkInterval);
        }, 10000);
    });
});
