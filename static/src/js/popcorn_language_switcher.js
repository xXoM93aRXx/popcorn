odoo.define('popcorn.language_switcher', [], function () {
    'use strict';

    // Simple jQuery-based implementation for frontend
    $(document).ready(function() {
        function initializeLanguageSwitcher() {
            var $switcher = $('#popcorn-language-switcher');
            if (!$switcher.length) return;

            // Add click animation to language options
            $switcher.find('.popcorn-lang-option').on('click', function(e) {
                addSwitchFeedback($(this));
            });
            
            // Add hover effects to dropdown
            $switcher.find('.popcorn-lang-dropdown').on('mouseenter', function() {
                $(this).addClass('popcorn-dropdown-hover');
            }).on('mouseleave', function() {
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
    });
});
