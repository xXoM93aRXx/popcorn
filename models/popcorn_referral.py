from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging
import secrets
import string

_logger = logging.getLogger(__name__)


class PopcornReferral(models.Model):
    _name = 'popcorn.referral'
    _description = 'Event Referral'
    _order = 'create_date desc'
    
    name = fields.Char(
        string='Referral Code',
        required=True,
        default=lambda self: self._generate_referral_code(),
        help='Unique referral code'
    )
    
    event_id = fields.Many2one(
        'event.event',
        string='Event',
        required=True,
        ondelete='cascade',
        help='Event being referred'
    )
    
    referrer_id = fields.Many2one(
        'res.partner',
        string='Referrer',
        required=True,
        help='Person who made the referral'
    )
    
    referee_id = fields.Many2one(
        'res.partner',
        string='Referee',
        help='Person who was referred (friend)'
    )
    
    registration_id = fields.Many2one(
        'event.registration',
        string='Registration',
        help='Registration created through this referral'
    )
    
    referral_prize = fields.Float(
        string='Referral Prize',
        digits='Product Price',
        help='Prize amount for successful referral'
    )
    
    status = fields.Selection([
        ('pending', 'Pending'),
        ('registered', 'Registered'),
        ('attended', 'Attended'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired')
    ], string='Status', default='pending', required=True, help='Referral status')
    
    referral_link = fields.Char(
        string='Referral Link',
        compute='_compute_referral_link',
        store=False,
        help='Full referral link URL'
    )
    
    created_date = fields.Datetime(
        string='Created Date',
        default=fields.Datetime.now,
        required=True
    )
    
    expiry_date = fields.Datetime(
        string='Expiry Date',
        help='Referral link expiry date'
    )
    
    completed_date = fields.Datetime(
        string='Completed Date',
        help='Date when referral was completed and prize awarded'
    )
    
    prize_awarded = fields.Boolean(
        string='Prize Awarded',
        default=False,
        help='Whether the referral prize has been awarded'
    )
    
    @api.model
    def _generate_referral_code(self):
        """Generate a unique referral code"""
        import random
        import string
        
        while True:
            # Generate a 12-character alphanumeric code
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
            
            # Check if code already exists
            if not self.search([('name', '=', code)], limit=1):
                return code
    
    @api.depends('name', 'event_id')
    def _compute_referral_link(self):
        """Compute the full referral link URL"""
        for referral in self:
            if referral.name and referral.event_id:
                base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
                referral.referral_link = f"{base_url}/popcorn/event/{referral.event_id.id}/referral/{referral.name}"
            else:
                referral.referral_link = False
    
    @api.model
    def create_referral(self, event_id, referrer_id, referral_prize):
        """Create a new referral"""
        referral = self.create({
            'event_id': event_id,
            'referrer_id': referrer_id,
            'referral_prize': referral_prize,
            'expiry_date': fields.Datetime.now() + fields.timedelta(days=30)  # 30 days expiry
        })
        return referral
    
    @api.model
    def process_referral_registration(self, referral_code, referee_id, registration_id):
        """Process a registration made through a referral link"""
        # Find the original referral to get the referrer and event info
        original_referral = self.search([('name', '=', referral_code)], limit=1)
        
        if not original_referral:
            raise ValidationError(_('Invalid referral code'))
        
        # Check if the original referral is expired
        if original_referral.expiry_date and fields.Datetime.now() > original_referral.expiry_date:
            raise ValidationError(_('This referral link has expired'))
        
        # Create a NEW referral record for this specific registration
        # This allows the same referral code to be used by multiple people
        from datetime import timedelta
        
        new_referral = self.create({
            'name': f"{referral_code}-{referee_id}-{registration_id}",  # Unique identifier
            'referrer_id': original_referral.referrer_id.id,
            'event_id': original_referral.event_id.id,
            'referral_prize': original_referral.referral_prize,
            'referee_id': referee_id,
            'registration_id': registration_id,
            'status': 'registered',
            'created_date': fields.Datetime.now(),
            'expiry_date': fields.Datetime.now() + timedelta(days=30)  # 30 days from now
        })
        
        # Add referral tracking to registration
        if registration_id:
            registration = self.env['event.registration'].browse(registration_id)
            registration.referral_id = new_referral.id
        
        return new_referral
    
    def mark_as_attended(self):
        """Mark referral as attended when event is completed"""
        for referral in self:
            if referral.status == 'registered' and referral.registration_id:
                # Check if registration is confirmed and not cancelled
                if referral.registration_id.state in ['open', 'done']:
                    referral.write({
                        'status': 'attended'
                    })
    
    def complete_referral(self):
        """Complete the referral and award the prize"""
        for referral in self:
            if referral.status == 'attended' and not referral.prize_awarded:
                # Award the prize to referrer's popcorn money
                if referral.referrer_id and referral.referral_prize > 0:
                    # Use the proper method to add popcorn money
                    referral.referrer_id.add_popcorn_money(
                        referral.referral_prize,
                        f'Referral prize for event: {referral.event_id.name} (Referee: {referral.referee_id.name})'
                    )
                    
                    # Log the prize award
                    referral.referrer_id.message_post(
                        body=_('Referral prize of %s awarded for successful referral to event: %s') % (
                            f"{referral.event_id.currency_id.symbol}{referral.referral_prize:,.2f}",
                            referral.event_id.name
                        )
                    )
                
                referral.write({
                    'status': 'completed',
                    'completed_date': fields.Datetime.now(),
                    'prize_awarded': True
                })
    
    def cancel_referral(self):
        """Cancel the referral"""
        for referral in self:
            referral.status = 'cancelled'
    
    @api.model
    def cleanup_expired_referrals(self):
        """Cleanup expired referrals"""
        expired_referrals = self.search([
            ('status', '=', 'pending'),
            ('expiry_date', '<', fields.Datetime.now())
        ])
        
        if expired_referrals:
            expired_referrals.write({'status': 'expired'})
            _logger.info(f'Marked {len(expired_referrals)} referrals as expired')
        
        return len(expired_referrals)
    
    @api.model
    def auto_complete_attended_referrals(self):
        """Automatically complete referrals for events that have ended"""
        # Find referrals where the event has ended but referral is still marked as attended
        ended_events = self.env['event.event'].search([
            ('date_end', '<', fields.Datetime.now()),
            ('stage_id.name', '=', 'Ended')
        ])
        
        if ended_events:
            attended_referrals = self.search([
                ('event_id', 'in', ended_events.ids),
                ('status', '=', 'attended'),
                ('prize_awarded', '=', False)
            ])
            
            for referral in attended_referrals:
                referral.complete_referral()
            
            if attended_referrals:
                _logger.info(f'Completed {len(attended_referrals)} referrals for ended events')
        
        return len(attended_referrals) if 'attended_referrals' in locals() else 0
