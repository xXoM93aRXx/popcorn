# -*- coding: utf-8 -*-

from odoo import http, fields
from odoo.http import request
import json

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