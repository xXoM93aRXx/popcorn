# -*- coding: utf-8 -*-

from odoo import http, fields
from odoo.http import request


class PopcornMoneyController(http.Controller):
    """Controller for managing Popcorn money operations"""
    
    @http.route('/popcorn/money/add', type='json', auth='user', methods=['POST'])
    def add_popcorn_money(self, partner_id, amount, notes=''):
        """Add Popcorn money to a partner's account"""
        try:
            partner = request.env['res.partner'].browse(partner_id)
            if not partner.exists():
                return {'success': False, 'message': 'Partner not found'}
            
            if amount <= 0:
                return {'success': False, 'message': 'Amount must be greater than 0'}
            
            success = partner.add_popcorn_money(amount, notes)
            if success:
                return {
                    'success': True, 
                    'message': f'Successfully added {amount} Popcorn money to {partner.name}',
                    'new_balance': partner.popcorn_money_balance
                }
            else:
                return {'success': False, 'message': 'Failed to add Popcorn money'}
                
        except Exception as e:
            return {'success': False, 'message': f'Error: {str(e)}'}
    
    @http.route('/popcorn/money/deduct', type='json', auth='user', methods=['POST'])
    def deduct_popcorn_money(self, partner_id, amount, notes=''):
        """Deduct Popcorn money from a partner's account"""
        try:
            partner = request.env['res.partner'].browse(partner_id)
            if not partner.exists():
                return {'success': False, 'message': 'Partner not found'}
            
            if amount <= 0:
                return {'success': False, 'message': 'Amount must be greater than 0'}
            
            if partner.popcorn_money_balance < amount:
                return {
                    'success': False, 
                    'message': f'Insufficient balance. Current balance: {partner.popcorn_money_balance}'
                }
            
            success = partner.deduct_popcorn_money(amount, notes)
            if success:
                return {
                    'success': True, 
                    'message': f'Successfully deducted {amount} Popcorn money from {partner.name}',
                    'new_balance': partner.popcorn_money_balance
                }
            else:
                return {'success': False, 'message': 'Failed to deduct Popcorn money'}
                
        except Exception as e:
            return {'success': False, 'message': f'Error: {str(e)}'}
    
    @http.route('/popcorn/money/set', type='json', auth='user', methods=['POST'])
    def set_popcorn_money(self, partner_id, amount, notes=''):
        """Set Popcorn money balance to a specific amount"""
        try:
            partner = request.env['res.partner'].browse(partner_id)
            if not partner.exists():
                return {'success': False, 'message': 'Partner not found'}
            
            if amount < 0:
                return {'success': False, 'message': 'Amount cannot be negative'}
            
            success = partner.set_popcorn_money(amount, notes)
            if success:
                return {
                    'success': True, 
                    'message': f'Successfully set Popcorn money balance to {amount} for {partner.name}',
                    'new_balance': partner.popcorn_money_balance
                }
            else:
                return {'success': False, 'message': 'Failed to set Popcorn money balance'}
                
        except Exception as e:
            return {'success': False, 'message': f'Error: {str(e)}'}
    
    @http.route('/popcorn/money/balance/<int:partner_id>', type='json', auth='user')
    def get_popcorn_money_balance(self, partner_id):
        """Get current Popcorn money balance for a partner"""
        try:
            partner = request.env['res.partner'].browse(partner_id)
            if not partner.exists():
                return {'success': False, 'message': 'Partner not found'}
            
            return {
                'success': True,
                'balance': partner.popcorn_money_balance,
                'last_updated': partner.popcorn_money_last_updated.strftime('%Y-%m-%d %H:%M:%S') if partner.popcorn_money_last_updated else None
            }
                
        except Exception as e:
            return {'success': False, 'message': f'Error: {str(e)}'}
