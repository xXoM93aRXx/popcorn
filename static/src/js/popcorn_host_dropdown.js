/** @odoo-module **/

/**
 * Frontend helper for Popcorn host dropdown functionality.
 *
 * Responsibilities:
 *  - Handle dropdown toggle for host sections and event descriptions.
 *  - Manage preview/full content display for host bios and event descriptions.
 *  - Support accordion-style behavior (only one section open at a time).
 *
 * Notes:
 *  - The asset is declared in the module manifest under web.assets_frontend.
 */

function wireHostDropdowns() {
    // Handle section header clicks for dropdown toggles
    const sectionHeaders = document.querySelectorAll('.popcorn-section-header, .popcorn-event-host-header');
    sectionHeaders.forEach((header) => {
        header.addEventListener('click', function(evt) {
            evt.preventDefault();
            evt.stopPropagation();
            
            const sectionId = header.dataset.target;
            if (sectionId) {
                toggleSection(sectionId, header);
            }
        });
    });
    
    // Handle event host bio preview/full toggle
    const eventHostHeaders = document.querySelectorAll('.popcorn-event-host-header');
    eventHostHeaders.forEach((header) => {
        const preview = header.querySelector('.popcorn-host-preview');
        const fullBio = header.querySelector('.popcorn-host-full-bio');
        
        if (preview && fullBio) {
            header.addEventListener('click', function(evt) {
                evt.preventDefault();
                evt.stopPropagation();
                
                if (preview.style.display !== 'none') {
                    preview.style.display = 'none';
                    fullBio.style.display = '';
                    header.classList.add('popcorn-section-open');
                } else {
                    fullBio.style.display = 'none';
                    preview.style.display = '';
                    header.classList.remove('popcorn-section-open');
                }
            });
        }
    });
    
    // Handle event description preview/full toggle
    const descriptionHeaders = document.querySelectorAll('.popcorn-event-description-header');
    descriptionHeaders.forEach((header) => {
        const card = header.closest('.popcorn-event-description-card');
        if (!card) return;
        
        const preview = card.querySelector('.popcorn-event-description-preview');
        const fullDesc = card.querySelector('.popcorn-event-description-full');
        
        if (preview && fullDesc) {
            header.addEventListener('click', function(evt) {
                evt.preventDefault();
                evt.stopPropagation();
                
                if (preview.style.display !== 'none') {
                    preview.style.display = 'none';
                    fullDesc.style.display = '';
                    header.classList.add('popcorn-section-open');
                } else {
                    fullDesc.style.display = 'none';
                    preview.style.display = '';
                    header.classList.remove('popcorn-section-open');
                }
            });
        }
    });
}

function toggleSection(sectionId, clickedHeader) {
    const dropdown = document.getElementById(sectionId);
    const sectionHeader = clickedHeader || document.querySelector(`[data-target="${sectionId}"]`);
    
    if (!dropdown || !sectionHeader) return;
    
    if (dropdown.classList.contains('open')) {
        // Close the dropdown
        dropdown.classList.remove('open');
        sectionHeader.classList.remove('popcorn-section-open');
    } else {
        // Close all other dropdowns first
        document.querySelectorAll('.popcorn-hosts-dropdown, .popcorn-event-host-dropdown').forEach((el) => {
            el.classList.remove('open');
        });
        document.querySelectorAll('.popcorn-section-header, .popcorn-event-host-header').forEach((el) => {
            el.classList.remove('popcorn-section-open');
        });
        
        // Open the selected dropdown
        dropdown.classList.add('open');
        sectionHeader.classList.add('popcorn-section-open');
    }
}

// Make toggleSection globally available for external use
window.toggleSection = toggleSection;

// Wait for the page to be ready before wiring events
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', wireHostDropdowns);
} else {
    wireHostDropdowns();
}
