# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta

class PopcornMembership(models.Model):
    """Membership instances for customers"""
    _name = 'popcorn.membership'
    _description = 'Popcorn Club Membership'
    _order = 'activation_date desc nulls last'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'display_name'

    # Core fields
    partner_id = fields.Many2one('res.partner', string='Member', required=True)
    partner_phone = fields.Char(string='Phone', related='partner_id.phone', readonly=True, store=True)
    membership_plan_id = fields.Many2one('popcorn.membership.plan', string='Membership Plan', required=True)
    state = fields.Selection([
        ('pending', 'Pending'),
        ('pending_payment', 'Pending Payment'),
        ('active', 'Active'),
        ('frozen', 'Frozen'),
        ('expired', 'Expired')
    ], string='Status', default='pending', required=True, tracking=True)
    
    # Purchase details
    purchase_price_paid = fields.Monetary(string='Purchase Price', currency_field='currency_id', required=True)
    price_tier = fields.Selection([
        ('normal', 'Normal'),
        ('first_timer', 'First Timer'),
        ('discount', 'Discount Applied')
    ], string='Price Tier', required=True, default='normal')
    applied_discount_id = fields.Many2one('popcorn.discount', string='Applied Discount', readonly=True)
    purchase_channel = fields.Selection([
        ('online', 'Online'),
        ('pitch_day', 'Pitch Day'),
        ('other', 'Other')
    ], string='Purchase Channel', required=True, default='online')
    
    # Dates
    activation_date = fields.Date(string='Activation Date')
    end_date_base = fields.Date(string='Base End Date', compute='_compute_end_date_base', store=True)
    
    # Freeze & extensions
    freeze_total_days_used = fields.Integer(string='Total Freeze Days Used', default=0)
    freeze_active = fields.Boolean(string='Freeze Active', default=False)
    freeze_start = fields.Date(string='Freeze Start Date')
    freeze_end = fields.Date(string='Freeze End Date')
    extra_days_extension = fields.Integer(string='Extra Days Extension', default=0)
    
    # Manual adjustments (tracked in chatter)
    adj_offline = fields.Integer(string='Offline Adjustment', default=0, tracking=True)
    adj_online = fields.Integer(string='Online Adjustment', default=0, tracking=True)
    adj_sp = fields.Integer(string='Special Club Adjustment', default=0, tracking=True)
    adj_points = fields.Integer(string='Points Adjustment', default=0, tracking=True)
    
    # Upgrade eligibility
    upgrade_discount_allowed = fields.Boolean(string='Upgrade Discount Allowed', default=False)
    first_timer_customer = fields.Boolean(string='First Timer Customer', compute='_compute_first_timer_customer', store=True)
    
    # Computed fields
    remaining_offline = fields.Integer(string='Remaining Offline Sessions', compute='_compute_remaining_usage')
    remaining_online = fields.Integer(string='Remaining Online Sessions', compute='_compute_remaining_usage')
    remaining_sp = fields.Integer(string='Remaining Special Club Sessions', compute='_compute_remaining_usage')
    points_remaining = fields.Integer(string='Points Remaining', compute='_compute_remaining_usage')
    effective_end_date = fields.Date(string='Effective End Date', compute='_compute_effective_end_date', store=True)
    
    # Display name
    display_name = fields.Char(string='Display Name', compute='_compute_display_name', store=True)
    
    # Currency for monetary fields
    currency_id = fields.Many2one('res.currency', string='Currency', 
                                 default=lambda self: self.env.company.currency_id)
    
    # Payment tracking
    payment_transaction_id = fields.Many2one('payment.transaction', string='Payment Transaction', readonly=True)
    payment_reference = fields.Char(string='Payment Reference', readonly=True)
    
    # Contract relationship
    contract_id = fields.Many2one('popcorn.contract', string='Contract', ondelete='cascade')
    
    # Related fields for convenience
    plan_duration_days = fields.Integer(string='Plan Duration (Days)', related='membership_plan_id.duration_days')
    plan_quota_mode = fields.Selection(string='Quota Mode', related='membership_plan_id.quota_mode')
    plan_allowed_regular_offline = fields.Boolean(string='Allows Regular Offline', related='membership_plan_id.allowed_regular_offline')
    plan_allowed_regular_online = fields.Boolean(string='Allows Regular Online', related='membership_plan_id.allowed_regular_online')
    plan_allowed_spclub = fields.Boolean(string='Allows Special Club', related='membership_plan_id.allowed_spclub')
    
    # Computed fields for duration
    total_duration_days = fields.Integer(string='Total Duration (Days)', compute='_compute_total_duration_days', store=True)
    
    @api.depends('membership_plan_id.duration_days', 'extra_days_extension')
    def _compute_total_duration_days(self):
        """Compute total duration including extra days"""
        for membership in self:
            base_duration = membership.membership_plan_id.duration_days or 0
            extra_days = membership.extra_days_extension or 0
            membership.total_duration_days = base_duration + extra_days
    
    @api.depends('activation_date', 'total_duration_days')
    def _compute_end_date_base(self):
        for membership in self:
            if membership.activation_date and membership.total_duration_days > 0:
                membership.end_date_base = membership.activation_date + timedelta(days=membership.total_duration_days)
            else:
                membership.end_date_base = False
    
    @api.depends('end_date_base', 'freeze_total_days_used')
    def _compute_effective_end_date(self):
        for membership in self:
            if membership.end_date_base:
                # Extra days are now included in end_date_base, so we only add freeze days
                membership.effective_end_date = membership.end_date_base + timedelta(days=membership.freeze_total_days_used)
            else:
                membership.effective_end_date = False
    
    @api.depends('partner_id.is_first_timer')
    def _compute_first_timer_customer(self):
        for membership in self:
            # Use the contact's first timer status
            membership.first_timer_customer = membership.partner_id.is_first_timer if membership.partner_id else False
    
    @api.depends('adj_offline', 'adj_online', 'adj_sp', 'adj_points', 'membership_plan_id.quota_mode', 'membership_plan_id.quota_offline', 'membership_plan_id.quota_online', 'membership_plan_id.quota_sp', 'membership_plan_id.points_start')
    def _compute_remaining_usage(self):
        for membership in self:
            plan = membership.membership_plan_id
            
            # Set default values first
            membership.remaining_offline = 0
            membership.remaining_online = 0
            membership.remaining_sp = 0
            membership.points_remaining = 0
            
            # Only compute if we have a valid plan
            if not plan or not plan.quota_mode:
                continue
                
            if plan.quota_mode == 'unlimited':
                membership.remaining_offline = -1  # -1 indicates unlimited
                membership.remaining_online = -1
                membership.remaining_sp = -1
                membership.points_remaining = -1
                
            elif plan.quota_mode == 'bucket_counts':
                # Calculate used sessions from registrations
                used_offline = membership._count_used_sessions('regular_offline')
                used_online = membership._count_used_sessions('regular_online')
                used_sp = membership._count_used_sessions('spclub')
                
                # Use safe access with defaults
                quota_offline = getattr(plan, 'quota_offline', 0) or 0
                quota_online = getattr(plan, 'quota_online', 0) or 0
                quota_sp = getattr(plan, 'quota_sp', 0) or 0
                
                membership.remaining_offline = max(0, quota_offline - used_offline + membership.adj_offline)
                membership.remaining_online = max(0, quota_online - used_online + membership.adj_online)
                membership.remaining_sp = max(0, quota_sp - used_sp + membership.adj_sp)
                membership.points_remaining = 0
                
            elif plan.quota_mode == 'points':
                used_points = membership._count_used_points()
                membership.remaining_offline = 0
                membership.remaining_online = 0
                membership.remaining_sp = 0
                points_start = getattr(plan, 'points_start', 0) or 0
                membership.points_remaining = max(0, points_start - used_points + membership.adj_points)
    
    @api.depends('partner_id', 'membership_plan_id')
    def _compute_display_name(self):
        for membership in self:
            partner_name = membership.partner_id.name if membership.partner_id else 'Unknown'
            plan_name = membership.membership_plan_id.name if membership.membership_plan_id else 'Unknown Plan'
            membership.display_name = f"{partner_name} - {plan_name}"
    
    def _count_used_sessions(self, club_type):
        """Count used sessions of a specific club type using event tags - robust approach"""
        # If this is a new record, return 0
        if not self.id or self.id < 0:
            return 0
        
        try:
            # Only count registrations that went through proper consumption flow
            # Exclude imported registrations and registrations without proper state
            registrations = self.env['event.registration'].sudo().search([
                ('membership_id', '=', self.id),
                ('consumption_state', '=', 'consumed'),
                ('state', 'in', ['open', 'confirmed', 'done']),  # Only count valid registrations
                ('is_imported', '=', False)  # Exclude imported registrations
            ])
            
            count = 0
            for reg in registrations:
                # Use the computed club_type field from the registration, not from the event
                if reg.club_type == club_type:
                    count += 1
            
            return count
        except Exception:
            # If access denied, return 0
            return 0
    
    def _count_used_points(self):
        """Count used points from consumed registrations using event club_type field"""
        # If this is a new record, return 0
        if not self.id or self.id < 0:
            return 0
            
        try:
            # Only count registrations that went through proper consumption flow
            # Exclude imported registrations and registrations without proper state
            registrations = self.env['event.registration'].sudo().search([
                ('membership_id', '=', self.id),
                ('consumption_state', '=', 'consumed'),
                ('state', 'in', ['open', 'confirmed', 'done']),  # Only count valid registrations
                ('is_imported', '=', False)  # Exclude imported registrations
            ])
            
            total_points = 0
            for reg in registrations:
                # Use the computed club_type field from the registration, not from the event
                if reg.club_type:
                    club_type = reg.club_type
                    plan = self.membership_plan_id
                    if club_type == 'regular_offline':
                        points = plan.points_per_offline
                        total_points += points
                    elif club_type == 'regular_online':
                        points = plan.points_per_online
                        total_points += points
                    elif club_type == 'spclub':
                        points = plan.points_per_sp
                        total_points += points
        
            return total_points
        except Exception:
            # If access denied, return 0
            return 0
    
    @api.model
    def create(self, vals):
        """Override create to set default values based on purchase channel and first-timer status"""
        partner_id = vals.get('partner_id')
        purchase_channel = vals.get('purchase_channel')
        
        # Check if customer is a first-timer (no prior club attendance AND no prior memberships)
        is_first_timer = self._is_first_timer_customer(partner_id)
        
        # Set upgrade discount allowed based on first-timer status
        # First-timers get upgrade discount ability by default
        vals['upgrade_discount_allowed'] = is_first_timer
        
        membership = super().create(vals)
        
        # Update partner's first timer status after creating membership
        if partner_id:
            self.env['res.partner']._update_first_timer_status(partner_id)
        
        return membership
    
    @api.model
    def _is_first_timer_customer(self, partner_id):
        """Check if customer is a first-timer (delegates to partner model)"""
        return self.env['res.partner']._is_first_timer_customer(partner_id)
    
    def action_activate(self):
        """Activate a pending membership"""
        self.ensure_one()
        if self.state not in ['pending', 'pending_payment']:
            raise UserError(_('Only pending or pending payment memberships can be activated'))
        
        self.write({
            'state': 'active',
            'activation_date': fields.Date.today()
        })
        
        # Log the manual activation
        self.message_post(
            body=_('Membership manually activated by staff')
        )
    
    def action_activate_pending_payment(self):
        """Activate a membership that was pending payment"""
        self.ensure_one()
        if self.state != 'pending_payment':
            raise UserError(_('Only pending payment memberships can be activated'))
        
        self.write({
            'state': 'active',
            'activation_date': fields.Date.today()
        })
        
        # Log the manual activation from pending payment
        self.message_post(
            body=_('Membership activated manually from pending payment status by staff')
        )
    
    def action_freeze(self, freeze_days):
        """Freeze membership for specified days"""
        self.ensure_one()
        plan = self.membership_plan_id
        
        if not plan.freeze_allowed:
            raise UserError(_('This plan does not allow freezing'))
        
        if freeze_days < plan.freeze_min_days:
            raise UserError(_('Minimum freeze period is %s days') % plan.freeze_min_days)
        
        if self.freeze_total_days_used + freeze_days > plan.freeze_max_total_days:
            raise UserError(_('Total freeze days cannot exceed %s') % plan.freeze_max_total_days)
        
        if self.freeze_active:
            raise UserError(_('Membership is already frozen'))
        
        freeze_start = fields.Date.today()
        # Freeze end should be start + freeze_days - 1 (since the start day counts as day 1)
        freeze_end = freeze_start + timedelta(days=freeze_days - 1)
        
        # Debug logging
        print(f"Freezing membership {self.id}: start={freeze_start}, end={freeze_end}, days={freeze_days}")
        
        self.write({
            'freeze_active': True,
            'freeze_start': freeze_start,
            'freeze_end': freeze_end,
            'freeze_total_days_used': self.freeze_total_days_used + freeze_days
        })
    
    def action_unfreeze(self):
        """End active freeze period"""
        self.ensure_one()
        if not self.freeze_active:
            raise UserError(_('Membership is not currently frozen'))
        
        # Just clear the freeze state - freeze_total_days_used already contains the freeze days
        # that were added when the freeze was initiated, so we don't need to add them again
        self.write({
            'freeze_active': False,
            'freeze_start': False,
            'freeze_end': False,
            # freeze_total_days_used remains unchanged - it already contains the correct total
        })
    
    def action_expire(self):
        """Mark membership as expired"""
        self.ensure_one()
        if self.state not in ['active', 'frozen']:
            raise UserError(_('Only active or frozen memberships can be expired'))
        
        self.write({'state': 'expired'})
    
    # Staff manual adjustment methods
    def action_extend_membership(self, extra_days):
        """Staff action to manually extend membership expiration"""
        self.ensure_one()
        if extra_days <= 0:
            raise UserError(_('Extension days must be positive'))
        
        self.write({
            'extra_days_extension': self.extra_days_extension + extra_days
        })
        
        # Log the action
        self.message_post(
            body=_('Membership extended by %s days by staff. New effective end date: %s') % 
                 (extra_days, self.effective_end_date)
        )
        
        return True
    
    def action_adjust_offline_quota(self, adjustment):
        """Staff action to manually adjust offline quota"""
        self.ensure_one()
        if self.plan_quota_mode != 'bucket_counts':
            raise UserError(_('This membership plan does not use bucket quotas'))
        
        self.write({
            'adj_offline': self.adj_offline + adjustment
        })
        
        # Log the action
        action = 'added' if adjustment > 0 else 'removed'
        self.message_post(
            body=_('Staff %s %s offline sessions. New remaining: %s') % 
                 (action, abs(adjustment), self.remaining_offline)
        )
        
        return True
    
    def action_adjust_online_quota(self, adjustment):
        """Staff action to manually adjust online quota"""
        self.ensure_one()
        if self.plan_quota_mode != 'bucket_counts':
            raise UserError(_('This membership plan does not use bucket quotas'))
        
        self.write({
            'adj_online': self.adj_online + adjustment
        })
        
        # Log the action
        action = 'added' if adjustment > 0 else 'removed'
        self.message_post(
            body=_('Staff %s %s online sessions. New remaining: %s') % 
                 (action, abs(adjustment), self.remaining_online)
        )
        
        return True
    
    def action_adjust_sp_quota(self, adjustment):
        """Staff action to manually adjust SP club quota"""
        self.ensure_one()
        if self.plan_quota_mode != 'bucket_counts':
            raise UserError(_('This membership plan does not use bucket quotas'))
        
        self.write({
            'adj_sp': self.adj_sp + adjustment
        })
        
        # Log the action
        action = 'added' if adjustment > 0 else 'removed'
        self.message_post(
            body=_('Staff %s %s SP club sessions. New remaining: %s') % 
                 (action, abs(adjustment), self.remaining_sp)
        )
        
        return True
    
    def action_adjust_points(self, adjustment):
        """Staff action to manually adjust points"""
        self.ensure_one()
        if self.plan_quota_mode != 'points':
            raise UserError(_('This membership plan does not use points'))
        
        self.write({
            'adj_points': self.adj_points + adjustment
        })
        
        # Log the action
        action = 'added' if adjustment > 0 else 'removed'
        self.message_post(
            body=_('Staff %s %s points. New remaining: %s') % 
                 (action, abs(adjustment), self.points_remaining)
        )
        
        return True
    
    def action_toggle_upgrade_ability(self):
        """Staff action to toggle upgrade discount ability"""
        self.ensure_one()
        new_value = not self.upgrade_discount_allowed
        
        self.write({
            'upgrade_discount_allowed': new_value
        })
        
        # Log the action
        status = 'enabled' if new_value else 'disabled'
        self.message_post(
            body=_('Staff %s upgrade discount ability') % status
        )
        
        return True
    
    def get_upgrade_quote(self, target_plan):
        """Calculate upgrade price to target plan"""
        self.ensure_one()
        if not self.upgrade_discount_allowed:
            return target_plan.price_first_timer
        
        # Check upgrade window
        if self.activation_date:
            upgrade_deadline = self.activation_date + timedelta(days=self.membership_plan_id.upgrade_window_days)
            if fields.Date.today() > upgrade_deadline:
                return target_plan.price_first_timer  # No discount outside window
        
        # Calculate upgrade price based on plan type
        if self.membership_plan_id.quota_mode == 'bucket_counts':
            return self._calculate_bucket_upgrade_price(target_plan)
        elif self.membership_plan_id.quota_mode == 'points':
            return self._calculate_points_upgrade_price(target_plan)
        elif self.membership_plan_id.quota_mode == 'unlimited':
            return self._calculate_gold_upgrade_price(target_plan)
        
        return target_plan.price_first_timer
    
    def _calculate_bucket_upgrade_price(self, target_plan):
        """Calculate upgrade price for bucket-based plans (Experience, Online)"""
        plan = self.membership_plan_id
        if not plan.unit_base_count:
            return target_plan.price_first_timer
        
        # Calculate remaining units
        used_offline = self._count_used_sessions('regular_offline')
        used_online = self._count_used_sessions('regular_online')
        used_sp = self._count_used_sessions('spclub')
        
        total_used = used_offline + used_online + used_sp
        units_left = max(0, plan.unit_base_count - total_used)
        
        # Calculate unit value
        if plan.unit_value_fixed > 0:
            unit_value = plan.unit_value_fixed
        else:
            unit_value = self.purchase_price_paid / plan.unit_base_count
        
        upgrade_price = target_plan.price_first_timer - (unit_value * units_left)
        return max(0, upgrade_price)
    
    def _calculate_points_upgrade_price(self, target_plan):
        """Calculate upgrade price for Freedom plan"""
        plan = self.membership_plan_id
        if not plan.unit_base_count:
            return target_plan.price_first_timer
        
        # Calculate remaining units from points
        points_remaining = self.points_remaining
        units_left = points_remaining / 3  # Assuming 3 points = 1 club unit
        
        unit_value = self.purchase_price_paid / plan.unit_base_count
        upgrade_price = target_plan.price_first_timer - (unit_value * units_left)
        return max(0, upgrade_price)
    
    def _calculate_gold_upgrade_price(self, target_plan):
        """Calculate upgrade price for Gold plans (days pro-rata)"""
        if not self.activation_date or not self.membership_plan_id.duration_days:
            return target_plan.price_first_timer
        
        # Calculate used days
        days_since_activation = (fields.Date.today() - self.activation_date).days
        old_used_days = min(days_since_activation, self.membership_plan_id.duration_days)
        
        # Calculate pro-rata prices
        old_daily_rate = self.purchase_price_paid / self.membership_plan_id.duration_days
        new_daily_rate = target_plan.price_first_timer / target_plan.duration_days
        
        # Calculate upgrade price
        old_remaining_value = old_daily_rate * (self.membership_plan_id.duration_days - old_used_days)
        new_remaining_value = new_daily_rate * (target_plan.duration_days - old_used_days)
        
        upgrade_price = new_remaining_value - old_remaining_value
        return max(0, upgrade_price)
    
    @api.model
    def _cron_expire_memberships(self):
        """Cron job to expire memberships past their effective end date"""
        expired_memberships = self.search([
            ('state', 'in', ['active', 'frozen']),
            ('effective_end_date', '<', fields.Date.today())
        ])
        
        for membership in expired_memberships:
            membership.action_expire()
    
    @api.model
    def _cron_check_renewal_eligibility(self):
        """Cron job to check renewal eligibility and send notifications"""
        # Check Gold plans for early renewal
        gold_memberships = self.search([
            ('state', '=', 'active'),
            ('membership_plan_id.quota_mode', '=', 'unlimited'),
            ('membership_plan_id.early_renew_window_days', '>', 0)
        ])
        
        for membership in gold_memberships:
            if membership.end_date_base:
                days_until_expiry = (membership.end_date_base - fields.Date.today()).days
                if days_until_expiry <= membership.membership_plan_id.early_renew_window_days:
                    # Send renewal notification (implement notification logic)
                    pass
        
        # Check Freedom plans for low points
        freedom_memberships = self.search([
            ('state', '=', 'active'),
            ('membership_plan_id.quota_mode', '=', 'points')
        ])
        
        for membership in freedom_memberships:
            if membership.points_remaining <= 15:
                # Send low points notification (implement notification logic)
                pass
    
    def action_toggle_upgrade_discount(self):
        """Staff action to manually toggle upgrade discount ability"""
        self.ensure_one()
        new_value = not self.upgrade_discount_allowed
        
        self.write({
            'upgrade_discount_allowed': new_value
        })
        
        # Log the action
        status = 'enabled' if new_value else 'disabled'
        self.message_post(
            body=_('Staff %s upgrade discount ability') % status
        )
        
        return True
    
    def action_create_contract(self):
        """Create a contract for this membership"""
        self.ensure_one()
        if self.contract_id:
            raise UserError(_('A contract already exists for this membership'))
        
        # Create contract with default text
        contract_vals = {
            'membership_id': self.id,
            'contract_type': 'standard',
            'contract_text': self._get_default_contract_text(),
            'state': 'draft'
        }
        
        contract = self.env['popcorn.contract'].create(contract_vals)
        
        # Link the contract to the membership
        self.write({'contract_id': contract.id})
        
        # Log the action
        self.message_post(
            body=_('Contract created for this membership')
        )
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Contract'),
            'res_model': 'popcorn.contract',
            'res_id': contract.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_view_contract(self):
        """View the contract for this membership"""
        self.ensure_one()
        if not self.contract_id:
            raise UserError(_('No contract exists for this membership'))
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Contract'),
            'res_model': 'popcorn.contract',
            'res_id': self.contract_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def _get_default_contract_text(self):
        """Get default contract text based on membership plan"""
        plan = self.membership_plan_id
        if not plan:
            return _('Standard membership contract terms and conditions.')
        
        contract_text = f"""
        <h2>Membership Contract</h2>
        <h3>Plan: {plan.name}</h3>
        <p><strong>Member:</strong> {self.partner_id.name if self.partner_id else 'N/A'}</p>
        <p><strong>Purchase Price:</strong> {self.purchase_price_paid} {self.currency_id.symbol if self.currency_id else ''}</p>
        <p><strong>Duration:</strong> {plan.duration_days} days</p>
        
        <h3>Terms and Conditions:</h3>
        <ul>
            <li>This membership is valid for {plan.duration_days} days from the activation date.</li>
            <li>The member agrees to abide by all club rules and regulations.</li>
            <li>Membership benefits are subject to the terms of the selected plan.</li>
            <li>Refunds are subject to the club's refund policy.</li>
        </ul>
        
        <h3>Plan Details:</h3>
        <p><strong>Quota Mode:</strong> {dict(plan._fields['quota_mode'].selection)[plan.quota_mode]}</p>
        """
        
        if plan.quota_mode == 'bucket_counts':
            contract_text += f"""
            <ul>
                <li>Offline Sessions: {plan.quota_offline or 0}</li>
                <li>Online Sessions: {plan.quota_online or 0}</li>
                <li>Special Club Sessions: {plan.quota_sp or 0}</li>
            </ul>
            """
        elif plan.quota_mode == 'points':
            contract_text += f"""
            <ul>
                <li>Starting Points: {plan.points_start or 0}</li>
                <li>Points per Offline Session: {plan.points_per_offline or 0}</li>
                <li>Points per Online Session: {plan.points_per_online or 0}</li>
                <li>Points per Special Club Session: {plan.points_per_sp or 0}</li>
            </ul>
            """
        elif plan.quota_mode == 'unlimited':
            contract_text += """
            <ul>
                <li>Unlimited access to all club activities</li>
            </ul>
            """
        
        contract_text += """
        <p><strong>Signature:</strong> By signing this contract, both parties agree to the terms and conditions outlined above.</p>
        """
        
        return contract_text
    
    def apply_discount(self, discount):
        """Apply a discount to this membership"""
        self.ensure_one()
        
        if not discount or not discount.is_valid:
            raise UserError(_('Invalid or expired discount'))
        
        # Check if discount applies to this plan
        if discount.membership_plan_ids and self.membership_plan_id not in discount.membership_plan_ids:
            raise UserError(_('This discount does not apply to the selected membership plan'))
        
        # Check customer type restrictions
        if discount.customer_type != 'all':
            if discount.customer_type == 'first_timer' and not self.partner_id.is_first_timer:
                raise UserError(_('This discount is only available for first-time customers'))
            elif discount.customer_type == 'existing' and self.partner_id.is_first_timer:
                raise UserError(_('This discount is only available for existing customers'))
            elif discount.customer_type == 'new' and self.partner_id.is_first_timer:
                raise UserError(_('This discount is only available for new customers'))
        
        # Calculate discounted price
        discounted_price = self.membership_plan_id.get_discounted_price(discount, self.partner_id)
        
        # Update membership with discount
        self.write({
            'purchase_price_paid': discounted_price,
            'price_tier': 'discount',
            'applied_discount_id': discount.id
        })
        
        # Increment discount usage
        discount.action_increment_usage()
        
        # Log the discount application
        self.message_post(
            body=_('Discount "%s" applied. New price: %s %s') % 
                 (discount.name, discounted_price, self.currency_id.symbol if self.currency_id else '')
        )
        
        return True
    
    def remove_discount(self):
        """Remove applied discount and revert to normal pricing"""
        self.ensure_one()
        
        if not self.applied_discount_id:
            raise UserError(_('No discount is currently applied to this membership'))
        
        # Revert to normal price
        self.write({
            'purchase_price_paid': self.membership_plan_id.price_normal,
            'price_tier': 'normal',
            'applied_discount_id': False
        })
        
        # Log the discount removal
        self.message_post(
            body=_('Discount removed. Reverted to normal pricing: %s %s') % 
                 (self.purchase_price_paid, self.currency_id.symbol if self.currency_id else '')
        )
        
        return True
