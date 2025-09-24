odoo.define('popcorn.host_dropdown', [], function () {
    'use strict';

    // Host Dropdown Functionality
    $(document).ready(function() {
        function initializeHostDropdowns() {
            // Only initialize if we're on the hosts page
            if (!$('.popcorn-hosts-page').length) {
                console.log('Not on hosts page, skipping initialization');
                return;
            }
            
            // Wait a bit for elements to be available (especially after language switch)
            setTimeout(function() {
                // Set initial state - all dropdowns closed
                $('.popcorn-hosts-dropdown').removeClass('open');
                $('.popcorn-section-header').removeClass('popcorn-section-open');
                
                // Remove any existing event listeners first
                $('.popcorn-section-header').off('click.popcorn');
                
                // Add click event listeners to section headers
                $('.popcorn-section-header').on('click.popcorn', function(e) {
                    e.preventDefault();
                    e.stopPropagation();
                    
                    var sectionId = $(this).data('target');
                    if (sectionId) {
                        toggleSection(sectionId);
                    }
                });
                
                console.log('Host dropdowns initialized - found', $('.popcorn-section-header').length, 'section headers');
            }, 100);
        }

        function toggleSection(sectionId) {
            console.log('toggleSection called with:', sectionId);
            
            // Try multiple times to find elements (for language switch timing issues)
            var attempts = 0;
            var maxAttempts = 5;
            
            function findElements() {
                var $dropdown = $('#' + sectionId);
                var $sectionHeader = $('[data-target="' + sectionId + '"]');
                
                console.log('Attempt', attempts + 1, '- Looking for dropdown:', sectionId, 'found:', $dropdown.length);
                console.log('Attempt', attempts + 1, '- Looking for section header:', $sectionHeader.length);
                
                if ($dropdown.length && $sectionHeader.length) {
                    performToggle($dropdown, $sectionHeader);
                } else if (attempts < maxAttempts) {
                    attempts++;
                    setTimeout(findElements, 200);
                } else {
                    console.log('Elements not found after', maxAttempts, 'attempts, returning');
                }
            }
            
            function performToggle($dropdown, $sectionHeader) {
                if ($dropdown.hasClass('open')) {
                    console.log('Closing dropdown');
                    // Close the dropdown
                    $dropdown.removeClass('open');
                    $sectionHeader.removeClass('popcorn-section-open');
                } else {
                    console.log('Opening dropdown');
                    // Close all other dropdowns first
                    $('.popcorn-hosts-dropdown').removeClass('open');
                    $('.popcorn-section-header').removeClass('popcorn-section-open');
                    
                    // Open the selected dropdown
                    $dropdown.addClass('open');
                    $sectionHeader.addClass('popcorn-section-open');
                    console.log('Added open class to dropdown');
                }
            }
            
            // Start the element finding process
            findElements();
        }

        // Make toggleSection globally available
        window.toggleSection = toggleSection;

        // Initialize when DOM is ready
        initializeHostDropdowns();
        
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
            if ($('.popcorn-hosts-page').length && $('.popcorn-section-header').length) {
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
