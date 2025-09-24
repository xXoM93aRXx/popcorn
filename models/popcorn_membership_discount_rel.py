# -*- coding: utf-8 -*-

from odoo import fields, models


class PopcornMembershipDiscountRel(models.Model):
    """Many-to-many relationship between membership plans and discounts"""
    _name = 'popcorn.membership.discount.rel'
    _description = 'Membership Plan Discount Relationship'
    _table = 'popcorn_membership_plan_discount_rel'

    # Relationship fields
    plan_id = fields.Many2one('popcorn.membership.plan', string='Membership Plan', required=True, ondelete='cascade')
    discount_id = fields.Many2one('popcorn.discount', string='Discount', required=True, ondelete='cascade')
    
    # Additional relationship data
    sequence = fields.Integer(string='Sequence', default=10, help='Order of display')
    active = fields.Boolean(string='Active', default=True, help='Whether this relationship is active')
    
    # Constraints
    _sql_constraints = [
        ('unique_plan_discount', 'unique(plan_id, discount_id)', 
         'A discount can only be linked to a membership plan once')
    ]
