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
