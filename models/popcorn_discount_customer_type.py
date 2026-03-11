# -*- coding: utf-8 -*-

from odoo import models, fields


class PopcornDiscountCustomerType(models.Model):
    """Customer type options for discount targeting when using multiple selection"""
    _name = 'popcorn.discount.customer.type'
    _description = 'Discount Customer Type'
    _order = 'sequence, name'

    name = fields.Char(string='Name', required=True, translate=True)
    code = fields.Char(string='Code', required=True, help='Internal code: first_timer, existing, new')
    sequence = fields.Integer(string='Sequence', default=10)

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'Customer type code must be unique.')
    ]
