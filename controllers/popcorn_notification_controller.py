# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)


class PopcornNotificationController(http.Controller):
    
    @http.route('/popcorn/notifications/get', type='json', auth='public', website=True)
    def get_notifications(self, **kwargs):
        """Get all active notifications for the current user"""
        try:
            # Get current partner
            partner = request.env.user.partner_id
            
            if not partner:
                return {'success': True, 'notifications': []}
            
            # Get all active notifications
            notifications = request.env['popcorn.notification'].sudo().search([
                ('active', '=', True)
            ], order='sequence, id')
            
            # Filter and format notifications
            result_notifications = []
            for notification in notifications:
                if notification._evaluate_notification_for_partner(partner):
                    notification_data = notification.get_notification_data_for_partner(partner)
                    if notification_data:
                        result_notifications.append(notification_data)
            
            return {
                'success': True,
                'notifications': result_notifications
            }
            
        except Exception as e:
            _logger.error(f"Error in get_notifications: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'notifications': []
            }

