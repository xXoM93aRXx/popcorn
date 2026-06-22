# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

import pytz
import logging
from datetime import datetime, time, timedelta
from collections import defaultdict

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    """Extends res.partner with Popcorn Club specific fields"""
    _inherit = 'res.partner'
    
    is_host = fields.Boolean(
        string='Is Host',
        default=False,
        help='Indicates if this contact is a host for events'
    )
    
    host_bio = fields.Text(
        string='Host Bio',
        help='Biography or description of the host for events'
    )
    
    excerpt = fields.Text(
        string='Excerpt',
        help='Short sentence or excerpt to display in host listings'
    )
    
    online_status = fields.Selection([
        ('online', 'Online'),
        ('offline', 'Offline')
    ], string='Online Status', default='online',
       help='Current online/offline status of the host')

    host_poster_image = fields.Binary(
        string='Host Poster Image',
        help='Specific image for host poster display (separate from regular poster image)'
    )

    host_poster_image_filename = fields.Char(
        string='Host Poster Image Filename',
        help='Filename of the host poster image'
    )

    diversity_badge_image = fields.Binary(
        string='Diversity Badge Image',
        attachment=True,
        help='Image shown on the Diversity Badge character select screen (silhouetted until the member attends this host)'
    )

    diversity_badge_image_filename = fields.Char(
        string='Diversity Badge Image Filename',
    )

    diversity_badge_locked_image = fields.Binary(
        string='Diversity Badge Locked Image',
        attachment=True,
        help='Image shown on the Diversity Badge character select screen when the host has not yet been attended'
    )

    diversity_badge_locked_image_filename = fields.Char(
        string='Diversity Badge Locked Image Filename',
    )
    
    banner_image = fields.Binary(
        string='Banner Image',
        help='Banner image for host profile display'
    )
    
    banner_image_filename = fields.Char(
        string='Banner Image Filename',
        help='Filename of the banner image'
    )
    
    baidu_map_link = fields.Char(
        string='Baidu Map Link',
        help='Baidu Maps web link for this location'
    )
    
    amap_link = fields.Char(
        string='Amap Link',
        help='Amap web link for this location'
    )
    
    
    # Computed field to show events hosted by this partner
    hosted_events_count = fields.Integer(
        string='Hosted Events Count',
        compute='_compute_hosted_events_count',
        store=False,
        help='Number of events hosted by this partner'
    )
    
    # First timer logic fields
    is_first_timer = fields.Boolean(
        string='Is First Timer',
        default=True,
        help='Indicates if this contact is a first timer. Can be manually toggled.'
    )
    
    # First timer discount fields
    first_timer_discount_code = fields.Char(
        string='First Timer Discount Code',
        help='Automatically generated discount code for first-timer customers'
    )
    
    first_timer_discount_expiry = fields.Date(
        string='First Timer Discount Expiry',
        help='Date when the first-timer discount code expires (21 days from first-timer status)'
    )
    
    first_timer_discount_remaining_days = fields.Integer(
        string='Remaining Discount Days',
        compute='_compute_first_timer_discount_remaining_days',
        store=False,
        help='Number of days remaining for first-timer discount'
    )

    first_timer_discount_remaining_hours = fields.Integer(
        string='Remaining Discount Hours',
        compute='_compute_first_timer_discount_remaining_days',
        store=False,
        help='Number of whole hours remaining for first-timer discount (company timezone, end-of-day)'
    )
    
    first_timer_discount_is_expired = fields.Boolean(
        string='Discount Expired',
        compute='_compute_first_timer_discount_remaining_days',
        store=False,
        help='Whether the first-timer discount has expired'
    )
    
    first_timer_discount_is_used = fields.Boolean(
        string='Discount Used',
        compute='_compute_first_timer_discount_status',
        store=True,
        help='Whether the first-timer discount has been used'
    )

    has_expired_membership = fields.Boolean(
        string='Has Expired Membership',
        compute='_compute_has_expired_membership',
        store=False,
        help='True if this partner has expired membership(s) and NO active, frozen, or pending memberships (Old Customer)'
    )
    
    pdb = fields.Boolean(
        string='PDB',
        default=False,
        help='Pitched Didn\'t Buy'
    )

    pdb_date = fields.Date(
        string='PDB Date',
        help='Date when partner was first marked as PDB (Pitched Didn\'t Buy)'
    )

    pdb_pending_date = fields.Date(
        string='PDB Pending Date',
        help='Date of first offline club attendance. Partner remains a first-timer until midnight of this date, then PDB is applied.'
    )

    is_pdb_today = fields.Boolean(
        string='Is PDB Today',
        compute='_compute_is_pdb_today',
        store=False,
        help='True if this partner was marked as PDB today — used to show same-day popup notification'
    )

    # Staff member field
    book_club_automatically = fields.Boolean(
        string='Book Club Automatically',
        default=False,
        help='Indicates if this contact should be automatically registered for all published events.'
    )
    
    # Badge tracking: count of distinct hosts attended
    distinct_hosts_count = fields.Integer(
        string='Distinct Hosts Count',
        compute='_compute_distinct_hosts_count',
        store=True,
        help='Number of different hosts this partner has attended events with'
    )
    
    # Badge tracking: count of distinct hosts attended within a time period
    distinct_hosts_count_in_period = fields.Integer(
        string='Distinct Hosts Count (Period)',
        compute='_compute_distinct_hosts_count_in_period',
        store=False,
        help='Number of different hosts this partner has attended events with within a specific time period (for badges)'
    )
    
    # Popcorn Money fields
    popcorn_money_balance = fields.Float(
        string='Popcorn Money Balance',
        default=0.0,
        digits=(16, 2),
        help='Current Popcorn money balance for this partner'
    )
    
    popcorn_money_last_updated = fields.Datetime(
        string='Last Money Update',
        help='When the Popcorn money balance was last updated'
    )
    
    # Personal Information fields
    mbti = fields.Selection([
        ('INTJ', 'INTJ - Architect'),
        ('INTP', 'INTP - Thinker'),
        ('ENTJ', 'ENTJ - Commander'),
        ('ENTP', 'ENTP - Debater'),
        ('INFJ', 'INFJ - Advocate'),
        ('INFP', 'INFP - Mediator'),
        ('ENFJ', 'ENFJ - Protagonist'),
        ('ENFP', 'ENFP - Campaigner'),
        ('ISTJ', 'ISTJ - Logistician'),
        ('ISFJ', 'ISFJ - Defender'),
        ('ESTJ', 'ESTJ - Executive'),
        ('ESFJ', 'ESFJ - Consul'),
        ('ISTP', 'ISTP - Virtuoso'),
        ('ISFP', 'ISFP - Adventurer'),
        ('ESTP', 'ESTP - Entrepreneur'),
        ('ESFP', 'ESFP - Entertainer'),
    ], string='MBTI', help='Myers-Briggs Type Indicator personality type')
    
    gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
        ('prefer_not_to_say', 'Prefer Not to Say'),
    ], string='Gender', help='Gender identity')
    
    zodiac = fields.Selection([
        ('aries', 'Aries'),
        ('taurus', 'Taurus'),
        ('gemini', 'Gemini'),
        ('cancer', 'Cancer'),
        ('leo', 'Leo'),
        ('virgo', 'Virgo'),
        ('libra', 'Libra'),
        ('scorpio', 'Scorpio'),
        ('sagittarius', 'Sagittarius'),
        ('capricorn', 'Capricorn'),
        ('aquarius', 'Aquarius'),
        ('pisces', 'Pisces'),
    ], string='Zodiac Sign', help='Zodiac sign')
    
    preferred_topics = fields.Many2many(
        'event.tag',
        string='Preferred Topics',
        help='Preferred event topics/tags this partner is interested in',
        domain="[('category_id.name', 'ilike', 'Topic')]"
    )
    
    activities_sports = fields.Many2many(
        'popcorn.activity_sport',
        string='Activities & Sports',
        help='Activities and sports this partner is interested in'
    )
    
    @api.depends('is_host')
    def _compute_hosted_events_count(self):
        """Compute the number of events hosted by this partner"""
        for partner in self:
            if partner.is_host:
                try:
                    # Count events where this partner is the host
                    count = self.env['event.event'].sudo().search_count([
                        ('host_id', '=', partner.id)
                    ])
                    partner.hosted_events_count = count
                except:
                    partner.hosted_events_count = 0
            else:
                partner.hosted_events_count = 0
    
    def _compute_distinct_hosts_count(self):
        """Compute the number of distinct hosts this partner has attended"""
        for partner in self:
            try:
                # Get all registrations for this partner where state is 'done' (attended)
                attended_registrations = self.env['event.registration'].sudo().search([
                    ('partner_id', '=', partner.id),
                    ('state', '=', 'done')
                ])
                
                # Get all unique host IDs from these registrations
                unique_host_ids = attended_registrations.mapped('event_id.host_id').filtered('id')
                unique_host_ids_list = list(set(unique_host_ids.mapped('id')))
                
                partner.distinct_hosts_count = len(unique_host_ids_list)
            except Exception as e:
                # Log error but don't fail
                import logging
                _logger = logging.getLogger(__name__)
                _logger.warning(f"Error computing distinct_hosts_count for partner {partner.id}: {e}")
                partner.distinct_hosts_count = 0
    
    def get_attended_host_ids(self, from_date=None):
        """Return a set of host partner IDs this partner has a non-cancelled registration for.

        Only events whose end time has already passed are counted.
        If from_date is provided, only registrations created on or after that date are counted.
        """
        self.ensure_one()
        domain = [
            ('partner_id', '=', self.id),
            ('state', '!=', 'cancel'),
            ('is_no_show_attendance', '=', False),
            ('event_id.date_end', '<=', fields.Datetime.now()),
        ]
        if from_date:
            domain.append(('create_date', '>=', from_date))
        attended_registrations = self.env['event.registration'].sudo().search(domain)
        host_partners = attended_registrations.mapped('event_id.host_id').filtered('id')
        return set(host_partners.mapped('id'))

    def get_attended_topic_ids(self, from_date=None):
        """Return a set of Topic tag IDs this partner has attended events for.

        Only events whose end time has already passed are counted.
        If from_date is provided, only registrations created on or after that date are counted.
        """
        self.ensure_one()
        domain = [
            ('partner_id', '=', self.id),
            ('state', '!=', 'cancel'),
            ('is_no_show_attendance', '=', False),
            ('event_id.date_end', '<=', fields.Datetime.now()),
        ]
        if from_date:
            domain.append(('create_date', '>=', from_date))
        attended_registrations = self.env['event.registration'].sudo().search(domain)
        topic_tag_ids = set()
        for reg in attended_registrations:
            for tag in reg.event_id.tag_ids:
                if tag.category_id.name == 'Topics':
                    topic_tag_ids.add(tag.id)
        return topic_tag_ids

    @api.model
    def recompute_distinct_hosts_count(self, partner_ids=None):
        """Manually recompute distinct hosts count for specified partners or all partners"""
        if partner_ids:
            partners = self.browse(partner_ids)
        else:
            partners = self.search([])
        
        partners._compute_distinct_hosts_count()
        return True
    
    @api.depends('first_timer_discount_expiry')
    def _compute_first_timer_discount_remaining_days(self):
        """Compute remaining days for first-timer discount"""
        today = fields.Date.today()
        now_utc = fields.Datetime.now()  # naive UTC
        company_tz_name = (self.env.company.partner_id.tz or 'UTC')
        try:
            company_tz = pytz.timezone(company_tz_name)
        except Exception:
            company_tz = pytz.UTC

        for partner in self:
            if partner.first_timer_discount_expiry:
                remaining_days = (partner.first_timer_discount_expiry - today).days
                partner.first_timer_discount_remaining_days = max(0, remaining_days)
                partner.first_timer_discount_is_expired = remaining_days <= 0
                try:
                    expiry_local = company_tz.localize(
                        datetime.combine(partner.first_timer_discount_expiry, time(23, 59, 59))
                    )
                    expiry_utc = expiry_local.astimezone(pytz.UTC).replace(tzinfo=None)  # naive UTC
                    hours = (expiry_utc - now_utc).total_seconds() / 3600.0
                    partner.first_timer_discount_remaining_hours = int(max(hours, 0.0))
                except Exception:
                    partner.first_timer_discount_remaining_hours = 0
            else:
                partner.first_timer_discount_remaining_days = 0
                partner.first_timer_discount_is_expired = True
                partner.first_timer_discount_remaining_hours = 0
    
    def _compute_has_expired_membership(self):
        """Compute if partner is an Old Customer: has expired membership(s) and NO active/frozen/pending memberships"""
        for partner in self:
            has_expired = bool(
                self.env['popcorn.membership'].search([
                    ('partner_id', '=', partner.id),
                    ('state', '=', 'expired')
                ], limit=1)
            )
            has_active = bool(
                self.env['popcorn.membership'].search([
                    ('partner_id', '=', partner.id),
                    ('state', 'in', ['active', 'frozen', 'pending', 'pending_payment', 'pending_buy_together'])
                ], limit=1)
            )
            partner.has_expired_membership = has_expired and not has_active

    def _compute_first_timer_discount_status(self):
        """Compute if first-timer discount has been used"""
        for partner in self:
            if partner.first_timer_discount_code:
                # Check if the discount has been used
                discount_record = self.env['popcorn.discount'].sudo().search([
                    ('code', '=', partner.first_timer_discount_code)
                ], limit=1)
                
                if discount_record:
                    partner.first_timer_discount_is_used = discount_record.usage_count > 0
                else:
                    partner.first_timer_discount_is_used = False
            else:
                partner.first_timer_discount_is_used = False

    @api.depends('pdb', 'pdb_date')
    def _compute_is_pdb_today(self):
        today = fields.Date.today()
        for partner in self:
            partner.is_pdb_today = partner.pdb and partner.pdb_date == today

    @api.model
    def _cron_apply_pending_pdb(self):
        """Hourly cron: convert grace-period partners to PDB after midnight."""
        today = fields.Date.today()
        pending = self.search([
            ('pdb_pending_date', '<', today),
            ('pdb', '=', False),
            ('pdb_pending_date', '!=', False),
        ])
        for partner in pending:
            partner.pdb = True

    def _get_first_timer_discount_record(self):
        """Get the live discount record linked to this partner's first-timer code."""
        self.ensure_one()
        if not self.first_timer_discount_code:
            return self.env['popcorn.discount']

        return self.env['popcorn.discount'].sudo().search([
            ('code', '=', self.first_timer_discount_code),
            ('partner_id', '=', self.id),
        ], limit=1)

    def has_valid_first_timer_coupon(self, club_type=None):
        """Return True if the partner currently has a usable first-timer coupon."""
        self.ensure_one()
        if not self.is_first_timer or not self.first_timer_discount_code:
            return False

        discount = self._get_first_timer_discount_record()
        if not discount:
            return False
        if club_type and discount.event_type and discount.event_type != club_type:
            return False

        return discount._is_currently_valid()
    
    def action_refresh_discount_expiry(self):
        """Manually refresh the discount expiry status"""
        self._compute_first_timer_discount_remaining_days()
        self._compute_first_timer_discount_status()
        return True
    
    @api.model
    def action_refresh_all_discount_status(self):
        """Refresh discount status for all partners with discount codes"""
        partners = self.search([('first_timer_discount_code', '!=', False)])
        for partner in partners:
            partner._compute_first_timer_discount_remaining_days()
            partner._compute_first_timer_discount_status()
        return True
    
    @api.model
    def _compute_is_first_timer_auto(self, partner_id):
        """Compute if this partner is a first timer (auto-computation)
        
        Note: is_first_timer status is ONLY for membership pricing eligibility.
        Using first-timer coupon for club registrations does NOT affect this status.
        Only memberships (existing or expired) determine first-timer status.
        """
        if not partner_id:
            return True
            
        try:
            # Check if customer has any prior memberships (including expired)
            # This determines first-timer pricing eligibility for memberships
            prior_memberships = self.env['popcorn.membership'].sudo().search([
                ('partner_id', '=', partner_id),
            ], limit=1)
            
            # First-timer status is ONLY based on prior memberships
            # Club registrations (even attended) do NOT affect this status
            return not bool(prior_memberships)
        except Exception:
            # If access denied or error, assume not first-timer for safety
            return False
    
    def action_auto_compute_first_timer(self):
        """Manually trigger auto-computation of first timer status"""
        for partner in self:
            partner.is_first_timer = self._compute_is_first_timer_auto(partner.id)
    
    def action_generate_first_timer_discount(self):
        """Generate a first-timer discount code and set expiry date"""
        for partner in self:
            if partner.is_first_timer and not partner.first_timer_discount_code:
                # Generate unique discount code
                import random
                import string
                
                # Create code like "FIRST123" or "NEW456"
                prefix = random.choice(['FIRST', 'NEW', 'WELCOME'])
                suffix = ''.join(random.choices(string.digits, k=3))
                discount_code = f"{prefix}{suffix}"
                
                # Ensure code is unique
                while self.env['popcorn.discount'].sudo().search([('code', '=', discount_code)]):
                    suffix = ''.join(random.choices(string.digits, k=3))
                    discount_code = f"{prefix}{suffix}"
                
                # Set expiry date to 21 days from now
                from datetime import timedelta
                expiry_date = fields.Date.today() + timedelta(days=21)
                
                partner.write({
                    'first_timer_discount_code': discount_code,
                    'first_timer_discount_expiry': expiry_date
                })
                
                # Get the first-timer discount amount from system parameter
                discount_amount = float(self.env['ir.config_parameter'].sudo().get_param(
                    'popcorn.first_timer_discount_amount', '118.00'
                ))
                
                # Create the actual discount record (restricted to regular offline clubs only)
                self.env['popcorn.discount'].sudo().create({
                    'name': f'First Timer Discount - {partner.name}',
                    'code': discount_code,
                    'description': f'First timer discount for {partner.name} - Valid for Regular Offline clubs only',
                    'active': True,
                    'discount_type': 'fixed_amount',
                    'discount_value': discount_amount,
                    'date_from': fields.Date.today(),
                    'date_to': expiry_date,
                    'usage_limit': 1,  # Can only be used once
                    'usage_limit_per_customer': 1,
                    'customer_type': 'first_timer',
                    'partner_id': partner.id,  # Restrict to this specific partner
                    'event_type': 'regular_offline',  # Only valid for regular offline clubs
                    'is_public': True,
                    'website_description': f'Welcome discount for {partner.name}! Get {discount_amount}RMB off your first regular offline club registration.'
                })
                
                # Post message
                partner.message_post(
                    body=f"🎉 First-timer discount code generated: {discount_code}. Expires on {expiry_date.strftime('%Y-%m-%d')}",
                    message_type='notification'
                )
    
    @api.model
    def _update_first_timer_status(self, partner_id):
        """Update first timer status for a partner (called from other models)"""
        if not partner_id:
            return
            
        partner = self.browse(partner_id)
        if partner.exists():
            partner.is_first_timer = self._compute_is_first_timer_auto(partner_id)
    
    @api.model
    def _is_first_timer_customer(self, partner_id):
        """Check if customer is a first-timer for membership pricing
        
        Note: Club registrations (even attended) do NOT affect first-timer status.
        Only memberships determine first-timer pricing eligibility.
        """
        if not partner_id:
            return False
            
        try:
            partner = self.browse(partner_id)
            if partner.exists():
                return partner.is_first_timer
            else:
                return False
        except Exception:
            # If access denied or error, assume not first-timer for safety
            return False
    
    def add_popcorn_money(self, amount, notes=''):
        """Add Popcorn money to this partner's balance"""
        if amount <= 0:
            return False
        
        old_balance = self.popcorn_money_balance
        new_balance = old_balance + amount
        
        self.with_context(skip_popcorn_money_logging=True).write({
            'popcorn_money_balance': new_balance,
            'popcorn_money_last_updated': fields.Datetime.now()
        })
        
        # Post message in chatter
        message = f"💰 Added {amount} Popcorn money. Balance: {old_balance} → {new_balance}"
        if notes:
            message += f"\nNote: {notes}"
        
        self.message_post(
            body=message,
            message_type='notification',
            subtype_xmlid='mail.mt_note'
        )
        
        return True
    
    def deduct_popcorn_money(self, amount, notes=''):
        """Deduct Popcorn money from this partner's balance"""
        if amount <= 0 or self.popcorn_money_balance < amount:
            return False
        
        old_balance = self.popcorn_money_balance
        new_balance = old_balance - amount
        
        self.with_context(skip_popcorn_money_logging=True).write({
            'popcorn_money_balance': new_balance,
            'popcorn_money_last_updated': fields.Datetime.now()
        })
        
        # Post message in chatter
        message = f"💸 Deducted {amount} Popcorn money. Balance: {old_balance} → {new_balance}"
        if notes:
            message += f"\nNote: {notes}"
        
        self.message_post(
            body=message,
            message_type='notification',
            subtype_xmlid='mail.mt_note'
        )
        
        return True
    
    def set_popcorn_money(self, amount, notes=''):
        """Set Popcorn money balance to a specific amount"""
        if amount < 0:
            return False
        
        old_balance = self.popcorn_money_balance
        new_balance = amount
        
        self.with_context(skip_popcorn_money_logging=True).write({
            'popcorn_money_balance': new_balance,
            'popcorn_money_last_updated': fields.Datetime.now()
        })
        
        # Post message in chatter
        message = f"⚖️ Set Popcorn money balance. Balance: {old_balance} → {new_balance}"
        if notes:
            message += f"\nNote: {notes}"
        
        self.message_post(
            body=message,
            message_type='notification',
            subtype_xmlid='mail.mt_note'
        )
        
        return True
    
    @api.model
    def create(self, vals):
        """Override create to auto-generate first-timer discount for new customers"""
        result = super(ResPartner, self).create(vals)
        
        # Auto-generate discount code for new first-timer customers
        if result.is_first_timer and not result.first_timer_discount_code:
            result.action_generate_first_timer_discount()
        
        return result
    
    def write(self, vals):
        """Override write to detect Popcorn money balance changes and auto-generate first-timer discounts"""
        # When PDB is switched on, clear First Timer and stamp today's date
        if vals.get('pdb'):
            vals['is_first_timer'] = False
            vals['pdb_date'] = fields.Date.today()

        # Check if popcorn_money_balance is being changed
        if 'popcorn_money_balance' in vals:
            for record in self:
                old_balance = record.popcorn_money_balance
                new_balance = vals['popcorn_money_balance']
                
                # Only log if balance actually changed and it's not from our methods
                if old_balance != new_balance and not self.env.context.get('skip_popcorn_money_logging'):
                    # Post message in chatter after the write
                    if new_balance > old_balance:
                        message = f"💰 Popcorn money balance increased. Balance: {old_balance} → {new_balance}"
                    elif new_balance < old_balance:
                        message = f"💸 Popcorn money balance decreased. Balance: {old_balance} → {new_balance}"
                    else:
                        message = f"⚖️ Popcorn money balance changed. Balance: {old_balance} → {new_balance}"
                    
                    # Use a post-write hook to avoid recursion
                    self.env.context = self.env.context.copy()
                    self.env.context['popcorn_money_message'] = message
                    self.env.context['popcorn_money_partner_id'] = record.id
        
        # Check if is_first_timer is being set to True and auto-generate discount
        if 'is_first_timer' in vals and vals['is_first_timer']:
            for record in self:
                # Only generate if they don't already have a discount code
                if not record.first_timer_discount_code:
                    self.env.context = self.env.context.copy()
                    self.env.context['auto_generate_discount'] = record.id
        
        result = super(ResPartner, self).write(vals)
        
        # Post the message after the write is complete
        if self.env.context.get('popcorn_money_message'):
            partner_id = self.env.context.get('popcorn_money_partner_id')
            if partner_id:
                partner = self.browse(partner_id)
                partner.message_post(
                    body=self.env.context['popcorn_money_message'],
                    message_type='notification',
                    subtype_xmlid='mail.mt_note'
                )
        
        # Auto-generate discount code after the write is complete
        if self.env.context.get('auto_generate_discount'):
            partner_id = self.env.context.get('auto_generate_discount')
            if partner_id:
                partner = self.browse(partner_id)
                partner.action_generate_first_timer_discount()

        return result

    # -------------------------------------------------------------------------
    # Punctuality Badge — daily cron evaluation
    # -------------------------------------------------------------------------

    # Set to False once logs confirm the logic is correct
    _PUNCTUALITY_DRY_RUN = True

    @api.model
    def _cron_evaluate_punctuality_badge(self):
        """Daily cron: award Punctuality Badge to members who have had
        zero attendance incidents and at least 5 clean attendances per
        complete calendar month over the last 90 days.

        While _PUNCTUALITY_DRY_RUN is True, only logs — no badges awarded.
        """
        DRY_RUN = self._PUNCTUALITY_DRY_RUN
        prefix = '[PUNCTUALITY_BADGE DRY RUN]' if DRY_RUN else '[PUNCTUALITY_BADGE]'

        badge = self.env.ref('popcorn.badge_punctuality_90d', raise_if_not_found=False)
        if not badge:
            _logger.warning('%s Badge record not found — skipping', prefix)
            return

        today = fields.Date.today()
        window_start = today - timedelta(days=90)
        window_start_dt = datetime.combine(window_start, time.min)

        # Only evaluate partners who don't already have the badge
        already_earned_ids = self.env['res.partner'].sudo().search([
            ('permanently_earned_badge_ids', 'in', [badge.id]),
        ]).ids

        candidates = self.env['res.partner'].sudo().search([
            ('id', 'not in', already_earned_ids),
            ('user_ids', '!=', False),   # actual portal/internal users only
        ])

        _logger.info('%s Evaluating %s candidates (badge: %s)', prefix, len(candidates), badge.name)

        Registration = self.env['event.registration'].sudo()

        for partner in candidates:
            # ── Rule 1: zero attendance incidents in the 90-day window ──────
            # Covers all membership types: late_no_show_incident (unlimited)
            # and quota_penalty_violation (bucket/points)
            incident_count = Registration.search_count([
                ('partner_id', '=', partner.id),
                '|',
                '&', ('late_no_show_incident', '=', True),
                     ('late_no_show_incident_date', '>=', window_start_dt),
                '&', ('quota_penalty_violation', '=', True),
                     ('quota_penalty_violation_date', '>=', window_start_dt),
            ])

            if incident_count > 0:
                _logger.info('%s partner=%s (%s) FAILS: %s incident(s) in last 90 days',
                             prefix, partner.id, partner.name, incident_count)
                continue

            # ── Rule 2: ≥5 clean attendances in every complete calendar month ─
            clean_regs = Registration.search([
                ('partner_id', '=', partner.id),
                ('state', 'not in', ['cancel', 'draft']),
                ('late_no_show_incident', '=', False),
                ('is_no_show_attendance', '=', False),
                ('event_id.date_begin', '>=', window_start_dt),
            ])

            # Group by event month
            monthly = defaultdict(int)
            for reg in clean_regs:
                if reg.event_id.date_begin:
                    monthly[(reg.event_id.date_begin.year, reg.event_id.date_begin.month)] += 1

            # Only check complete calendar months (exclude current month in progress)
            complete_months = []
            cursor = window_start.replace(day=1)
            while cursor < today.replace(day=1):
                complete_months.append((cursor.year, cursor.month))
                if cursor.month == 12:
                    cursor = cursor.replace(year=cursor.year + 1, month=1)
                else:
                    cursor = cursor.replace(month=cursor.month + 1)

            if not complete_months:
                _logger.info('%s partner=%s (%s) FAILS: no complete months in 90-day window yet',
                             prefix, partner.id, partner.name)
                continue

            failed_months = [m for m in complete_months if monthly.get(m, 0) < 5]
            monthly_summary = ', '.join(
                '%d/%d=%d' % (m[1], m[0], monthly.get(m, 0)) for m in complete_months
            )

            if failed_months:
                _logger.info('%s partner=%s (%s) FAILS: months below 5 clean attendances: %s | full: %s',
                             prefix, partner.id, partner.name,
                             [('%d/%d' % (m[1], m[0])) for m in failed_months],
                             monthly_summary)
                continue

            # ── Qualifies ────────────────────────────────────────────────────
            _logger.info('%s partner=%s (%s) QUALIFIES: 0 incidents | %s',
                         prefix, partner.id, partner.name, monthly_summary)

            if not DRY_RUN:
                partner.write({
                    'permanently_earned_badge_ids': [(4, badge.id)],
                    'notified_badge_ids': [(4, badge.id)],
                })
                if badge.prize_popcorn_money > 0:
                    expiry_date = None
                    if badge.prize_expiry_days > 0:
                        expiry_date = today + timedelta(days=badge.prize_expiry_days)
                    partner.add_popcorn_money(
                        badge.prize_popcorn_money,
                        notes='Badge earned: %s' % badge.name,
                    )
                    self.env['popcorn.badge.prize'].sudo().create({
                        'partner_id': partner.id,
                        'badge_id': badge.id,
                        'amount': badge.prize_popcorn_money,
                        'expiry_date': expiry_date,
                    })
                    _logger.info('%s partner=%s (%s) AWARDED badge + %s popcorn money',
                                 prefix, partner.id, partner.name, badge.prize_popcorn_money)

        _logger.info('%s Evaluation complete', prefix)
