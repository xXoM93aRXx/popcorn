# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from datetime import timedelta

class PopcornProductTemplate(models.Model):
    """Extends product.template with Popcorn Club specific fields"""
    _inherit = 'product.template'
    
    # Remove all membership plan fields - products are now separate from memberships
