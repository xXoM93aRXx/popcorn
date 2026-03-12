# -*- coding: utf-8 -*-

import json
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


    @http.route(['/my/diversity'], type='http', auth="user", website=True)
    def portal_diversity(self, **kw):
        """Display Mortal Kombat style diversity badge — all hosts, locked/unlocked"""
        partner = request.env.user.partner_id

        # All active hosts
        hosts = request.env['res.partner'].sudo().search([
            ('is_host', '=', True),
            ('active', '=', True),
        ], order='name')

        # Which hosts has this partner actually attended?
        attended_host_ids = partner.get_attended_host_ids()

        hosts_data = []
        for host in hosts:
            # Build image URL via our sudo route to bypass portal access restrictions
            if host.diversity_badge_image:
                img_src = '/popcorn/host-image/%d' % host.id
            elif host.host_poster_image:
                img_src = '/popcorn/host-image/%d' % host.id
            else:
                img_src = None
            hosts_data.append({
                'host': host,
                'unlocked': host.id in attended_host_ids,
                'img_src': img_src,
            })

        unlocked_count = len(attended_host_ids & set(hosts.ids))

        values = {
            'partner': partner,
            'hosts_data': hosts_data,
            'unlocked_count': unlocked_count,
            'total_count': len(hosts),
            'page_name': 'diversity',
        }

        return request.render('popcorn.portal_diversity_page', values)

    @http.route(['/popcorn/badges/check-new'], type='http', auth='user', website=True, csrf=False)
    def check_new_badges(self, **kw):
        """Return badges earned since the last check and mark them as notified."""
        partner = request.env.user.partner_id

        all_active = request.env['popcorn.badge'].search([('active', '=', True)])
        earned = request.env['popcorn.badge']
        for badge in all_active:
            if badge._evaluate_badge_for_partner(partner):
                earned |= badge

        new_badges = earned - partner.notified_badge_ids

        result = []
        for badge in new_badges:
            image_url = '/web/image/popcorn.badge/%d/image' % badge.id if badge.image else ''
            result.append({
                'id': badge.id,
                'name': badge.name,
                'image_url': image_url,
            })

        if new_badges:
            partner.sudo().write({
                'notified_badge_ids': [(4, b.id) for b in new_badges],
                'permanently_earned_badge_ids': [(4, b.id) for b in new_badges],
            })
            for badge in new_badges:
                if badge.prize_popcorn_money > 0:
                    from odoo import fields as odoo_fields
                    from datetime import timedelta
                    expiry_date = None
                    if badge.prize_expiry_days > 0:
                        expiry_date = odoo_fields.Date.today() + timedelta(days=badge.prize_expiry_days)
                    partner.sudo().add_popcorn_money(
                        badge.prize_popcorn_money,
                        notes='Badge earned: %s%s' % (
                            badge.name,
                            ' (expires %s)' % expiry_date if expiry_date else '',
                        )
                    )
                    request.env['popcorn.badge.prize'].sudo().create({
                        'partner_id': partner.id,
                        'badge_id': badge.id,
                        'amount': badge.prize_popcorn_money,
                        'expiry_date': expiry_date,
                    })

        return request.make_response(
            json.dumps({'badges': result}),
            headers=[('Content-Type', 'application/json')],
        )

    @http.route(['/popcorn/badges/reset-notifications'], type='http', auth='user', website=True, csrf=False)
    def reset_badge_notifications(self, **kw):
        """Dev helper: clear all badge notifications for the current partner."""
        partner = request.env.user.partner_id
        partner.sudo().write({'notified_badge_ids': [(5,)]})
        return request.make_response(
            json.dumps({'ok': True}),
            headers=[('Content-Type', 'application/json')],
        )

    @http.route(['/popcorn/host-image/<int:host_id>'], type='http', auth='public', website=True)
    def host_diversity_image(self, host_id, **kw):
        """Serve host diversity badge image with sudo to bypass portal access restrictions"""
        import base64
        host = request.env['res.partner'].sudo().browse(host_id)
        if not host.exists() or not host.is_host:
            return request.not_found()

        img_data = host.diversity_badge_image or host.host_poster_image
        if not img_data:
            return request.not_found()

        img_bytes = base64.b64decode(img_data)
        content_type = 'image/png' if img_bytes[:4] == b'\x89PNG' else 'image/jpeg'
        headers = [
            ('Content-Type', content_type),
            ('Cache-Control', 'public, max-age=86400'),
        ]
        return request.make_response(img_bytes, headers=headers)


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
