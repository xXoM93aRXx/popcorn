# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

class PopcornContract(models.Model):
    """Membership contracts for storing contract text and terms"""
    _name = 'popcorn.contract'
    _description = 'Popcorn Membership Contract'
    _order = 'create_date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'display_name'

    # Core fields
    membership_id = fields.Many2one('popcorn.membership', string='Membership', required=True, ondelete='cascade')
    contract_type = fields.Selection([
        ('standard', 'Standard Contract'),
        ('custom', 'Custom Contract'),
        ('upgrade', 'Upgrade Contract'),
        ('renewal', 'Renewal Contract')
    ], string='Contract Type', default='standard', required=True)
    
    # Contract details
    contract_date = fields.Date(string='Contract Date', default=fields.Date.today, required=True)
    effective_date = fields.Date(string='Effective Date', default=fields.Date.today, required=True)
    expiry_date = fields.Date(string='Contract Expiry Date', related='membership_id.effective_end_date', store=True)
    
    # Status and approval
    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending_approval', 'Pending Approval'),
        ('approved', 'Approved'),
        ('signed', 'Signed'),
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', required=True, tracking=True)
    
    # Signatures and approval
    signed_by_customer = fields.Boolean(string='Signed by Customer', default=False, tracking=True)
    signed_by_staff = fields.Boolean(string='Signed by Staff', default=False, tracking=True)
    customer_signature_date = fields.Datetime(string='Customer Signature Date')
    staff_signature_date = fields.Datetime(string='Staff Signature Date')
    customer_signature = fields.Binary(string='Customer Signature', attachment=True, help='Digital signature from customer')
    approved_by = fields.Many2one('res.users', string='Approved By', readonly=True)
    approval_date = fields.Datetime(string='Approval Date', readonly=True)
    
    # Related fields for convenience
    partner_id = fields.Many2one('res.partner', string='Member', related='membership_id.partner_id', store=True)
    membership_plan_id = fields.Many2one('popcorn.membership.plan', string='Membership Plan', related='membership_id.membership_plan_id', store=True)
    membership_state = fields.Selection(string='Membership Status', related='membership_id.state', store=True)
    
    # Display name
    display_name = fields.Char(string='Display Name', compute='_compute_display_name', store=True)
    
    @api.depends('partner_id', 'contract_type', 'contract_date')
    def _compute_display_name(self):
        for contract in self:
            partner_name = contract.partner_id.name if contract.partner_id else 'Unknown'
            contract_type = dict(contract._fields['contract_type'].selection)[contract.contract_type]
            contract_date = contract.contract_date.strftime('%Y-%m-%d') if contract.contract_date else 'Unknown Date'
            contract.display_name = f"{partner_name} - {contract_type} ({contract_date})"
    
    @api.constrains('membership_id')
    def _check_unique_membership_contract(self):
        """Ensure one contract per membership"""
        for contract in self:
            if contract.membership_id:
                existing_contract = self.search([
                    ('membership_id', '=', contract.membership_id.id),
                    ('id', '!=', contract.id)
                ])
                if existing_contract:
                    raise ValidationError(_('A contract already exists for this membership. Only one contract per membership is allowed.'))
    
    @api.constrains('contract_date', 'effective_date')
    def _check_contract_dates(self):
        """Validate contract dates"""
        for contract in self:
            if contract.contract_date and contract.effective_date:
                if contract.effective_date < contract.contract_date:
                    raise ValidationError(_('Effective date cannot be before contract date.'))
    
    def action_approve(self):
        """Approve the contract"""
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_('Only draft contracts can be approved'))
        
        self.write({
            'state': 'approved',
            'approved_by': self.env.user.id,
            'approval_date': fields.Datetime.now()
        })
        
        # Log the approval
        self.message_post(
            body=_('Contract approved by %s') % self.env.user.name
        )
    
    def action_sign_customer(self, signature_data=None):
        """Mark contract as signed by customer"""
        self.ensure_one()
        if self.state not in ['approved', 'signed']:
            raise UserError(_('Contract must be approved before customer can sign'))
        
        vals = {
            'signed_by_customer': True,
            'customer_signature_date': fields.Datetime.now(),
            'state': 'signed' if not self.signed_by_staff else 'active'
        }
        
        if signature_data:
            vals['customer_signature'] = signature_data
        
        self.write(vals)
        
        # Log the customer signature
        self.message_post(
            body=_('Contract signed by customer')
        )
    
    @api.model
    def sign_customer_contract(self, contract_id, signature_data):
        """Sign contract with customer signature data"""
        contract = self.browse(contract_id)
        if not contract.exists():
            raise UserError(_('Contract not found'))
        
        contract.action_sign_customer(signature_data)
        return True
    
    def action_sign_staff(self):
        """Mark contract as signed by staff"""
        self.ensure_one()
        if self.state not in ['approved', 'signed']:
            raise UserError(_('Contract must be approved before staff can sign'))
        
        self.write({
            'signed_by_staff': True,
            'staff_signature_date': fields.Datetime.now(),
            'state': 'signed' if not self.signed_by_customer else 'active'
        })
        
        # Log the staff signature
        self.message_post(
            body=_('Contract signed by staff (%s)') % self.env.user.name
        )
    
    def action_activate(self):
        """Activate the contract"""
        self.ensure_one()
        if self.state != 'signed':
            raise UserError(_('Contract must be signed by both parties before activation'))
        
        self.write({'state': 'active'})
        
        # Log the activation
        self.message_post(
            body=_('Contract activated')
        )
    
    def action_cancel(self):
        """Cancel the contract"""
        self.ensure_one()
        if self.state in ['expired', 'cancelled']:
            raise UserError(_('Contract is already expired or cancelled'))
        
        self.write({'state': 'cancelled'})
        
        # Log the cancellation
        self.message_post(
            body=_('Contract cancelled')
        )
    
    def action_expire(self):
        """Mark contract as expired"""
        self.ensure_one()
        if self.state in ['expired', 'cancelled']:
            raise UserError(_('Contract is already expired or cancelled'))
        
        self.write({'state': 'expired'})
        
        # Log the expiration
        self.message_post(
            body=_('Contract expired')
        )
    
    def action_open_signature_dialog(self):
        """Open signature dialog for customer signing"""
        self.ensure_one()
        if self.state not in ['approved', 'signed']:
            raise UserError(_('Contract must be approved before signing'))
        
        if self.signed_by_customer:
            raise UserError(_('Contract is already signed by customer'))
        
        return {
            'type': 'ir.actions.client',
            'tag': 'popcorn_signature_dialog',
            'target': 'new',
            'context': {
                'contract_id': self.id,
            }
        }
    
    @api.model
    def _cron_expire_contracts(self):
        """Cron job to expire contracts past their expiry date"""
        expired_contracts = self.search([
            ('state', '=', 'active'),
            ('expiry_date', '<', fields.Date.today())
        ])
        
        for contract in expired_contracts:
            contract.action_expire()
    
    def get_contract_summary(self):
        """Get a summary of the contract for display purposes"""
        self.ensure_one()
        return {
            'contract_id': self.id,
            'member_name': self.partner_id.name if self.partner_id else 'Unknown',
            'membership_plan': self.membership_plan_id.name if self.membership_plan_id else 'Unknown',
            'contract_type': dict(self._fields['contract_type'].selection)[self.contract_type],
            'contract_date': self.contract_date.strftime('%Y-%m-%d') if self.contract_date else 'Unknown',
            'effective_date': self.effective_date.strftime('%Y-%m-%d') if self.effective_date else 'Unknown',
            'expiry_date': self.expiry_date.strftime('%Y-%m-%d') if self.expiry_date else 'Unknown',
            'status': dict(self._fields['state'].selection)[self.state],
            'signed_by_customer': self.signed_by_customer,
            'signed_by_staff': self.signed_by_staff,
        }
    
