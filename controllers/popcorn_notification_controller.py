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
            
            # Determine if partner already accepted terms
            terms_category = request.env.ref('popcorn.res_partner_category_terms_agreed', raise_if_not_found=False)
            terms_notification = request.env.ref('popcorn.notification_terms_agreement', raise_if_not_found=False)
            partner_sudo = partner.sudo()
            has_accepted_terms = bool(
                terms_category and partner_sudo.category_id.filtered(lambda c: c.id == terms_category.id)
            )
            
            # Get all active notifications
            notifications = request.env['popcorn.notification'].sudo().search([
                ('active', '=', True)
            ], order='sequence, id')
            
            # Filter and format notifications
            result_notifications = []
            for notification in notifications:
                if has_accepted_terms and terms_notification and notification.id == terms_notification.id:
                    continue
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

    @http.route('/popcorn/notifications/accept_terms', type='json', auth='user', website=True, methods=['POST'])
    def accept_terms(self, **kwargs):
        """Persist terms agreement for the logged-in partner"""
        try:
            partner = request.env.user.partner_id.sudo()
            if not partner:
                return {'success': False, 'error': 'no_partner'}
            
            category = request.env.ref('popcorn.res_partner_category_terms_agreed', raise_if_not_found=False)
            if not category:
                return {'success': False, 'error': 'missing_category'}
            
            if category not in partner.category_id:
                partner.write({'category_id': [(4, category.id)]})
            
            return {'success': True}
        except Exception as e:
            _logger.error(f"Error in accept_terms: {str(e)}", exc_info=True)
            return {'success': False, 'error': str(e)}
