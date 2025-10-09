/**
 * Popcorn Notification System JavaScript
 * Handles banner (toast) and popup notifications based on user conditions
 */

odoo.define('popcorn.notifications', [], function () {
    'use strict';

    // Storage keys
    const SESSION_STORAGE_KEY = 'popcorn_notifications_shown_session';
    const LOCAL_STORAGE_KEY = 'popcorn_notifications_shown_user';

    class PopcornNotificationManager {
        constructor() {
            this.notifications = [];
            this.shownInSession = this.getSessionStorage();
            this.shownForUser = this.getLocalStorage();
            this.activePopup = null;
        }

        // Storage management
        getSessionStorage() {
            try {
                return JSON.parse(sessionStorage.getItem(SESSION_STORAGE_KEY) || '[]');
            } catch (e) {
                return [];
            }
        }

        getLocalStorage() {
            try {
                return JSON.parse(localStorage.getItem(LOCAL_STORAGE_KEY) || '[]');
            } catch (e) {
                return [];
            }
        }

        markAsShownInSession(notificationId) {
            if (!this.shownInSession.includes(notificationId)) {
                this.shownInSession.push(notificationId);
                sessionStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(this.shownInSession));
            }
        }

        markAsShownForUser(notificationId) {
            if (!this.shownForUser.includes(notificationId)) {
                this.shownForUser.push(notificationId);
                localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(this.shownForUser));
            }
        }

        shouldShowNotification(notification) {
            // Check if notification should be shown based on frequency settings
            if (notification.show_once_per_session && this.shownInSession.includes(notification.id)) {
                return false;
            }
            if (notification.show_once_per_user && this.shownForUser.includes(notification.id)) {
                return false;
            }
            return true;
        }

        // Fetch notifications from server
        async fetchNotifications() {
            try {
                const response = await fetch('/popcorn/notifications/get', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        jsonrpc: '2.0',
                        method: 'call',
                        params: {}
                    })
                });

                const data = await response.json();
                
                if (data.result && data.result.success) {
                    this.notifications = data.result.notifications || [];
                    this.displayNotifications();
                }
            } catch (error) {
                console.error('Error fetching notifications:', error);
            }
        }

        // Display all notifications
        displayNotifications() {
            this.notifications.forEach((notification, index) => {
                if (!this.shouldShowNotification(notification)) {
                    return;
                }

                // Add delay between notifications
                setTimeout(() => {
                    if (notification.type === 'banner') {
                        this.showBanner(notification);
                    } else if (notification.type === 'popup') {
                        this.showPopup(notification);
                    }

                    // Mark as shown
                    if (notification.show_once_per_session) {
                        this.markAsShownInSession(notification.id);
                    }
                    if (notification.show_once_per_user) {
                        this.markAsShownForUser(notification.id);
                    }
                }, index * 500); // 500ms delay between notifications
            });
        }

        // Show banner notification
        showBanner(notification) {
            const position = notification.banner_position || 'top';
            const container = document.getElementById(`popcorn-banner-container-${position}`);
            
            if (!container) return;

            // Create banner element
            const banner = document.createElement('div');
            banner.className = `popcorn-banner popcorn-banner-${notification.banner_style || 'info'}`;
            banner.setAttribute('role', 'alert');
            banner.setAttribute('aria-live', 'polite');
            
            // Build banner HTML
            let bannerHTML = `
                <div class="popcorn-banner-content">
                    <div class="popcorn-banner-header">
                        <h4 class="popcorn-banner-title">${notification.title}</h4>
                        <button class="popcorn-banner-close" aria-label="Close notification">
                            <span aria-hidden="true">&times;</span>
                        </button>
                    </div>
                    <div class="popcorn-banner-body">${notification.message}</div>
            `;

            if (notification.show_action_button && notification.action_button_url) {
                bannerHTML += `
                    <div class="popcorn-banner-actions">
                        <a href="${notification.action_button_url}" class="popcorn-banner-action-btn">
                            ${notification.action_button_text || 'Learn More'}
                        </a>
                    </div>
                `;
            }

            bannerHTML += '</div>';
            banner.innerHTML = bannerHTML;

            // Add to container
            container.appendChild(banner);

            // Animate in
            setTimeout(() => banner.classList.add('popcorn-banner-show'), 10);

            // Close button handler
            const closeBtn = banner.querySelector('.popcorn-banner-close');
            closeBtn.addEventListener('click', () => this.dismissBanner(banner));

            // Auto dismiss
            if (notification.auto_dismiss) {
                const duration = (notification.dismiss_duration || 5) * 1000;
                setTimeout(() => this.dismissBanner(banner), duration);
            }
        }

        dismissBanner(banner) {
            banner.classList.remove('popcorn-banner-show');
            setTimeout(() => {
                if (banner.parentNode) {
                    banner.parentNode.removeChild(banner);
                }
            }, 300);
        }

        // Show popup notification
        showPopup(notification) {
            // Don't show if another popup is active
            if (this.activePopup) return;

            const overlay = document.getElementById('popcorn-popup-overlay');
            const container = document.getElementById('popcorn-popup-container');
            
            if (!overlay || !container) return;

            // Create popup element
            const popup = document.createElement('div');
            popup.className = `popcorn-popup popcorn-popup-${notification.popup_size || 'medium'}`;
            popup.setAttribute('role', 'dialog');
            popup.setAttribute('aria-modal', 'true');
            popup.setAttribute('aria-labelledby', 'popcorn-popup-title');
            
            // Build popup HTML
            let popupHTML = `
                <div class="popcorn-popup-header">
                    <h3 id="popcorn-popup-title" class="popcorn-popup-title">${notification.title}</h3>
                    <button class="popcorn-popup-close" aria-label="Close popup">
                        <span aria-hidden="true">&times;</span>
                    </button>
                </div>
                <div class="popcorn-popup-body">${notification.message}</div>
            `;

            if (notification.show_action_button && notification.action_button_url) {
                popupHTML += `
                    <div class="popcorn-popup-footer">
                        <a href="${notification.action_button_url}" class="popcorn-popup-action-btn">
                            ${notification.action_button_text || 'Learn More'}
                        </a>
                        <button class="popcorn-popup-dismiss-btn">Close</button>
                    </div>
                `;
            } else {
                popupHTML += `
                    <div class="popcorn-popup-footer">
                        <button class="popcorn-popup-dismiss-btn">Close</button>
                    </div>
                `;
            }

            popup.innerHTML = popupHTML;

            // Add to container
            container.appendChild(popup);
            this.activePopup = popup;

            // Show overlay and popup
            overlay.classList.add('popcorn-popup-overlay-show');
            setTimeout(() => popup.classList.add('popcorn-popup-show'), 10);

            // Close button handlers
            const closeBtn = popup.querySelector('.popcorn-popup-close');
            const dismissBtn = popup.querySelector('.popcorn-popup-dismiss-btn');
            
            closeBtn.addEventListener('click', () => this.dismissPopup(popup, overlay));
            dismissBtn.addEventListener('click', () => this.dismissPopup(popup, overlay));
            overlay.addEventListener('click', () => this.dismissPopup(popup, overlay));

            // Prevent overlay click from closing when clicking inside popup
            popup.addEventListener('click', (e) => e.stopPropagation());
        }

        dismissPopup(popup, overlay) {
            popup.classList.remove('popcorn-popup-show');
            overlay.classList.remove('popcorn-popup-overlay-show');
            
            setTimeout(() => {
                if (popup.parentNode) {
                    popup.parentNode.removeChild(popup);
                }
                this.activePopup = null;
            }, 300);
        }

        // Initialize
        init() {
            // Fetch and display notifications when page loads
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', () => this.fetchNotifications());
            } else {
                this.fetchNotifications();
            }
        }
    }

    // Initialize notification manager when DOM is ready
    $(document).ready(function() {
        const notificationManager = new PopcornNotificationManager();
        notificationManager.init();
    });
});

