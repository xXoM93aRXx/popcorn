# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from datetime import timedelta

class PopcornMembershipPlan(models.Model):
    """Standalone membership plans for Popcorn Club"""
    _name = 'popcorn.membership.plan'
    _description = 'Popcorn Club Membership Plan'
    _order = 'sequence, name'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    # Basic Information
    name = fields.Char(string='Plan Name', required=True, tracking=True)
    sequence = fields.Integer(string='Sequence', default=10, help='Order of display')
    active = fields.Boolean(string='Active', default=True, tracking=True)
    anchor_tag = fields.Char(string='Anchor Tag', help='Anchor tag for direct linking on the website (e.g., "premium-plan")')
    
    # Plan Configuration
    quota_mode = fields.Selection([
        ('unlimited', 'Unlimited'),
        ('bucket_counts', 'Session Buckets'),
        ('points', 'Points-Based')
    ], string='Quota Mode', default='unlimited', required=True, tracking=True)
    
    # Duration and Activation
    duration_days = fields.Integer(string='Duration (Days)', default=365, required=True, tracking=True)
    activation_policy = fields.Selection([
        ('immediate', 'Immediate'),
        ('first_attendance', 'First Attendance'),
        ('manual', 'Manual')
    ], string='Activation Policy', default='immediate', required=True, tracking=True)
    activation_policy_notes = fields.Text(string='Activation Policy Notes', tracking=True, translate=True,
                                         help='Additional notes about the activation policy that will be displayed on the website')
    
    # Club Type Permissions
    allowed_regular_offline = fields.Boolean(string='Allows Regular Offline', default=True, tracking=True)
    allowed_regular_online = fields.Boolean(string='Allows Regular Online', default=True, tracking=True)
    allowed_spclub = fields.Boolean(string='Allows Special Club', default=False, tracking=True)
    
    # Session Quotas (for bucket_counts mode)
    quota_offline = fields.Integer(string='Offline Sessions', default=0, tracking=True)
    quota_online = fields.Integer(string='Online Sessions', default=0, tracking=True)
    quota_sp = fields.Integer(string='Special Club Sessions', default=0, tracking=True)
    
    # Points Configuration (for points mode)
    points_start = fields.Integer(string='Starting Points', default=0, tracking=True)
    points_per_offline = fields.Integer(string='Points per Offline Session', default=3, tracking=True)
    points_per_online = fields.Integer(string='Points per Online Session', default=2, tracking=True)
    points_per_sp = fields.Integer(string='Points per Special Club Session', default=4, tracking=True)
    
    # Freeze Settings
    freeze_allowed = fields.Boolean(string='Freeze Allowed', default=False, tracking=True)
    freeze_min_days = fields.Integer(string='Minimum Freeze Days', default=7, tracking=True)
    freeze_max_total_days = fields.Integer(string='Maximum Total Freeze Days', default=30, tracking=True)
    
    # Pricing
    price_normal = fields.Monetary(string='Normal Price', currency_field='currency_id', default=0.0, required=True, tracking=True)
    price_first_timer = fields.Monetary(string='First Timer Price', currency_field='currency_id', default=0.0, tracking=True)
    
    # Upgrade Windows
    early_renew_window_days = fields.Integer(string='Early Renewal Window (Days)', default=30, tracking=True)
    upgrade_window_days = fields.Integer(string='Upgrade Window (Days)', default=60, tracking=True)
    first_timer_default_upgrade_ability = fields.Selection([
        ('yes', 'Yes'),
        ('no', 'No')
    ], string='First Timer Can Upgrade', default='yes', tracking=True)
    
    # Follow-up Configuration
    expiry_followup_days = fields.Char(
        string='Expiry Follow-up Days', 
        default='7', 
        tracking=True,
        help='Comma-separated list of days before expiry to create follow-up activities (e.g., "50,45,35,31")'
    )
    
    # Upgrade Configuration
    can_upgrade_to_ids = fields.Many2many('popcorn.membership.plan', 'membership_plan_upgrade_rel', 
                                         'from_plan_id', 'to_plan_id',
                                         string='Can Upgrade To', 
                                         domain="[('active', '=', True), ('id', '!=', id)]")
    
    # Discount Relationships
    discount_ids = fields.Many2many('popcorn.discount', 
                                   'popcorn_membership_plan_discount_rel',
                                   'plan_id', 'discount_id',
                                   string='Available Discounts',
                                   help='Discounts that can be applied to this membership plan')
    
    # Computed Fields
    display_name = fields.Char(string='Display Name', compute='_compute_display_name', store=True)
    plan_summary = fields.Text(string='Plan Summary', compute='_compute_plan_summary', store=True)
    
    # Currency
    currency_id = fields.Many2one('res.currency', string='Currency', 
                                 default=lambda self: self.env.company.currency_id)
    
    # Cover Image
    cover_image = fields.Binary(string='Cover Image', attachment=True, help='Cover image for the membership plan card')
    
    # Upgrade calculation fields
    unit_base_count = fields.Integer(string='Base Unit Count', 
                                   help='Base number of units for upgrade calculations')
    unit_value_fixed = fields.Monetary(string='Fixed Unit Value', currency_field='currency_id',
                                     help='Fixed value per unit for upgrade calculations')
    
    @api.depends('name', 'quota_mode', 'duration_days', 'quota_offline', 'quota_online', 'quota_sp', 'points_start')
    def _compute_display_name(self):
        """Compute a user-friendly display name for the membership plan"""
        for plan in self:
            if plan.quota_mode == 'unlimited':
                if plan.duration_days == 365:
                    plan.display_name = f"{plan.name} (Unlimited)"
                else:
                    plan.display_name = f"{plan.name} ({plan.duration_days} days)"
            elif plan.quota_mode == 'bucket_counts':
                total_sessions = (plan.quota_offline or 0) + (plan.quota_online or 0) + (plan.quota_sp or 0)
                plan.display_name = f"{plan.name} ({total_sessions} sessions)"
            elif plan.quota_mode == 'points':
                plan.display_name = f"{plan.name} ({plan.points_start} points)"
            else:
                plan.display_name = plan.name
    
    @api.depends('quota_mode', 'duration_days', 'quota_offline', 'quota_online', 'quota_sp', 'points_start', 'freeze_allowed', 'allowed_regular_offline', 'allowed_regular_online', 'allowed_spclub')
    def _compute_plan_summary(self):
        """Compute a comprehensive summary of the membership plan"""
        for plan in self:
            summary_parts = []
            
            # Basic plan info
            if plan.quota_mode == 'unlimited':
                summary_parts.append(f"Unlimited access for {plan.duration_days} days")
            elif plan.quota_mode == 'bucket_counts':
                sessions = []
                if plan.quota_offline:
                    sessions.append(f"{plan.quota_offline} offline")
                if plan.quota_online:
                    sessions.append(f"{plan.quota_online} online")
                if plan.quota_sp:
                    sessions.append(f"{plan.quota_sp} special club")
                summary_parts.append(f"Session-based: {', '.join(sessions)}")
            elif plan.quota_mode == 'points':
                summary_parts.append(f"Points-based: {plan.points_start} starting points")
            
            # Duration
            if plan.duration_days:
                summary_parts.append(f"Valid for {plan.duration_days} days")
            
            # Club access
            access_types = []
            if plan.allowed_regular_offline:
                access_types.append("Regular Offline")
            if plan.allowed_regular_online:
                access_types.append("Regular Online")
            if plan.allowed_spclub:
                access_types.append("Special Club")
            
            if access_types:
                summary_parts.append(f"Access: {', '.join(access_types)}")
            
            # Freeze policy
            if plan.freeze_allowed:
                summary_parts.append(f"Freeze allowed: {plan.freeze_min_days}-{plan.freeze_max_total_days} days")
            
            # Pricing
            if plan.price_normal > 0:
                summary_parts.append(f"Price: ${plan.price_normal:.2f}")
            if plan.price_first_timer > 0 and plan.price_first_timer != plan.price_normal:
                summary_parts.append(f"First Timer: ${plan.price_first_timer:.2f}")
            
            plan.plan_summary = " | ".join(summary_parts)
    
    @api.constrains('quota_mode', 'quota_offline', 'quota_online', 'quota_sp')
    def _check_quota_consistency(self):
        """Ensure quota fields are consistent with quota mode"""
        for plan in self:
            if plan.quota_mode == 'bucket_counts':
                total_quota = (plan.quota_offline or 0) + (plan.quota_online or 0) + (plan.quota_sp or 0)
                if total_quota <= 0:
                    raise ValidationError(_('Bucket-based plans must have at least one session quota'))
    
    @api.constrains('quota_mode', 'points_start')
    def _check_points_consistency(self):
        """Ensure points fields are consistent with quota mode"""
        for plan in self:
            if plan.quota_mode == 'points':
                if not plan.points_start or plan.points_start <= 0:
                    raise ValidationError(_('Points-based plans must have a positive starting points value'))
    
    @api.constrains('duration_days')
    def _check_duration_positive(self):
        """Ensure duration is positive for membership plans"""
        for plan in self:
            if plan.duration_days <= 0:
                raise ValidationError(_('Membership plans must have a positive duration'))
    
    @api.constrains('freeze_min_days', 'freeze_max_total_days')
    def _check_freeze_consistency(self):
        """Ensure freeze settings are consistent"""
        for plan in self:
            if plan.freeze_allowed:
                if plan.freeze_min_days <= 0:
                    raise ValidationError(_('Minimum freeze days must be positive'))
                if plan.freeze_max_total_days <= 0:
                    raise ValidationError(_('Maximum total freeze days must be positive'))
                if plan.freeze_min_days > plan.freeze_max_total_days:
                    raise ValidationError(_('Minimum freeze days cannot exceed maximum total freeze days'))
    
    @api.constrains('price_normal', 'price_first_timer')
    def _check_price_consistency(self):
        """Ensure pricing is consistent"""
        for plan in self:
            if plan.price_normal < 0:
                raise ValidationError(_('Normal price cannot be negative'))
            if plan.price_first_timer < 0:
                raise ValidationError(_('First timer price cannot be negative'))
    
    @api.onchange('quota_mode')
    def _onchange_quota_mode(self):
        """Handle changes to quota mode"""
        if self.quota_mode == 'unlimited':
            # Reset quota fields for unlimited plans
            self.quota_offline = 0
            self.quota_online = 0
            self.quota_sp = 0
            self.points_start = 0
        elif self.quota_mode == 'bucket_counts':
            # Reset points for bucket plans
            self.points_start = 0
        elif self.quota_mode == 'points':
            # Reset quotas for points plans
            self.quota_offline = 0
            self.quota_online = 0
            self.quota_sp = 0
    
    def get_membership_benefits(self):
        """Get a structured list of membership benefits"""
        self.ensure_one()
        
        benefits = []
        
        # Core benefits
        if self.quota_mode == 'unlimited':
            benefits.append({
                'type': 'unlimited',
                'title': 'Unlimited Access',
                'description': f'Unlimited access to all allowed club types for {self.duration_days} days'
            })
        elif self.quota_mode == 'bucket_counts':
            if self.quota_offline:
                benefits.append({
                    'type': 'quota',
                    'title': 'Offline Sessions',
                    'description': f'{self.quota_offline} offline club sessions'
                })
            if self.quota_online:
                benefits.append({
                    'type': 'quota',
                    'title': 'Online Sessions',
                    'description': f'{self.quota_online} online sessions'
                })
            if self.quota_sp:
                benefits.append({
                    'type': 'quota',
                    'title': 'Special Club',
                    'description': f'{self.quota_sp} special club sessions'
                })
        elif self.quota_mode == 'points':
            benefits.append({
                'type': 'points',
                'title': 'Flexible Points',
                'description': f'{self.points_start} points to spend across different club types'
            })
        
        # Additional benefits
        if self.freeze_allowed:
            benefits.append({
                'type': 'feature',
                'title': 'Freeze Option',
                'description': f'Can freeze membership for {self.freeze_min_days}-{self.freeze_max_total_days} days'
            })
        
        if self.upgrade_window_days > 0:
            benefits.append({
                'type': 'feature',
                'title': 'Upgrade Window',
                'description': f'{self.upgrade_window_days} days to upgrade with discount'
            })
        
        return benefits
    
    def get_available_discounts(self, customer_partner=None):
        """Get all available discounts for this membership plan"""
        self.ensure_one()
        
        # Get discounts linked to this plan (exclude partner-specific discounts)
        linked_discounts = self.discount_ids.filtered(lambda d: d.is_valid and not d.partner_id)
        
        # Get global discounts (not linked to specific plans, and not partner-specific)
        global_discounts = self.env['popcorn.discount'].search([
            ('is_valid', '=', True),
            ('membership_plan_ids', '=', False),
            ('partner_id', '=', False)  # Exclude first-timer discounts
        ])
        
        all_discounts = linked_discounts | global_discounts
        
        # Filter by customer type if customer is provided
        if customer_partner:
            filtered_discounts = self.env['popcorn.discount']
            for discount in all_discounts:
                if discount.customer_type == 'all':
                    filtered_discounts |= discount
                elif discount.customer_type == 'first_timer' and customer_partner.is_first_timer:
                    filtered_discounts |= discount
                elif discount.customer_type == 'existing' and not customer_partner.is_first_timer:
                    filtered_discounts |= discount
                elif discount.customer_type == 'new' and customer_partner.is_first_timer:
                    filtered_discounts |= discount
            all_discounts = filtered_discounts
        
        return all_discounts
    
    def get_discounted_price(self, discount, customer_partner=None):
        """Calculate discounted price using a specific discount"""
        self.ensure_one()
        
        if not discount or not discount.is_valid:
            return self.price_normal
        
        # Check if discount applies to this plan
        if discount.membership_plan_ids and self not in discount.membership_plan_ids:
            return self.price_normal
        
        # Check customer type restrictions
        if customer_partner and discount.customer_type != 'all':
            if discount.customer_type == 'first_timer' and not customer_partner.is_first_timer:
                return self.price_normal
            elif discount.customer_type == 'existing' and customer_partner.is_first_timer:
                return self.price_normal
            elif discount.customer_type == 'new' and customer_partner.is_first_timer:
                return self.price_normal
        
        # Calculate discount
        if discount.discount_type == 'percentage':
            discount_amount = self.price_normal * (discount.discount_value / 100)
            return max(0, self.price_normal - discount_amount)
        
        elif discount.discount_type == 'fixed_amount':
            return max(0, self.price_normal - discount.discount_value)
        
        elif discount.discount_type == 'first_timer':
            return self.price_first_timer
        
        elif discount.discount_type == 'upgrade':
            return max(0, self.price_normal - discount.discount_value)
        
        return self.price_normal
    
    def get_best_discount_price(self, customer_partner=None):
        """Get the best discounted price for this plan"""
        self.ensure_one()
        
        available_discounts = self.get_available_discounts(customer_partner)
        if not available_discounts:
            return self.price_normal, None
        
        best_price = self.price_normal
        best_discount = None
        
        for discount in available_discounts:
            discounted_price = discount.get_discounted_price(self, self.price_normal, customer_partner)
            if discounted_price < best_price:
                best_price = discounted_price
                best_discount = discount
        
        return best_price, best_discount
    
    def get_best_discount_with_extra_days(self, customer_partner=None):
        """Get the best discount including extra days information"""
        self.ensure_one()
        
        available_discounts = self.get_available_discounts(customer_partner)
        if not available_discounts:
            return self.price_normal, None, 0
        
        best_price = self.price_normal
        best_discount = None
        total_extra_days = 0
        best_value = 0  # Track the best value (price savings or extra days)
        
        # First pass: find the best price discount
        for discount in available_discounts:
            discounted_price = discount.get_discounted_price(self, self.price_normal, customer_partner)
            extra_days = discount.get_extra_days(self, customer_partner)
            
            # Calculate value: price savings or extra days
            if discount.discount_type == 'extra_days' and extra_days > 0:
                # For extra days, consider each day as equivalent to 1 unit of value
                discount_value = extra_days
            else:
                # For price discounts, calculate the savings
                discount_value = self.price_normal - discounted_price
            
            # Choose the discount with the highest value
            if discount_value > best_value:
                best_price = discounted_price
                best_discount = discount
                total_extra_days = extra_days
                best_value = discount_value
        
        # Second pass: collect all available extra days from any discount
        # This ensures extra days are applied even if they're not from the "best" discount
        all_extra_days = 0
        for discount in available_discounts:
            extra_days = discount.get_extra_days(self, customer_partner)
            if extra_days > 0:
                all_extra_days += extra_days
        
        # Use the maximum of the best discount's extra days or all available extra days
        total_extra_days = max(total_extra_days, all_extra_days)
        
        return best_price, best_discount, total_extra_days

