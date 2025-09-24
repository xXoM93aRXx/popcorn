odoo.define('popcorn.language_switcher', [], function () {
    'use strict';

    // Simple jQuery-based implementation for frontend
    $(document).ready(function() {
        function initializeLanguageSwitcher() {
            var $switcher = $('#popcorn-language-switcher');
            if (!$switcher.length) return;

            // Remove existing event listeners to prevent duplicates
            $switcher.find('.popcorn-lang-option').off('click.popcorn');
            $switcher.find('.popcorn-lang-dropdown').off('mouseenter.popcorn mouseleave.popcorn');

            // Add click animation to language options
            $switcher.find('.popcorn-lang-option').on('click.popcorn', function(e) {
                addSwitchFeedback($(this));
                
                // Trigger custom event for other components to listen to
                $(document).trigger('popcorn:language-switching', {
                    targetLang: $(this).data('lang')
                });
            });
            
            // Add hover effects to dropdown
            $switcher.find('.popcorn-lang-dropdown').on('mouseenter.popcorn', function() {
                $(this).addClass('popcorn-dropdown-hover');
            }).on('mouseleave.popcorn', function() {
                $(this).removeClass('popcorn-dropdown-hover');
            });
        }

        function addSwitchFeedback($element) {
            $element.addClass('popcorn-switching');
            
            setTimeout(function () {
                $element.removeClass('popcorn-switching');
            }, 300);
        }

        // Initialize when DOM is ready
        initializeLanguageSwitcher();
        
        // Re-initialize on window load (for dynamic content)
        $(window).on('load', function() {
            setTimeout(function() {
                initializeLanguageSwitcher();
            }, 200);
        });
        
        // Re-initialize when new content is loaded (for language switches)
        $(document).on('DOMNodeInserted', function() {
            setTimeout(function() {
                initializeLanguageSwitcher();
            }, 100);
        });
    });
});
