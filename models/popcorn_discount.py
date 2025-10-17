# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class PopcornDiscount(models.Model):
    """Flexible discount system for membership plans"""
    _name = 'popcorn.discount'
    _description = 'Popcorn Club Discount'
    _order = 'sequence, name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # Basic Information
    name = fields.Char(string='Discount Name', required=True, tracking=True)
    code = fields.Char(string='Discount Code', help='Optional code for customers to enter')
    description = fields.Text(string='Description', help='Internal description of the discount')
    active = fields.Boolean(string='Active', default=True, tracking=True)
    sequence = fields.Integer(string='Sequence', default=10, help='Order of display')

    # Discount Configuration
    discount_type = fields.Selection([
        ('percentage', 'Percentage'),
        ('fixed_amount', 'Fixed Amount'),
        ('first_timer', 'First Timer Price'),
        ('upgrade', 'Upgrade Discount'),
        ('extra_days', 'Extra Days')
    ], string='Discount Type', required=True, default='percentage', tracking=True)

    discount_value = fields.Float(string='Discount Value', 
                                 help='Percentage (0-100) or fixed amount', 
                                 required=True, tracking=True)
    
    extra_days = fields.Integer(string='Extra Days', 
                               help='Number of extra days to add to membership duration',
                               default=0, tracking=True)

    # Validity Period
    date_from = fields.Date(string='Valid From', help='Discount valid from this date')
    date_to = fields.Date(string='Valid To', help='Discount valid until this date')

    # Usage Limits
    usage_limit = fields.Integer(string='Usage Limit', 
                               help='Maximum number of times this discount can be used (0 = unlimited)')
    usage_count = fields.Integer(string='Times Used', default=0, readonly=True)
    usage_limit_per_customer = fields.Integer(string='Per Customer Limit', 
                                            help='Maximum times one customer can use this discount (0 = unlimited)')

    # Membership Plan Relationships
    membership_plan_ids = fields.Many2many('popcorn.membership.plan', 
                                         'popcorn_membership_plan_discount_rel',
                                         'discount_id', 'plan_id',
                                         string='Applicable Plans',
                                         help='Membership plans this discount applies to')

    # Event Type Restriction
    event_type = fields.Selection([
        ('regular_offline', 'Regular Offline Only'),
        ('regular_online', 'Regular Online Only'),
        ('spclub', 'Special Club Only'),
    ], string='Event Type Restriction', 
       help='Restrict discount to specific event types. Leave empty for no restriction.')

    # Customer Restrictions
    customer_type = fields.Selection([
        ('all', 'All Customers'),
        ('first_timer', 'First Timer Only'),
        ('existing', 'Existing Customers Only'),
        ('new', 'New Customers Only')
    ], string='Customer Type', default='all', required=True)
    
    partner_id = fields.Many2one('res.partner', string='Specific Customer',
                                 help='If set, this discount can only be used by this specific customer')

    # Display and Marketing
    display_name = fields.Char(string='Display Name', compute='_compute_display_name', store=True)
    badge_image = fields.Binary(string='Badge Image', attachment=True, 
                               help='Image to display as badge on website')
    is_public = fields.Boolean(string='Public Discount', 
                              help='Show this discount to customers on website')
    website_description = fields.Html(string='Website Description', 
                                     help='Description shown to customers')

    # Computed Fields
    is_valid = fields.Boolean(string='Currently Valid', compute='_compute_is_valid', store=True)
    remaining_usage = fields.Integer(string='Remaining Usage', compute='_compute_remaining_usage')

    @api.depends('name', 'discount_type', 'discount_value')
    def _compute_display_name(self):
        """Compute display name for the discount"""
        for discount in self:
            if discount.discount_type == 'percentage':
                display = f"{discount.name} ({discount.discount_value}%)"
            elif discount.discount_type == 'fixed_amount':
                display = f"{discount.name} (${discount.discount_value})"
            elif discount.discount_type == 'first_timer':
                display = f"{discount.name} (First Timer)"
            elif discount.discount_type == 'upgrade':
                display = f"{discount.name} (Upgrade)"
            else:
                display = discount.name
            discount.display_name = display

    @api.depends('active', 'date_from', 'date_to', 'usage_limit', 'usage_count')
    def _compute_is_valid(self):
        """Check if discount is currently valid"""
        today = fields.Date.today()
        for discount in self:
            valid = discount.active
            if discount.date_from and discount.date_from > today:
                valid = False
            if discount.date_to and discount.date_to < today:
                valid = False
            if discount.usage_limit > 0 and discount.usage_count >= discount.usage_limit:
                valid = False
            discount.is_valid = valid

    @api.depends('usage_limit', 'usage_count')
    def _compute_remaining_usage(self):
        """Calculate remaining usage count"""
        for discount in self:
            if discount.usage_limit == 0:
                discount.remaining_usage = -1  # Unlimited
            else:
                discount.remaining_usage = max(0, discount.usage_limit - discount.usage_count)

    @api.constrains('discount_value', 'discount_type')
    def _check_discount_value(self):
        """Validate discount value based on type"""
        for discount in self:
            if discount.discount_type == 'percentage':
                if discount.discount_value < 0 or discount.discount_value > 100:
                    raise ValidationError(_('Percentage discount must be between 0 and 100'))
            elif discount.discount_type in ['fixed_amount', 'first_timer', 'upgrade']:
                if discount.discount_value < 0:
                    raise ValidationError(_('Fixed amount discount cannot be negative'))

    @api.constrains('date_from', 'date_to')
    def _check_date_range(self):
        """Validate date range"""
        for discount in self:
            if discount.date_from and discount.date_to and discount.date_from > discount.date_to:
                raise ValidationError(_('Valid From date cannot be after Valid To date'))

    @api.constrains('usage_limit', 'usage_limit_per_customer')
    def _check_usage_limits(self):
        """Validate usage limits"""
        for discount in self:
            if discount.usage_limit < 0:
                raise ValidationError(_('Usage limit cannot be negative'))
            if discount.usage_limit_per_customer < 0:
                raise ValidationError(_('Per customer limit cannot be negative'))

    def action_increment_usage(self):
        """Increment usage count (called when discount is applied)"""
        self.ensure_one()
        if self.usage_limit > 0 and self.usage_count >= self.usage_limit:
            raise UserError(_('This discount has reached its usage limit'))
        
        self.write({'usage_count': self.usage_count + 1})
        
        # Log the usage
        self.message_post(
            body=_('Discount used - Total usage: %s') % self.usage_count
        )
        
        # Refresh partner discount status if this is a first-timer discount
        if self.code:
            partners = self.env['res.partner'].sudo().search([
                ('first_timer_discount_code', '=', self.code)
            ])
            for partner in partners:
                partner._compute_first_timer_discount_status()

    def action_reset_usage(self):
        """Reset usage count (staff action)"""
        self.ensure_one()
        self.write({'usage_count': 0})
        
        # Refresh partner discount status if this is a first-timer discount
        if self.code:
            partners = self.env['res.partner'].sudo().search([
                ('first_timer_discount_code', '=', self.code)
            ])
            for partner in partners:
                partner._compute_first_timer_discount_status()
        
        # Log the reset
        self.message_post(
            body=_('Usage count reset by staff')
        )

    def action_duplicate(self):
        """Duplicate this discount"""
        self.ensure_one()
        copy_vals = {
            'name': f"{self.name} (Copy)",
            'usage_count': 0,  # Reset usage count
        }
        
        new_discount = self.copy(copy_vals)
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Discount'),
            'res_model': 'popcorn.discount',
            'res_id': new_discount.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def get_discounted_price(self, membership_plan, original_price, customer_partner=None):
        """Calculate discounted price for a membership plan"""
        self.ensure_one()
        
        # Check if discount is valid
        if not self.is_valid:
            return original_price
        
        # Check if discount is restricted to a specific partner
        if self.partner_id and customer_partner and self.partner_id.id != customer_partner.id:
            return original_price
        
        # Check customer type restrictions
        if customer_partner and self.customer_type != 'all':
            if self.customer_type == 'first_timer' and not customer_partner.is_first_timer:
                return original_price
            elif self.customer_type == 'existing' and customer_partner.is_first_timer:
                return original_price
            elif self.customer_type == 'new' and customer_partner.is_first_timer:
                return original_price
        
        # Check if plan is applicable
        if self.membership_plan_ids and membership_plan not in self.membership_plan_ids:
            return original_price
        
        # Calculate discount
        if self.discount_type == 'percentage':
            discount_amount = original_price * (self.discount_value / 100)
            return max(0, original_price - discount_amount)
        
        elif self.discount_type == 'fixed_amount':
            return max(0, original_price - self.discount_value)
        
        elif self.discount_type == 'first_timer':
            # Use the first timer price from the plan
            return membership_plan.price_first_timer
        
        elif self.discount_type == 'upgrade':
            # This would be used in upgrade scenarios
            return max(0, original_price - self.discount_value)
        
        elif self.discount_type == 'extra_days':
            # For extra days, return the original price (no price discount)
            # The extra days will be handled during membership creation
            return original_price
        
        return original_price

    def get_extra_days(self, membership_plan, customer_partner=None):
        """Get extra days from this discount"""
        self.ensure_one()
        
        # Check if discount is valid
        if not self.is_valid:
            return 0
        
        # Check if discount is restricted to a specific partner
        if self.partner_id and customer_partner and self.partner_id.id != customer_partner.id:
            return 0
        
        # Check customer type restrictions
        if customer_partner and self.customer_type != 'all':
            if self.customer_type == 'first_timer' and not customer_partner.is_first_timer:
                return 0
            elif self.customer_type == 'existing' and customer_partner.is_first_timer:
                return 0
            elif self.customer_type == 'new' and customer_partner.is_first_timer:
                return 0
        
        # Check if plan is applicable
        if self.membership_plan_ids and membership_plan not in self.membership_plan_ids:
            return 0
        
        # Return extra days if this is an extra_days discount
        if self.discount_type == 'extra_days':
            return self.extra_days
        
        return 0

    @api.model
    def get_available_discounts(self, membership_plan, customer_partner=None):
        """Get all available discounts for a membership plan and customer"""
        domain = [
            ('is_valid', '=', True),
            ('partner_id', '=', False),  # Exclude partner-specific discounts (first-timer coupons)
            '|',
            ('membership_plan_ids', '=', False),  # Applies to all plans
            ('membership_plan_ids', 'in', membership_plan.id)
        ]
        
        discounts = self.search(domain)
        
        # Filter by customer type
        if customer_partner:
            filtered_discounts = self.env['popcorn.discount']
            for discount in discounts:
                if discount.customer_type == 'all':
                    filtered_discounts |= discount
                elif discount.customer_type == 'first_timer' and customer_partner.is_first_timer:
                    filtered_discounts |= discount
                elif discount.customer_type == 'existing' and not customer_partner.is_first_timer:
                    filtered_discounts |= discount
                elif discount.customer_type == 'new' and customer_partner.is_first_timer:
                    filtered_discounts |= discount
            discounts = filtered_discounts
        
        return discounts
    
    @api.constrains('discount_type', 'extra_days')
    def _check_extra_days_required(self):
        """Ensure extra_days is set when discount_type is 'extra_days'"""
        for discount in self:
            if discount.discount_type == 'extra_days' and discount.extra_days <= 0:
                raise ValidationError(_("Extra Days must be greater than 0 when discount type is 'Extra Days'"))
    
    @api.constrains('discount_type', 'discount_value')
    def _check_discount_value_required(self):
        """Ensure discount_value is set for non-extra_days discounts"""
        for discount in self:
            if discount.discount_type != 'extra_days' and discount.discount_value <= 0:
                raise ValidationError(_("Discount Value must be greater than 0 for this discount type"))
            elif discount.discount_type == 'extra_days' and discount.discount_value < 0:
                raise ValidationError(_("Discount Value cannot be negative"))
    
    def get_badge_display_info(self):
        """Get badge display information for website"""
        self.ensure_one()
        return {
            'id': self.id,
            'name': self.name,
            'code': self.code,
            'discount_type': self.discount_type,
            'discount_value': self.discount_value,
            'extra_days': self.extra_days,
            'badge_image': self.badge_image,
            'is_valid': self.is_valid,
            'website_description': self.website_description,
            'display_name': self.display_name
        }

    @api.model
    def _cron_check_expired_discounts(self):
        """Cron job to deactivate expired discounts"""
        expired_discounts = self.search([
            ('active', '=', True),
            ('date_to', '<', fields.Date.today())
        ])
        
        for discount in expired_discounts:
            discount.write({'active': False})
            discount.message_post(
                body=_('Discount automatically deactivated - expired on %s') % discount.date_to
            )
