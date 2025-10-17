# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PopcornDiscountUsage(models.Model):
    """Track discount usage by customers"""
    _name = 'popcorn.discount.usage'
    _description = 'Popcorn Discount Usage'
    _order = 'usage_date desc'
    _rec_name = 'display_name'

    # Basic Information
    discount_id = fields.Many2one('popcorn.discount', string='Discount', required=True, ondelete='cascade')
    partner_id = fields.Many2one('res.partner', string='Customer', required=True, ondelete='cascade')
    usage_date = fields.Datetime(string='Usage Date', required=True, default=fields.Datetime.now)
    
    # Context Information
    membership_plan_id = fields.Many2one('popcorn.membership.plan', string='Membership Plan', ondelete='set null')
    event_id = fields.Many2one('event.event', string='Event', ondelete='set null')
    membership_id = fields.Many2one('popcorn.membership', string='Membership', ondelete='set null')
    event_registration_id = fields.Many2one('event.registration', string='Event Registration', ondelete='set null')
    
    # Pricing Information
    original_price = fields.Float(string='Original Price', required=True)
    discounted_price = fields.Float(string='Discounted Price', required=True)
    discount_amount = fields.Float(string='Discount Amount', compute='_compute_discount_amount', store=True)
    currency_id = fields.Many2one('res.currency', string='Currency', required=True)
    
    # Extra Benefits
    extra_days = fields.Integer(string='Extra Days', default=0)
    
    # Computed Fields
    display_name = fields.Char(string='Display Name', compute='_compute_display_name', store=True)
    
    @api.depends('original_price', 'discounted_price')
    def _compute_discount_amount(self):
        """Calculate the discount amount"""
        for usage in self:
            usage.discount_amount = usage.original_price - usage.discounted_price
    
    @api.depends('discount_id', 'partner_id', 'usage_date')
    def _compute_display_name(self):
        """Compute display name"""
        for usage in self:
            usage.display_name = f"{usage.discount_id.code or usage.discount_id.name} - {usage.partner_id.name} ({usage.usage_date.strftime('%Y-%m-%d')})"
    
    @api.model
    def create_usage_record(self, discount_id, partner_id, original_price, discounted_price, 
                           currency_id, membership_plan_id=None, event_id=None, 
                           membership_id=None, event_registration_id=None, extra_days=0):
        """Create a usage record for a discount"""
        vals = {
            'discount_id': discount_id,
            'partner_id': partner_id,
            'original_price': original_price,
            'discounted_price': discounted_price,
            'currency_id': currency_id,
            'extra_days': extra_days,
        }
        
        if membership_plan_id:
            vals['membership_plan_id'] = membership_plan_id
        if event_id:
            vals['event_id'] = event_id
        if membership_id:
            vals['membership_id'] = membership_id
        if event_registration_id:
            vals['event_registration_id'] = event_registration_id
            
        return self.create(vals)
    
    @api.constrains('original_price', 'discounted_price')
    def _check_prices(self):
        """Validate pricing"""
        for usage in self:
            if usage.original_price < 0:
                raise ValidationError(_('Original price cannot be negative'))
            if usage.discounted_price < 0:
                raise ValidationError(_('Discounted price cannot be negative'))
            if usage.discounted_price > usage.original_price:
                raise ValidationError(_('Discounted price cannot be higher than original price'))





