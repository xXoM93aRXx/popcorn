# -*- coding: utf-8 -*-

import base64
import json
import logging
from odoo import http, fields, _
from odoo.http import request
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)

class PopcornContractController(http.Controller):

    @http.route('/popcorn/contract/<int:contract_id>', type='http', auth='public', website=True)
    def view_contract(self, contract_id=None, **kwargs):
        """Display contract for viewing and signing"""
        if not contract_id:
            return request.not_found()
        
        contract = request.env['popcorn.contract'].sudo().browse(contract_id)
        if not contract.exists():
            return request.not_found()
        
        # Check if user has access to this contract
        if not self._check_contract_access(contract):
            return request.redirect('/web/login')
        
        values = {
            'contract': contract,
            'page_name': 'contract_view',
        }
        
        return request.render('popcorn.contract_view_template', values)
    
    @http.route('/popcorn/contract/<int:contract_id>/sign', type='http', auth='public', methods=['POST'], website=True, csrf=False)
    def sign_contract(self, contract_id=None, **kwargs):
        """Handle contract signing"""
        if not contract_id:
            return request.not_found()
        
        contract = request.env['popcorn.contract'].sudo().browse(contract_id)
        if not contract.exists():
            return request.not_found()
        
        # Check if user has access to this contract
        if not self._check_contract_access(contract):
            return request.redirect('/web/login')
        
        # Check if contract is in signable state
        if contract.state not in ['approved', 'signed']:
            return request.render('popcorn.contract_error_template', {
                'error_message': _('Contract is not in a signable state.')
            })
        
        # Get signature data from request
        signature_data = kwargs.get('signature_data')
        if signature_data:
            # Decode base64 signature data
            try:
                signature_data = base64.b64decode(signature_data.split(',')[1])
            except:
                signature_data = None
        
        # Sign the contract
        try:
            contract.action_sign_customer(signature_data)
            
            # Redirect to success page
            return request.redirect(f'/popcorn/contract/{contract_id}/signed')
        except Exception as e:
            _logger.error(f"Error signing contract {contract_id}: {str(e)}")
            return request.render('popcorn.contract_error_template', {
                'error_message': _('An error occurred while signing the contract.')
            })
    
    @http.route('/popcorn/contract/<int:contract_id>/signed', type='http', auth='public', website=True)
    def contract_signed(self, contract_id=None, **kwargs):
        """Display contract signed confirmation"""
        if not contract_id:
            return request.not_found()
        
        contract = request.env['popcorn.contract'].sudo().browse(contract_id)
        if not contract.exists():
            return request.not_found()
        
        values = {
            'contract': contract,
            'page_name': 'contract_signed',
        }
        
        return request.render('popcorn.contract_signed_template', values)
    
    @http.route('/popcorn/contract/<int:contract_id>/pdf', type='http', auth='public', website=True)
    def download_contract_pdf(self, contract_id=None, **kwargs):
        """Download contract as PDF"""
        if not contract_id:
            return request.not_found()
        
        contract = request.env['popcorn.contract'].sudo().browse(contract_id)
        if not contract.exists():
            return request.not_found()
        
        # Check if user has access to this contract
        if not self._check_contract_access(contract):
            return request.redirect('/web/login')
        
        try:
            # Generate PDF report
            report = request.env.ref('popcorn.action_report_popcorn_contract')
            
            # Debug: Log contract data
            _logger.info(f"Generating PDF for contract ID: {contract.id}")
            _logger.info(f"Contract name: {contract.name}")
            _logger.info(f"Partner: {contract.partner_id.name if contract.partner_id else 'No partner'}")
            _logger.info(f"Membership: {contract.membership_id.name if contract.membership_id else 'No membership'}")
            _logger.info(f"Contract IDs being passed: {contract.ids}")
            
            pdf_data = report._render_qweb_pdf(contract.ids)[0]
            
            pdf_http_headers = [
                ('Content-Type', 'application/pdf'),
                ('Content-Disposition', f'attachment; filename="Service_Contract_{contract.display_name}.pdf"'),
                ('Content-Length', len(pdf_data)),
            ]
            
            return request.make_response(pdf_data, headers=pdf_http_headers)
        except Exception as e:
            _logger.error(f"Error generating PDF for contract {contract_id}: {str(e)}")
            return request.render('popcorn.contract_error_template', {
                'error_message': _('An error occurred while generating the PDF.')
            })
    
    @http.route('/popcorn/contract/create/<int:membership_id>', type='http', auth='user', website=True)
    def create_contract(self, membership_id=None, **kwargs):
        """Create contract for a membership"""
        if not membership_id:
            return request.not_found()
        
        membership = request.env['popcorn.membership'].sudo().browse(membership_id)
        if not membership.exists():
            return request.not_found()
        
        # Check if contract already exists
        if membership.contract_id:
            return request.redirect(f'/popcorn/contract/{membership.contract_id.id}')
        
        try:
            # Create contract
            contract = membership.action_create_contract()
            return request.redirect(f'/popcorn/contract/{contract["res_id"]}')
        except Exception as e:
            _logger.error(f"Error creating contract for membership {membership_id}: {str(e)}")
            return request.render('popcorn.contract_error_template', {
                'error_message': _('An error occurred while creating the contract.')
            })
    
    def _check_contract_access(self, contract):
        """Check if current user has access to the contract"""
        # Check if user is logged in
        if not request.env.user._is_public():
            # Logged in user - check if they are the contract member or staff
            return (contract.partner_id.user_ids and request.env.user in contract.partner_id.user_ids) or \
                   request.env.user.has_group('base.group_system')
        
        # Public user - check if they have access token or are the contract member
        # This could be extended with token-based access for public users
        return False
    
    @http.route('/popcorn/contract/validate-signature', type='json', auth='public', website=True, csrf=False)
    def validate_signature(self, signature_data=None, **kwargs):
        """Validate signature data"""
        if not signature_data:
            return {'valid': False, 'message': _('No signature data provided')}
        
        try:
            # Basic validation - check if it's valid base64
            if signature_data.startswith('data:image'):
                # Extract base64 part
                base64_data = signature_data.split(',')[1]
                base64.b64decode(base64_data)
                return {'valid': True, 'message': _('Signature is valid')}
            else:
                return {'valid': False, 'message': _('Invalid signature format')}
        except Exception as e:
            return {'valid': False, 'message': _('Invalid signature data')}
