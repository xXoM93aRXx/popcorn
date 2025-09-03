# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)

class PopcornSaleOrder(models.Model):
    """Extends sale.order with Popcorn Club specific functionality"""
    _inherit = 'sale.order'
    
    # Remove all membership-related logic - memberships are now separate entities
