/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.popcornDayFilter = publicWidget.Widget.extend({
    selector: '.popcorn-day-filter',
    events: {
        'change input[type="checkbox"]': '_onDayToggle',
    },

    _onDayToggle: function (ev) {
        const checkbox = ev.target;
        const dayValue = checkbox.getAttribute('data-day');
        const currentUrl = new URL(window.location);
        const currentDays = currentUrl.searchParams.get('day_of_week') || '';
        const selectedDays = currentDays ? currentDays.split(',') : [];
        
        if (checkbox.checked) {
            // Add day if not already selected
            if (!selectedDays.includes(dayValue)) {
                selectedDays.push(dayValue);
            }
        } else {
            // Remove day from selection
            const index = selectedDays.indexOf(dayValue);
            if (index > -1) {
                selectedDays.splice(index, 1);
            }
        }
        
        // Update URL parameter
        if (selectedDays.length > 0) {
            currentUrl.searchParams.set('day_of_week', selectedDays.join(','));
        } else {
            currentUrl.searchParams.delete('day_of_week');
        }
        
        // Update URL without page reload
        window.history.pushState({}, '', currentUrl.toString());
        
        // Reload the page content via AJAX
        fetch(currentUrl.toString())
            .then(response => response.text())
            .then(html => {
                // Update the events container
                const parser = new DOMParser();
                const doc = parser.parseFromString(html, 'text/html');
                const newEventsContainer = doc.querySelector('.popcorn-events-container');
                const currentEventsContainer = document.querySelector('.popcorn-events-container');
                if (newEventsContainer && currentEventsContainer) {
                    currentEventsContainer.innerHTML = newEventsContainer.innerHTML;
                }
                
                // Update the filter button text
                const filterButton = document.querySelector('[data-bs-toggle="dropdown"]');
                if (filterButton) {
                    if (selectedDays.length === 0) {
                        filterButton.textContent = 'All Days';
                    } else if (selectedDays.length === 1) {
                        const dayNames = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
                        filterButton.textContent = dayNames[parseInt(selectedDays[0])];
                    } else {
                        filterButton.textContent = selectedDays.length + ' Days';
                    }
                }
            })
            .catch(error => {
                console.error('Error updating filter:', error);
                // Fallback to page reload
                window.location.href = currentUrl.toString();
            });
    },
});
