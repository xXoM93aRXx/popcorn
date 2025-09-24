# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request


class PopcornContactController(http.Controller):
    
    @http.route(['/contact'], type='http', auth="public", website=True)
    def contact_page(self, **kwargs):
        """Contact Us page"""
        return request.render('popcorn.popcorn_contact_page')
