# -*- coding: utf-8 -*-

from odoo import http, fields
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal


class PopcornBadgeController(http.Controller):

    @http.route(['/my/badges'], type='http', auth="user", website=True)
    def portal_my_badges(self, **kw):
        """Display user's badges in portal"""
        partner = request.env.user.partner_id
        
        # Get all badges and evaluate them for the current user
        badges = request.env['popcorn.badge'].search([('active', '=', True)])
        
        # Add context to compute earned status
        badges = badges.with_context(uid=request.env.user.id)
        
        values = {
            'partner': partner,
            'badges': badges,
            'page_name': 'badges',
        }
        
        return request.render('popcorn.portal_my_badges_page', values)

    @http.route(['/my/badge/<int:badge_id>'], type='http', auth="user", website=True)
    def portal_badge_detail(self, badge_id, **kw):
        """Display detailed badge information"""
        badge = request.env['popcorn.badge'].browse(badge_id)
        if not badge.exists() or not badge.active:
            return request.not_found()
        
        partner = request.env.user.partner_id
        
        # Add context to compute earned status
        badge = badge.with_context(uid=request.env.user.id)
        
        values = {
            'partner': partner,
            'badge': badge,
            'page_name': 'badge_detail',
        }
        
        return request.render('popcorn.portal_badge_detail_page', values)


class PopcornCustomerPortal(CustomerPortal):
    
    def _prepare_portal_layout_values(self):
        """Add badge count to portal values"""
        values = super()._prepare_portal_layout_values()
        
        if request.env.user.partner_id:
            partner = request.env.user.partner_id
            # Count earned badges
            earned_badges = request.env['popcorn.badge'].search([
                ('active', '=', True)
            ]).with_context(uid=request.env.user.id)
            
            earned_count = sum(1 for badge in earned_badges if badge.earned)
            total_count = len(earned_badges)
            
            values.update({
                'earned_badges_count': earned_count,
                'total_badges_count': total_count,
            })
        
        return values
