/**
 * Popcorn Sticky Footer Navigation JavaScript
 * Handles active tab highlighting and navigation state
 */

odoo.define('popcorn.sticky_footer', [], function () {
    'use strict';

    // Simple jQuery-based implementation for frontend
    $(document).ready(function() {
        function initializeStickyFooter() {
            var $stickyFooter = $('.sticky-footer');
            if (!$stickyFooter.length) return;

            function highlightActiveTab() {
                var currentPath = normalizePath(window.location.pathname);
                
                // Remove any existing active classes
                $stickyFooter.find('.nav-btn.active').removeClass('active');
                
                // Find matching navigation items
                $stickyFooter.find('.nav-btn').each(function () {
                    var $btn = $(this);
                    var dataPaths = $btn.attr('data-paths') || $btn.attr('data-path') || '';
                    var paths = dataPaths.split(',').map(function (path) {
                        return normalizePath(path.trim());
                    });
                    
                    var isActive = paths.some(function (path) {
                        if (path === '/') {
                            return currentPath === '/';
                        }
                        return currentPath === path || currentPath.startsWith(path + '/');
                    });
                    
                    if (isActive) {
                        $btn.addClass('active');
                    }
                });
            }

            function normalizePath(path) {
                try {
                    path = path.split('?')[0].split('#')[0];
                    path = path.replace(/\/+$/, '') || '/';
                    path = path.replace(/^\/(?:[a-z]{2}(?:_[A-Z]{2})?)\//, '/');
                    return path || '/';
                } catch (e) {
                    return '/';
                }
            }

            // Handle navigation button clicks
            $stickyFooter.on('click', '.nav-btn', function(ev) {
                var $btn = $(this);
                var href = $btn.attr('href');
                
                // Update active state immediately
                $stickyFooter.find('.nav-btn.active').removeClass('active');
                $btn.addClass('active');
                
                // Let browser handle navigation
                if (href && (href.startsWith('http') || href.startsWith('mailto:') || href.startsWith('tel:'))) {
                    return;
                }
            });

            // Setup resize handler
            var resizeTimer;
            $(window).on('resize.popcorn_sticky_footer', function () {
                clearTimeout(resizeTimer);
                resizeTimer = setTimeout(function () {
                    highlightActiveTab();
                }, 250);
            });

            // Initial highlight
            highlightActiveTab();
        }

        // Initialize when DOM is ready
        initializeStickyFooter();

        // Re-initialize on page changes (for SPA-like behavior)
        $(document).on('DOMContentLoaded', function () {
            initializeStickyFooter();
        });
    });
});