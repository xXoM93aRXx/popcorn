/** @odoo-module **/

/**
 * Frontend helper for Popcorn language switcher functionality.
 *
 * Responsibilities:
 *  - Handle language option clicks with visual feedback.
 *  - Manage dropdown hover effects.
 *  - Trigger custom events for language switching notifications.
 *
 * Notes:
 *  - The asset is declared in the module manifest under web.assets_frontend.
 */

function wireLanguageSwitcher() {
    const switcher = document.getElementById('popcorn-language-switcher');
    if (!switcher) return;
    
    // Handle language option clicks
    const langOptions = switcher.querySelectorAll('.popcorn-lang-option');
    langOptions.forEach((option) => {
        option.addEventListener('click', function(evt) {
            addSwitchFeedback(option);
            
            // Trigger custom event for other components to listen to
            const customEvent = new CustomEvent('popcorn:language-switching', {
                detail: {
                    targetLang: option.dataset.lang
                }
            });
            document.dispatchEvent(customEvent);
        });
    });
    
    // Handle dropdown hover effects
    const dropdown = switcher.querySelector('.popcorn-lang-dropdown');
    if (dropdown) {
        dropdown.addEventListener('mouseenter', function() {
            dropdown.classList.add('popcorn-dropdown-hover');
        });
        dropdown.addEventListener('mouseleave', function() {
            dropdown.classList.remove('popcorn-dropdown-hover');
        });
    }
}

function addSwitchFeedback(element) {
    element.classList.add('popcorn-switching');
    setTimeout(() => {
        element.classList.remove('popcorn-switching');
    }, 300);
}

// Wait for the page to be ready before wiring events
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', wireLanguageSwitcher);
} else {
    wireLanguageSwitcher();
}
