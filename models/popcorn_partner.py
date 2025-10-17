# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


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
        store=True,
        help='Number of days remaining for first-timer discount'
    )
    
    first_timer_discount_is_expired = fields.Boolean(
        string='Discount Expired',
        compute='_compute_first_timer_discount_remaining_days',
        store=True,
        help='Whether the first-timer discount has expired'
    )
    
    first_timer_discount_is_used = fields.Boolean(
        string='Discount Used',
        compute='_compute_first_timer_discount_status',
        store=True,
        help='Whether the first-timer discount has been used'
    )
    
    first_timer_discount_is_available = fields.Boolean(
        string='Discount Available',
        compute='_compute_first_timer_discount_status',
        store=True,
        help='Whether the first-timer discount is available (not expired and not used)'
    )
    
    # Staff member field
    book_club_automatically = fields.Boolean(
        string='Book Club Automatically',
        default=False,
        help='Indicates if this contact should be automatically registered for all published events.'
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
    
    @api.depends('first_timer_discount_expiry')
    def _compute_first_timer_discount_remaining_days(self):
        """Compute remaining days for first-timer discount"""
        today = fields.Date.today()
        for partner in self:
            if partner.first_timer_discount_expiry:
                remaining_days = (partner.first_timer_discount_expiry - today).days
                partner.first_timer_discount_remaining_days = max(0, remaining_days)
                partner.first_timer_discount_is_expired = remaining_days <= 0
            else:
                partner.first_timer_discount_remaining_days = 0
                partner.first_timer_discount_is_expired = True
    
    @api.depends('first_timer_discount_code')
    def _compute_first_timer_discount_status(self):
        """Compute if first-timer discount has been used and is available"""
        for partner in self:
            if partner.first_timer_discount_code:
                # Check if the discount has been used
                discount_record = self.env['popcorn.discount'].sudo().search([
                    ('code', '=', partner.first_timer_discount_code)
                ], limit=1)
                
                if discount_record:
                    partner.first_timer_discount_is_used = discount_record.usage_count > 0
                    # Available if not expired AND not used
                    partner.first_timer_discount_is_available = (
                        not partner.first_timer_discount_is_expired and 
                        not partner.first_timer_discount_is_used
                    )
                else:
                    partner.first_timer_discount_is_used = False
                    partner.first_timer_discount_is_available = False
            else:
                partner.first_timer_discount_is_used = False
                partner.first_timer_discount_is_available = False
    
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
        """Compute if this partner is a first timer (auto-computation)"""
        if not partner_id:
            return True
            
        try:
            # Check if customer has any prior attended registrations
            prior_registrations = self.env['event.registration'].sudo().search([
                ('partner_id', '=', partner_id),
                ('state', '=', 'done'),  # Attended
            ], limit=1)
            
            # Check if customer has any prior memberships (including expired)
            prior_memberships = self.env['popcorn.membership'].sudo().search([
                ('partner_id', '=', partner_id),
            ], limit=1)
            
            # If no prior registrations AND no prior memberships, they are a first-timer
            return not bool(prior_registrations) and not bool(prior_memberships)
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
                
                # Create the actual discount record (restricted to regular clubs only)
                self.env['popcorn.discount'].sudo().create({
                    'name': f'First Timer Discount - {partner.name}',
                    'code': discount_code,
                    'description': f'First timer discount for {partner.name} - Valid for Regular clubs only',
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
                    'website_description': f'Welcome discount for {partner.name}! Get {discount_amount}RMB off your first regular club registration.'
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
        """Check if customer is a first-timer (never joined a club before AND never had a membership)"""
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
