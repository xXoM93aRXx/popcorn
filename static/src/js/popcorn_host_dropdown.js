odoo.define('popcorn.host_dropdown', [], function () {
    'use strict';

    // Host Dropdown Functionality
    $(document).ready(function() {
        function initializeHostDropdowns() {
            // Initialize for both hosts page and event description page
            if (!$('.popcorn-hosts-page').length && !$('.popcorn-event-host-section').length) {
                return;
            }
            
            // Wait a bit for elements to be available (especially after language switch)
            setTimeout(function() {
                // Set initial state - all dropdowns closed
                $('.popcorn-hosts-dropdown, .popcorn-event-host-dropdown').removeClass('open');
                $('.popcorn-section-header, .popcorn-event-host-header').removeClass('popcorn-section-open');
                
                // Remove any existing event listeners first
                $('.popcorn-section-header, .popcorn-event-host-header').off('click.popcorn');
                
                // Add click event listeners to section headers
                $('.popcorn-section-header, .popcorn-event-host-header').on('click.popcorn', function(e) {
                    e.preventDefault();
                    e.stopPropagation();
                    
                    var sectionId = $(this).data('target');
                    if (sectionId) {
                        toggleSection(sectionId);
                    }
                });
            }, 100);
        }

        function toggleSection(sectionId) {
            // Try multiple times to find elements (for language switch timing issues)
            var attempts = 0;
            var maxAttempts = 5;
            
            function findElements() {
                var $dropdown = $('#' + sectionId);
                var $sectionHeader = $('[data-target="' + sectionId + '"]');
                
                if ($dropdown.length && $sectionHeader.length) {
                    performToggle($dropdown, $sectionHeader);
                } else if (attempts < maxAttempts) {
                    attempts++;
                    setTimeout(findElements, 200);
                }
            }
            
            function performToggle($dropdown, $sectionHeader) {
                if ($dropdown.hasClass('open')) {
                    // Close the dropdown
                    $dropdown.removeClass('open');
                    $sectionHeader.removeClass('popcorn-section-open');
                } else {
                    // Close all other dropdowns first
                    $('.popcorn-hosts-dropdown, .popcorn-event-host-dropdown').removeClass('open');
                    $('.popcorn-section-header, .popcorn-event-host-header').removeClass('popcorn-section-open');
                    
                    // Open the selected dropdown
                    $dropdown.addClass('open');
                    $sectionHeader.addClass('popcorn-section-open');
                }
            }
            
            // Start the element finding process
            findElements();
        }

        // Make toggleSection globally available
        window.toggleSection = toggleSection;

        // Initialize when DOM is ready
        initializeHostDropdowns();
        
        // Direct fallback event listener for event host bio
        $(document).on('click', '.popcorn-event-host-header', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            var $header = $(this);
            var $preview = $header.find('.popcorn-host-preview');
            var $fullBio = $header.find('.popcorn-host-full-bio');
            
            if ($preview.is(':visible')) {
                // Show full bio, hide preview
                $preview.hide();
                $fullBio.show();
                $header.addClass('popcorn-section-open');
            } else {
                // Show preview, hide full bio
                $fullBio.hide();
                $preview.show();
                $header.removeClass('popcorn-section-open');
            }
        });
        
        // Event listener for event description dropdown
        $(document).on('click', '.popcorn-event-description-header', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            var $header = $(this);
            var $card = $header.closest('.popcorn-event-description-card');
            var $preview = $card.find('.popcorn-event-description-preview');
            var $fullDesc = $card.find('.popcorn-event-description-full');
            
            if ($preview.is(':visible')) {
                // Show full description, hide preview
                $preview.hide();
                $fullDesc.show();
                $header.addClass('popcorn-section-open');
            } else {
                // Show preview, hide full description
                $fullDesc.hide();
                $preview.show();
                $header.removeClass('popcorn-section-open');
            }
        });
        
        // Re-initialize on window load (for language switches)
        $(window).on('load', function() {
            setTimeout(function() {
                initializeHostDropdowns();
            }, 300);
        });
        
        // Re-initialize when language switcher is clicked (for Chinese language compatibility)
        $(document).on('click', '.popcorn-lang-option', function() {
            setTimeout(function() {
                initializeHostDropdowns();
            }, 1000); // Increased timeout for language switch
        });
        
        // Listen for custom language switching event
        $(document).on('popcorn:language-switching', function(e, data) {
            console.log('Language switching to:', data.targetLang);
            setTimeout(function() {
                initializeHostDropdowns();
            }, 1200); // Slightly longer timeout for the custom event
        });
        
        // Re-initialize when page content changes (for language switches)
        $(document).on('DOMContentLoaded', function() {
            setTimeout(function() {
                initializeHostDropdowns();
            }, 300);
        });
        
        // Re-initialize on page visibility change (for language switches)
        document.addEventListener('visibilitychange', function() {
            if (!document.hidden) {
                setTimeout(function() {
                    initializeHostDropdowns();
                }, 200);
            }
        });
        
        // Additional check for when page content is fully loaded
        var checkInterval = setInterval(function() {
            if (($('.popcorn-hosts-page').length && $('.popcorn-section-header').length) || 
                $('.popcorn-event-host-header').length) {
                initializeHostDropdowns();
                clearInterval(checkInterval);
            }
        }, 500);
        
        // Clear interval after 10 seconds to prevent infinite checking
        setTimeout(function() {
            clearInterval(checkInterval);
        }, 10000);
    });
});
