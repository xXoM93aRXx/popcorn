# -*- coding: utf-8 -*-

import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta, time
import pytz

_logger = logging.getLogger(__name__)

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
        ('pending_buy_together', 'Pending Buy-Together'),
        ('pending_student_verification', 'Pending Student Verification'),
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
    # Buy-Together linking
    buy_together_discount_id = fields.Many2one('popcorn.discount', string='Buy-Together Discount', readonly=True)
    buy_together_partner_id = fields.Many2one('res.partner', string='Buy-Together Partner', readonly=True,
                                              help='The partner who purchased together with this member')
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
    freeze_is_penalty = fields.Boolean(
        string='Penalty Freeze',
        default=False,
        copy=False,
        help='If enabled, this freeze was applied as a policy penalty and cannot be unfrozen by portal users.'
    )
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
    contract_id = fields.Many2one('popcorn.contract', string='Contract', ondelete='set null')

    # Student verification
    student_card_attachment_id = fields.Many2one('ir.attachment', string='Student Card', ondelete='set null',
        help='Student ID card uploaded at checkout for verification by staff.')
    student_card_image = fields.Binary(string='Student Card Preview',
        compute='_compute_student_card_image', store=False,
        help='Image preview of the uploaded student card (images only).')
    id_card_attachment_id = fields.Many2one('ir.attachment', string='ID Card', ondelete='set null',
        help='Government ID card uploaded at checkout for verification by staff.')
    id_card_image = fields.Binary(string='ID Card Preview',
        compute='_compute_id_card_image', store=False,
        help='Image preview of the uploaded ID card (images only).')

    @api.depends('student_card_attachment_id')
    def _compute_student_card_image(self):
        for rec in self:
            att = rec.student_card_attachment_id
            if att and att.mimetype and att.mimetype.startswith('image/'):
                rec.student_card_image = att.datas
            else:
                rec.student_card_image = False

    @api.depends('id_card_attachment_id')
    def _compute_id_card_image(self):
        for rec in self:
            att = rec.id_card_attachment_id
            if att and att.mimetype and att.mimetype.startswith('image/'):
                rec.id_card_image = att.datas
            else:
                rec.id_card_image = False
    
    # Related fields for convenience
    plan_duration_days = fields.Integer(string='Plan Duration (Days)', related='membership_plan_id.duration_days')
    plan_quota_mode = fields.Selection(string='Quota Mode', related='membership_plan_id.quota_mode')
    plan_allowed_regular_offline = fields.Boolean(string='Allows Regular Offline', related='membership_plan_id.allowed_regular_offline')
    plan_allowed_regular_online = fields.Boolean(string='Allows Regular Online', related='membership_plan_id.allowed_regular_online')
    plan_allowed_spclub = fields.Boolean(string='Allows Special Club', related='membership_plan_id.allowed_spclub')
    
    # Computed fields for duration
    total_duration_days = fields.Integer(string='Total Duration (Days)', compute='_compute_total_duration_days', store=True)
    days_until_expiry = fields.Integer(string='Days Until Expiry', compute='_compute_days_until_expiry', store=False)
    days_since_activation = fields.Integer(string='Days Since Activation', compute='_compute_days_since_activation', store=False)
    upgrade_deadline = fields.Date(string='Upgrade Deadline', compute='_compute_upgrade_deadline', store=False)
    hours_until_expiry = fields.Integer(string='Hours Until Expiry', compute='_compute_hours_until_expiry', store=False)
    total_clubs_remaining = fields.Integer(string='Total Clubs Remaining', compute='_compute_total_clubs_remaining', store=False)
    
    # Computed fields for eligibility
    plan_has_upgrade_paths = fields.Boolean(string='Plan Has Upgrade Paths', compute='_compute_plan_has_upgrade_paths', store=False)
    can_renew_discount = fields.Boolean(string='Can Renew with Discount', compute='_compute_can_renew_discount', store=False)
    can_renew = fields.Boolean(string='Can Renew', compute='_compute_can_renew', store=False)
    attendance_policy_freeze_count = fields.Integer(
        string='Attendance Policy Freeze Count',
        default=0,
        help='Number of attendance-policy freezes already applied.'
    )
    attendance_policy_last_penalty_date = fields.Datetime(
        string='Attendance Policy Last Penalty Date',
        copy=False,
        help='Last datetime when attendance policy penalty freeze was applied.'
    )
    @api.depends('membership_plan_id.duration_days', 'extra_days_extension')
    def _compute_total_duration_days(self):
        """Compute total duration including extra days"""
        for membership in self:
            base_duration = membership.membership_plan_id.duration_days or 0
            extra_days = membership.extra_days_extension or 0
            membership.total_duration_days = base_duration + extra_days
    
    def _compute_days_until_expiry(self):
        """Compute days until membership expires"""
        today = fields.Date.today()
        for membership in self:
            if membership.effective_end_date:
                delta = membership.effective_end_date - today
                membership.days_until_expiry = delta.days
            else:
                membership.days_until_expiry = 0

    def _compute_days_since_activation(self):
        """Compute days elapsed since membership activation date"""
        today = fields.Date.today()
        for membership in self:
            if membership.activation_date:
                membership.days_since_activation = (today - membership.activation_date).days
            else:
                membership.days_since_activation = 0

    def _compute_upgrade_deadline(self):
        """Compute the last date the member can use their upgrade discount (activation + upgrade_window_days)"""
        for membership in self:
            if membership.activation_date and membership.membership_plan_id.upgrade_window_days:
                membership.upgrade_deadline = membership.activation_date + timedelta(
                    days=membership.membership_plan_id.upgrade_window_days
                )
            else:
                membership.upgrade_deadline = False

    @api.depends('effective_end_date', 'state')
    def _compute_hours_until_expiry(self):
        """Compute whole hours until membership expires (end of effective_end_date in company timezone), clamped at 0."""
        now_utc = fields.Datetime.now()  # naive UTC
        company_tz_name = (self.env.company.partner_id.tz or 'UTC')
        try:
            company_tz = pytz.timezone(company_tz_name)
        except Exception:
            company_tz = pytz.UTC

        for membership in self:
            if membership.state == 'expired' or not membership.effective_end_date:
                membership.hours_until_expiry = 0.0
                continue

            try:
                expiry_local = company_tz.localize(
                    datetime.combine(membership.effective_end_date, time(23, 59, 59))
                )
                expiry_utc = expiry_local.astimezone(pytz.UTC).replace(tzinfo=None)  # naive UTC
                hours = (expiry_utc - now_utc).total_seconds() / 3600.0
                # Floor to whole hours (and clamp at 0)
                membership.hours_until_expiry = int(max(hours, 0.0))
            except Exception:
                membership.hours_until_expiry = 0
    
    def _compute_total_clubs_remaining(self):
        """Compute total clubs/sessions remaining (for points-based plans, calculate equivalent clubs)"""
        for membership in self:
            if membership.plan_quota_mode == 'bucket_counts':
                # For bucket plans, sum all remaining sessions
                total = (membership.remaining_offline or 0) + (membership.remaining_online or 0) + (membership.remaining_sp or 0)
                membership.total_clubs_remaining = total
            elif membership.plan_quota_mode == 'points':
                # For points plans, divide by 3 to get approximate clubs (assuming avg 3 points per club)
                membership.total_clubs_remaining = (membership.points_remaining or 0) // 3
            else:
                # Unlimited plans
                membership.total_clubs_remaining = -1
    
    def _compute_plan_has_upgrade_paths(self):
        """Compute if the membership's plan has any configured upgrade paths"""
        for membership in self:
            membership.plan_has_upgrade_paths = bool(
                membership.membership_plan_id and membership.membership_plan_id.can_upgrade_to_ids
            )

    def _compute_can_renew_discount(self):
        """Compute if membership is eligible for renewal discount"""
        for membership in self:
            membership.can_renew_discount = membership.is_eligible_for_renewal_discount()

    def _compute_can_renew(self):
        """Compute if membership is eligible to show the renew button (with or without discount)"""
        for membership in self:
            if membership.state not in ['active', 'frozen']:
                membership.can_renew = False
            elif membership.membership_plan_id.quota_mode == 'bucket_counts':
                # Experience cards: renew button always available while active/frozen
                membership.can_renew = True
            else:
                membership.can_renew = membership.is_eligible_for_renewal()
    
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
                
                # Note: Auto-expiration will be handled by cron job for reliability
    
    @api.depends('partner_id', 'membership_plan_id')
    def _compute_display_name(self):
        for membership in self:
            partner_name = membership.partner_id.name if membership.partner_id else 'Unknown'
            plan_name = membership.membership_plan_id.name if membership.membership_plan_id else 'Unknown Plan'
            membership.display_name = f"{partner_name} - {plan_name}"
    
    def _count_used_sessions(self, club_type, past_only=False):
        """Count used sessions of a specific club type using event tags - robust approach"""
        # If this is a new record, return 0
        if not self.id or self.id < 0:
            return 0

        try:
            # Only count registrations that went through proper consumption flow
            # Exclude imported registrations and registrations without proper state
            domain = [
                ('membership_id', '=', self.id),
                ('consumption_state', '=', 'consumed'),
                ('is_imported', '=', False),
                # Count confirmed registrations AND waitlisted registrations that
                # have already had their quota consumed (quota is consumed on
                # waitlist join to prevent stacking unlimited waitlists).
                '|',
                ('state', 'in', ['open', 'confirmed', 'done']),
                '&', ('state', '=', 'draft'), ('is_on_waitlist', '=', True),
            ]
            # Bucket: no-show does not count as consumed unless penalty was applied
            if self.plan_quota_mode == 'bucket_counts':
                domain.append('|')
                domain.append(('is_no_show_attendance', '=', False))
                domain.append(('quota_penalty_applied', '=', True))
            # Upgrade credit only considers events that have already ended
            if past_only:
                domain.append(('event_id.date_end', '<', fields.Datetime.now()))
            registrations = self.env['event.registration'].sudo().search(domain)
            
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
            domain = [
                ('membership_id', '=', self.id),
                ('consumption_state', '=', 'consumed'),
                ('is_imported', '=', False),
                # Count confirmed registrations AND waitlisted registrations that
                # have already had their quota consumed (quota is consumed on
                # waitlist join to prevent stacking unlimited waitlists).
                '|',
                ('state', 'in', ['open', 'confirmed', 'done']),
                '&', ('state', '=', 'draft'), ('is_on_waitlist', '=', True),
            ]
            # Points: no-show does not count as consumed unless penalty was applied
            if self.plan_quota_mode == 'points':
                domain.append('|')
                domain.append(('is_no_show_attendance', '=', False))
                domain.append(('quota_penalty_applied', '=', True))
            registrations = self.env['event.registration'].sudo().search(domain)
            
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
                    elif club_type == 'social_experience':
                        points = plan.points_per_social_experience
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
        price_tier = vals.get('price_tier')
        
        # Check if customer is a first-timer (no prior club attendance AND no prior memberships)
        is_first_timer = self._is_first_timer_customer(partner_id)
        
        # Set upgrade discount allowed based on purchase channel and price tier
        # Only pitch_day purchases with first_timer pricing get upgrade discount by default
        # Online purchases default to FALSE (staff can manually enable)
        if purchase_channel == 'pitch_day' and price_tier == 'first_timer':
            vals['upgrade_discount_allowed'] = True
        else:
            vals['upgrade_discount_allowed'] = False
        
        membership = super().create(vals)

        # Update partner's first timer status after creating membership
        if partner_id:
            self.env['res.partner']._update_first_timer_status(partner_id)

        # PDB (Pitched Didn't Buy) logic: clear PDB flag when partner purchases a membership
        if partner_id:
            partner = self.env['res.partner'].browse(partner_id)
            if partner.pdb:
                partner.pdb = False

        return membership
    
    # Note: Automatic expiration is now handled by cron job for reliability
    
    @api.model
    def _is_first_timer_customer(self, partner_id):
        """Check if customer is a first-timer (delegates to partner model)"""
        return self.env['res.partner']._is_first_timer_customer(partner_id)
    
    def action_activate(self):
        """Activate a pending membership"""
        self.ensure_one()
        if self.state not in ['pending', 'pending_payment', 'pending_student_verification']:
            raise UserError(_('Only pending memberships can be activated'))
        
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
            'freeze_total_days_used': self.freeze_total_days_used + freeze_days,
            'freeze_is_penalty': False,
        })

    def _apply_attendance_policy_freeze(self, freeze_days):
        """Apply or extend freeze for attendance policy."""
        self.ensure_one()
        if freeze_days <= 0:
            return False

        freeze_start = fields.Date.today()
        freeze_end = freeze_start + timedelta(days=freeze_days - 1)

        if self.freeze_active and self.freeze_end:
            # Extend from current freeze end when already frozen.
            freeze_start = self.freeze_start or fields.Date.today()
            freeze_end = self.freeze_end + timedelta(days=freeze_days)

        vals = {
            'freeze_active': True,
            'freeze_start': freeze_start,
            'freeze_end': freeze_end,
            'freeze_is_penalty': True,
        }
        if self.state == 'active':
            vals['state'] = 'frozen'
        self.write(vals)
        return True

    def _evaluate_unlimited_late_no_show_policy(self):
        """
        Unlimited memberships:
        - if 3+ incidents in the current calendar month => freeze 3 days
        - apply at most once per calendar month
        """
        Registration = self.env['event.registration'].sudo()
        for membership in self:
            if membership.plan_quota_mode != 'unlimited':
                continue
            if membership.state not in ['active', 'frozen']:
                continue

            now = fields.Datetime.now()
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            incident_count = Registration.search_count([
                ('membership_id', '=', membership.id),
                ('late_no_show_incident', '=', True),
                ('late_no_show_incident_date', '>=', month_start),
            ])
            if incident_count < 3:
                continue

            if (
                membership.attendance_policy_last_penalty_date
                and membership.attendance_policy_last_penalty_date >= month_start
            ):
                continue

            freeze_days = 3
            membership._apply_attendance_policy_freeze(freeze_days)
            membership.write({
                'attendance_policy_freeze_count': (membership.attendance_policy_freeze_count or 0) + 1,
                'attendance_policy_last_penalty_date': now,
            })
            membership.message_post(
                body=_(
                    'Attendance policy applied: %s incidents detected this month. '
                    'Membership frozen for %s days. (Max once per calendar month)'
                ) % (incident_count, freeze_days)
            )
    
    def action_unfreeze(self):
        """End active freeze period"""
        self.ensure_one()
        if not self.freeze_active:
            raise UserError(_('Membership is not currently frozen'))
        # Portal users cannot end policy penalty freezes.
        if self.freeze_is_penalty and not self.env.user.has_group('base.group_user'):
            raise UserError(_('Penalty freeze cannot be ended from portal.'))
        
        # Just clear the freeze state - freeze_total_days_used already contains the freeze days
        # that were added when the freeze was initiated, so we don't need to add them again
        self.write({
            'freeze_active': False,
            'freeze_start': False,
            'freeze_end': False,
            'freeze_is_penalty': False,
            'state': 'active' if self.state == 'frozen' else self.state,
            # freeze_total_days_used remains unchanged - it already contains the correct total
        })
    
    def action_expire(self):
        """Mark membership as expired"""
        self.ensure_one()
        if self.state not in ['active', 'frozen', 'pending_student_verification']:
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
        """Calculate upgrade price for bucket-based plans (Experience, Online)

        Credit is the remaining value on the card:
        Upgrade price = new membership cost - (unit_value × remaining clubs)
        where remaining clubs = total clubs - past-attended clubs (future bookings
        are not deducted so they retain their full credit value).
        """
        plan = self.membership_plan_id
        if not plan.unit_base_count:
            return target_plan.price_first_timer

        # Count only past-attended sessions (exclude future bookings)
        past_offline = self._count_used_sessions('regular_offline', past_only=True)
        past_online = self._count_used_sessions('regular_online', past_only=True)
        past_sp = self._count_used_sessions('spclub', past_only=True)

        total_past = past_offline + past_online + past_sp
        total_remaining = max(0, plan.unit_base_count - total_past)

        # Calculate unit value
        if plan.unit_value_fixed > 0:
            unit_value = plan.unit_value_fixed
        else:
            unit_value = self.purchase_price_paid / plan.unit_base_count

        # Credit = remaining value on the card
        upgrade_price = target_plan.price_first_timer - (unit_value * total_remaining)
        return max(0, upgrade_price)
    
    def _calculate_points_upgrade_price(self, target_plan):
        """Calculate upgrade price for Freedom plan"""
        plan = self.membership_plan_id
        if not plan.unit_base_count:
            return target_plan.price_first_timer
        
        # Calculate remaining clubs from points
        # 108 points = 36 clubs (3 points per club)
        points_remaining = self.points_remaining
        clubs_left = points_remaining / 3
        
        # Calculate unit value per club
        # Freedom has 108 points = 36 clubs equivalent
        unit_value = self.purchase_price_paid / 36
        
        upgrade_price = target_plan.price_first_timer - (unit_value * clubs_left)
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
    
    def is_eligible_for_renewal(self):
        """Check if membership is eligible to show renewal banner (within reminder window)"""
        self.ensure_one()
        
        # Only active or frozen memberships can renew
        if self.state not in ['active', 'frozen']:
            return False
        
        plan = self.membership_plan_id
        
        # Check if plan allows renewal (early_renew_window_days > 0)
        if plan.early_renew_window_days == 0:
            return False
        
        # Points-based plans (Freedom): Check points remaining
        if plan.quota_mode == 'points':
            # Banner shows when points are within the window (24-15)
            min_threshold = plan.renewal_points_threshold or 15
            max_threshold = plan.renewal_points_max or 24
            return min_threshold <= self.points_remaining <= max_threshold
        
        # Time-based plans (Gold, Experience): Check days until expiry
        else:
            if not self.effective_end_date:
                return False
            
            days_until_expiry = (self.effective_end_date - fields.Date.today()).days
            
            # Experience card: banner shows within configured window from activation (15-30)
            if plan.quota_mode == 'bucket_counts' and plan.renewal_window_end_days > 0:
                if not self.activation_date:
                    return False
                days_since_activation = (fields.Date.today() - self.activation_date).days
                # Banner shows between early_renew_window_days and renewal_window_end_days
                return plan.early_renew_window_days <= days_since_activation <= plan.renewal_window_end_days
            
            # Gold cards: banner shows within the window (45-30 days before expiry)
            else:
                min_days = plan.early_renew_window_days or 30
                max_days = plan.renewal_window_max_days or 45
                return min_days <= days_until_expiry <= max_days
        
        return False
    
    def is_eligible_for_renewal_discount(self):
        """Check if membership is eligible for renewal discount (first-timer price)"""
        self.ensure_one()
        
        # Only active or frozen memberships can renew
        if self.state not in ['active', 'frozen']:
            return False
        
        plan = self.membership_plan_id
        
        # Check if plan allows renewal
        if plan.early_renew_window_days == 0:
            return False
        
        # Experience cards (bucket_counts) do not get renewal discount
        if plan.quota_mode == 'bucket_counts':
            return False

        # Points-based plans (Freedom): Discount available until points drop below threshold
        if plan.quota_mode == 'points':
            # Discount available from purchase → closes at 15 points
            min_threshold = plan.renewal_points_threshold or 15
            return self.points_remaining >= min_threshold

        # Gold cards: discount available until lower bound (30 days before expiry)
        if not self.effective_end_date:
            return False
        days_until_expiry = (self.effective_end_date - fields.Date.today()).days
        min_days = plan.early_renew_window_days or 30
        return days_until_expiry >= min_days
        
        return False
    
    @api.model
    def _cron_expire_memberships(self):
        """Cron job to expire memberships past their effective end date or with zero points"""
        
        # 1. Expire memberships past their effective end date
        expired_memberships = self.search([
            ('state', 'in', ['active', 'frozen']),
            ('effective_end_date', '<', fields.Date.today())
        ])
        
        for membership in expired_memberships:
            membership.action_expire()
        
        # 2. Expire points-based memberships with zero points
        points_memberships = self.search([
            ('state', 'in', ['active', 'frozen']),
            ('membership_plan_id.quota_mode', '=', 'points')
        ])
        
        for membership in points_memberships:
            # Force recomputation of points_remaining
            membership.invalidate_recordset(['points_remaining'])
            membership.flush_recordset(['points_remaining'])
            
            if membership.points_remaining == 0:
                _logger.info(f"Cron: Auto-expiring membership {membership.id} due to zero points")
                membership.action_expire()
                membership.message_post(
                    body=_('Membership automatically expired by cron: All points have been used')
                )
    
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
    
    @api.model
    def _cron_create_expiry_followup_activities(self):
        """Cron job to create follow-up activities for memberships nearing expiration"""
        # Get the follow-up group users
        followup_group = self.env.ref('popcorn.group_membership_followup', raise_if_not_found=False)
        if not followup_group or not followup_group.users:
            # Skip if group doesn't exist or has no users
            return
        
        # Activity type for membership follow-up (use default 'To Do' type)
        activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        if not activity_type:
            activity_type = self.env['mail.activity.type'].search([('name', '=', 'To Do')], limit=1)
        
        today = fields.Date.today()
        
        # Get all active/frozen memberships
        active_memberships = self.search([
            ('state', 'in', ['active', 'frozen']),
            ('effective_end_date', '!=', False)
        ])
        
        # Process each membership based on its plan's follow-up days
        for membership in active_memberships:
            # Get follow-up days from the membership plan (default to '7' if not set)
            followup_days_str = membership.membership_plan_id.expiry_followup_days or '7'
            
            # Parse comma-separated values
            try:
                followup_days_list = [int(day.strip()) for day in followup_days_str.split(',') if day.strip()]
            except (ValueError, AttributeError):
                # If parsing fails, use default of 7 days
                followup_days_list = [7]
            
            # Check each follow-up interval
            for days_before_expiry in followup_days_list:
                # Calculate target date for this interval
                target_date = today + timedelta(days=days_before_expiry)
                
                # Check if this membership expires on the target date
                if membership.effective_end_date != target_date:
                    continue
                
                # Check if activity already exists for this membership at this interval
                existing_activity = self.env['mail.activity'].search([
                    ('res_model', '=', 'popcorn.membership'),
                    ('res_id', '=', membership.id),
                    ('activity_type_id', '=', activity_type.id if activity_type else False),
                    ('summary', 'ilike', f'Membership Expiring in {days_before_expiry} days')
                ], limit=1)
                
                if existing_activity:
                    # Skip if activity already exists for this interval
                    continue
                
                # Create activity for each user in the follow-up group
                for user in followup_group.users:
                    activity_vals = {
                        'activity_type_id': activity_type.id if activity_type else False,
                        'summary': f'Membership Expiring in {days_before_expiry} days: {membership.display_name}',
                        'note': f'''
                            <p>The membership for <strong>{membership.partner_id.name}</strong> is expiring in <strong>{days_before_expiry} days</strong>.</p>
                            <ul>
                                <li><strong>Plan:</strong> {membership.membership_plan_id.name}</li>
                                <li><strong>Expiry Date:</strong> {membership.effective_end_date}</li>
                                <li><strong>Status:</strong> {dict(membership._fields['state'].selection)[membership.state]}</li>
                            </ul>
                            <p>Please contact the member to discuss renewal options.</p>
                        ''',
                        'date_deadline': today,
                        'res_model_id': self.env['ir.model']._get('popcorn.membership').id,
                        'res_id': membership.id,
                        'user_id': user.id,
                    }
                    
                    self.env['mail.activity'].create(activity_vals)
    
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
        
        # Create contract without contract_text field
        contract_vals = {
            'membership_id': self.id,
            'contract_type': 'standard',
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
    
    def apply_discount(self, discount):
        """Apply a discount to this membership"""
        self.ensure_one()
        
        if not discount or not discount._is_currently_valid():
            raise UserError(_('Invalid or expired discount'))
        
        # Check if discount applies to this plan
        if discount.membership_plan_ids and self.membership_plan_id not in discount.membership_plan_ids:
            raise UserError(_('This discount does not apply to the selected membership plan'))
        
        # Check customer type restrictions
        event_type = 'regular_online' if not self.membership_plan_id.allowed_regular_offline else None
        if not discount._customer_matches_types(self.partner_id, event_type=event_type):
            if discount.customer_type == 'multiple' and discount.customer_type_ids:
                type_names = ', '.join(discount.customer_type_ids.mapped('name'))
                raise UserError(_('This discount is only available for: %s') % type_names)
            raise UserError(_('This discount is not available for your customer type'))
        
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
    
    def action_upgrade_to_plan(self, new_plan, actual_payment_amount, payment_transaction_id=None, payment_reference=None, applied_discount=None):
        """Upgrade this membership to a new plan
        
        Args:
            new_plan: popcorn.membership.plan record
            actual_payment_amount: Actual money paid for upgrade (excludes popcorn money)
                This is the remaining_amount from payment transaction, which equals:
                upgrade_price - popcorn_money_to_use
            payment_transaction_id: Optional payment transaction ID
            payment_reference: Optional payment reference
            applied_discount: Optional discount record
        
        Returns:
            self (upgraded membership record, same ID)
        """
        self.ensure_one()
        
        # Store original values
        original_purchase_price = self.purchase_price_paid
        
        # Calculate accumulated purchase price
        # Only add actual money paid (not popcorn money) to purchase_price_paid
        new_purchase_price = original_purchase_price + actual_payment_amount
        
        # Build upgrade values
        upgrade_vals = {
            'membership_plan_id': new_plan.id,
            'purchase_price_paid': new_purchase_price,
            'price_tier': 'first_timer' if self.upgrade_discount_allowed else 'normal',
            'purchase_channel': 'online',
            'upgrade_discount_allowed': self.upgrade_discount_allowed,
        }
        
        # Add payment info if provided
        if payment_transaction_id:
            upgrade_vals['payment_transaction_id'] = payment_transaction_id
        if payment_reference:
            upgrade_vals['payment_reference'] = payment_reference
        if applied_discount:
            upgrade_vals['applied_discount_id'] = applied_discount.id
        
        # Update the existing membership
        self.write(upgrade_vals)
        
        # Invalidate computed fields that depend on membership_plan_id
        self.invalidate_recordset([
            'remaining_offline', 'remaining_online', 'remaining_sp',
            'points_remaining',
            'end_date_base', 'effective_end_date', 'total_duration_days',
            'plan_duration_days', 'plan_quota_mode',
            'plan_allowed_regular_offline', 'plan_allowed_regular_online',
            'plan_allowed_spclub'
        ])
        self.flush_recordset()
        
        return self
    
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
