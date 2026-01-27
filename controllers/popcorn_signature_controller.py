# -*- coding: utf-8 -*-

from odoo import http, fields
from odoo.http import request
import json
import base64
import logging

_logger = logging.getLogger(__name__)

class PopcornContractController(http.Controller):

    @http.route('/popcorn/contract/sign_customer', type='json', auth='user', methods=['POST'])
    def sign_customer_contract(self, contract_id, signature_data):
        """Handle customer signature via RPC"""
        try:
            contract = request.env['popcorn.contract'].browse(contract_id)
            if not contract.exists():
                return {'error': 'Contract not found'}
            
            # Validate contract state
            if contract.state not in ['approved', 'signed']:
                return {'error': 'Contract must be approved before signing'}
            
            # Sign the contract
            contract.action_sign_customer(signature_data)
            
            return {
                'success': True,
                'message': 'Contract signed successfully',
                'contract_state': contract.state
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    @http.route('/popcorn/contract/sign_from_event', type='json', auth='user', methods=['POST'])
    def sign_contract_from_event(self, contract_id, signature_data):
        """Handle customer signature during event registration
        Allows signing draft contracts (created during checkout) that haven't been approved yet.
        """
        try:
            contract = request.env['popcorn.contract'].sudo().browse(contract_id)
            if not contract.exists():
                return {'error': 'Contract not found'}
            
            # Process base64 string - Binary field expects base64-encoded string, not binary data
            if isinstance(signature_data, str):
                # If it's a data URL, extract the base64 part
                if signature_data.startswith('data:image'):
                    signature_data = signature_data.split(',')[1]
                # Keep as base64 string (don't decode - Binary field expects base64 string)
                # Validate it's valid base64 by trying to decode (but don't use the result)
                try:
                    base64.b64decode(signature_data, validate=True)
                except Exception as e:
                    _logger.error(f"Error validating signature data: {str(e)}")
                    return {'error': 'Invalid signature format'}
            else:
                return {'error': 'Signature data must be a base64 string'}
            
            # Sign the contract (allows draft contracts) - pass base64 string directly
            contract.action_sign_customer_from_event(signature_data)
            
            return {
                'success': True,
                'message': 'Contract signed successfully',
                'contract_state': contract.state
            }
            
        except Exception as e:
            _logger.error(f"Error signing contract from event: {str(e)}")
            return {'error': str(e)}