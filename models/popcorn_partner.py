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
    
    popcorn_money_notes = fields.Text(
        string='Money Notes',
        help='Notes about Popcorn money transactions or adjustments'
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
        
        # Ensure popcorn_money_notes is a string
        current_notes = str(self.popcorn_money_notes) if self.popcorn_money_notes else ""
        
        self.with_context(skip_popcorn_money_logging=True).write({
            'popcorn_money_balance': new_balance,
            'popcorn_money_last_updated': fields.Datetime.now(),
            'popcorn_money_notes': current_notes + f"\n{fields.Datetime.now().strftime('%Y-%m-%d %H:%M')}: Added {amount} Popcorn money. {notes}" if notes else current_notes + f"\n{fields.Datetime.now().strftime('%Y-%m-%d %H:%M')}: Added {amount} Popcorn money."
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
        
        # Ensure popcorn_money_notes is a string
        current_notes = str(self.popcorn_money_notes) if self.popcorn_money_notes else ""
        
        self.with_context(skip_popcorn_money_logging=True).write({
            'popcorn_money_balance': new_balance,
            'popcorn_money_last_updated': fields.Datetime.now(),
            'popcorn_money_notes': current_notes + f"\n{fields.Datetime.now().strftime('%Y-%m-%d %H:%M')}: Deducted {amount} Popcorn money. {notes}" if notes else current_notes + f"\n{fields.Datetime.now().strftime('%Y-%m-%d %H:%M')}: Deducted {amount} Popcorn money."
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
        
        # Ensure popcorn_money_notes is a string
        current_notes = str(self.popcorn_money_notes) if self.popcorn_money_notes else ""
        
        self.with_context(skip_popcorn_money_logging=True).write({
            'popcorn_money_balance': new_balance,
            'popcorn_money_last_updated': fields.Datetime.now(),
            'popcorn_money_notes': current_notes + f"\n{fields.Datetime.now().strftime('%Y-%m-%d %H:%M')}: Set balance to {amount} Popcorn money. {notes}" if notes else current_notes + f"\n{fields.Datetime.now().strftime('%Y-%m-%d %H:%M')}: Set balance to {amount} Popcorn money."
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
    
    def write(self, vals):
        """Override write to detect Popcorn money balance changes"""
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
        
        return result
