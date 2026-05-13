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

        badges = request.env['popcorn.badge'].sudo().search([('active', '=', True)])

        # Light up only badges already stored on the partner — once earned, always lit.
        earned_badge_ids = set(partner.sudo().permanently_earned_badge_ids.ids)

        values = {
            'partner': partner,
            'badges': badges,
            'earned_badge_ids': earned_badge_ids,
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

        # Only published hosts appear on the diversity screen
        hosts = request.env['res.partner'].sudo().search([
            ('is_host', '=', True),
            ('active', '=', True),
            ('website_published', '=', True),
        ], order='name')

        # Get the diversity badge anchor date so unlocked status only counts from that point
        diversity_badge = request.env['popcorn.badge'].sudo().search(
            [('is_diversity_badge', '=', True), ('active', '=', True)], limit=1
        )
        anchor_date = None
        if diversity_badge:
            anchor_rule = diversity_badge.badge_rule_ids.filtered(
                lambda r: r.active and r.time_filter_anchor_date
            )[:1]
            if anchor_rule:
                from datetime import datetime
                anchor_date = datetime.combine(
                    anchor_rule.time_filter_anchor_date, datetime.min.time()
                ).strftime('%Y-%m-%d %H:%M:%S')

        # Which hosts has this partner actually attended (from anchor date onwards)?
        attended_host_ids = partner.get_attended_host_ids(from_date=anchor_date)

        hosts_data = []
        for host in hosts:
            # Build image URL via our sudo route to bypass portal access restrictions
            if host.diversity_badge_image:
                img_src = '/popcorn/host-image/%d' % host.id
            elif host.host_poster_image:
                img_src = '/popcorn/host-image/%d' % host.id
            else:
                img_src = None

            locked_img_src = '/popcorn/host-locked-image/%d' % host.id if host.diversity_badge_locked_image else None

            hosts_data.append({
                'host': host,
                'unlocked': host.id in attended_host_ids,
                'img_src': img_src,
                'locked_img_src': locked_img_src,
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

    _VARIETY_POSITIONS = [
        (18, 8),  (18, 25), (18, 43), (18, 62), (18, 82),
        (33, 5),  (33, 20), (33, 38), (33, 56), (33, 74), (33, 90),
        (49, 12), (49, 28), (49, 47), (49, 65), (49, 83),
        (64, 7),  (64, 22), (64, 42), (64, 60), (64, 78), (64, 93),
        (79, 15), (79, 33), (79, 52), (79, 70), (79, 88),
    ]

    @http.route(['/my/variety'], type='http', auth="user", website=True)
    def portal_variety(self, **kw):
        """Display constellation sky variety badge — all topic tags, locked/unlocked"""
        partner = request.env.user.partner_id

        topic_category = request.env['event.tag.category'].sudo().search(
            [('name', '=', 'Topics')], limit=1
        )
        topic_tags = request.env['event.tag'].sudo().search(
            [('category_id', '=', topic_category.id)] if topic_category else [('id', '=', False)],
            order='name'
        )

        try:
            variety_badge = request.env.ref('popcorn.badge_variety').sudo()
            if not variety_badge.active:
                variety_badge = request.env['popcorn.badge']
        except Exception:
            variety_badge = request.env['popcorn.badge'].sudo().search(
                [('is_variety_badge', '=', True), ('active', '=', True)], limit=1
            )
        anchor_date = None
        if variety_badge:
            anchor_rule = variety_badge.badge_rule_ids.filtered(
                lambda r: r.active and r.time_filter_anchor_date
            )[:1]
            if anchor_rule:
                from datetime import datetime
                anchor_date = datetime.combine(
                    anchor_rule.time_filter_anchor_date, datetime.min.time()
                ).strftime('%Y-%m-%d %H:%M:%S')

        attended_topic_ids = partner.get_attended_topic_ids(from_date=anchor_date)
        badge_earned = bool(
            variety_badge and (
                variety_badge in partner.sudo().permanently_earned_badge_ids
                or variety_badge._evaluate_badge_for_partner(partner)
            )
        )

        positions = self._VARIETY_POSITIONS
        tags_data = []
        for i, tag in enumerate(topic_tags):
            pos = positions[i % len(positions)]
            tags_data.append({
                'tag': tag,
                'unlocked': tag.id in attended_topic_ids,
                'img_src': '/popcorn/tag-image/%d' % tag.id if tag.constellation_image else None,
                'top': pos[0],
                'left': pos[1],
            })

        unlocked_count = len(attended_topic_ids & set(topic_tags.ids))

        locked_teaser = ''
        if variety_badge:
            locked_teaser = variety_badge.variety_locked_teaser or ''

        values = {
            'partner': partner,
            'tags_data': tags_data,
            'unlocked_count': unlocked_count,
            'total_count': len(topic_tags),
            'badge_earned': badge_earned,
            'variety_locked_teaser': locked_teaser,
            'page_name': 'variety',
        }

        return request.render('popcorn.portal_variety_page', values)

    @http.route(['/popcorn/tag-image/<int:tag_id>'], type='http', auth='public', website=True)
    def tag_constellation_image(self, tag_id, **kw):
        """Serve topic tag constellation image"""
        import base64
        tag = request.env['event.tag'].sudo().browse(tag_id)
        if not tag.exists() or not tag.constellation_image:
            return request.not_found()

        img_bytes = base64.b64decode(tag.constellation_image)
        content_type = 'image/png' if img_bytes[:4] == b'\x89PNG' else 'image/jpeg'
        headers = [
            ('Content-Type', content_type),
            ('Cache-Control', 'public, max-age=86400'),
        ]
        return request.make_response(img_bytes, headers=headers)

    @http.route(['/popcorn/badges/check-new'], type='http', auth='user', website=True, csrf=False)
    def check_new_badges(self, **kw):
        """Return badges earned since the last check and mark them as notified."""
        enabled = request.env['ir.config_parameter'].sudo().get_param('popcorn.badges_evaluation_enabled', 'False')
        if enabled not in ('True', '1', 'true'):
            return request.make_response(
                json.dumps({'badges': []}),
                headers=[('Content-Type', 'application/json')],
            )

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

    @http.route(['/popcorn/host-locked-image/<int:host_id>'], type='http', auth='public', website=True)
    def host_diversity_locked_image(self, host_id, **kw):
        """Serve host diversity badge locked image"""
        import base64
        host = request.env['res.partner'].sudo().browse(host_id)
        if not host.exists() or not host.is_host:
            return request.not_found()

        img_data = host.diversity_badge_locked_image
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
