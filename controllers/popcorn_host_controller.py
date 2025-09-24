# -*- coding: utf-8 -*-

from odoo import http, fields
from odoo.http import request


class PopcornHostController(http.Controller):

    @http.route('/hosts', type='http', auth='public', website=True)
    def hosts_page(self, **kwargs):
        """Display all hosts page with dropdown sections"""
        all_hosts = request.env['res.partner'].sudo().search([
            ('is_host', '=', True),
            ('website_published', '=', True)
        ])
        
        online_hosts = all_hosts.filtered(lambda h: h.online_status == 'online')
        offline_hosts = all_hosts.filtered(lambda h: h.online_status == 'offline')
        
        values = {
            'online_hosts': online_hosts,
            'offline_hosts': offline_hosts,
            'online_hosts_count': len(online_hosts),
            'offline_hosts_count': len(offline_hosts),
            'filter_type': 'all'
        }
        
        return request.render('popcorn.popcorn_host_profile_page', values)

    @http.route('/host/<int:host_id>', type='http', auth='public', website=True)
    def host_profile(self, host_id, **kwargs):
        """Display individual host profile"""
        host = request.env['res.partner'].sudo().browse(host_id)
        
        if not host.exists() or not host.is_host or not host.website_published:
            return request.not_found()
        
        # Get events hosted by this host
        host_events = request.env['event.event'].sudo().search([
            ('host_id', '=', host.id),
            ('website_published', '=', True)
        ], order='date_begin desc', limit=10)
        
        values = {
            'host': host,
            'host_events': host_events,
        }
        
        return request.render('popcorn.popcorn_single_host_profile', values)

    @http.route('/hosts/online', type='http', auth='public', website=True)
    def online_hosts(self, **kwargs):
        """Display only online hosts"""
        hosts = request.env['res.partner'].sudo().search([
            ('is_host', '=', True),
            ('website_published', '=', True),
            ('online_status', '=', 'online')
        ])
        
        values = {
            'hosts': hosts,
            'filter_type': 'online'
        }
        
        return request.render('popcorn.popcorn_host_profile_page', values)

    @http.route('/hosts/offline', type='http', auth='public', website=True)
    def offline_hosts(self, **kwargs):
        """Display only offline hosts"""
        hosts = request.env['res.partner'].sudo().search([
            ('is_host', '=', True),
            ('website_published', '=', True),
            ('online_status', '=', 'offline')
        ])
        
        values = {
            'hosts': hosts,
            'filter_type': 'offline'
        }
        
        return request.render('popcorn.popcorn_host_profile_page', values)
