# -*- coding: utf-8 -*-

from odoo import http, _
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)


class PopcornDiscountController(http.Controller):
    """Controller for managing coupon/discount code validation and application"""
    
    @http.route('/popcorn/discount/validate', type='json', auth='user', methods=['POST'])
    def validate_discount_code(self, code, plan_id=None, event_id=None, partner_id=None):
        """
        Validate a discount code and return discount details
        
        Args:
            code: The discount code to validate
            plan_id: Optional membership plan ID for membership discounts
            event_id: Optional event ID for event discounts
            partner_id: Optional partner ID (defaults to current user's partner)
        
        Returns:
            dict: Success status, discount details, and calculated prices
        """
        try:
            _logger.info(f"Discount validation request - code: {code}, plan_id: {plan_id}, event_id: {event_id}")
            
            if not code:
                return {
                    'success': False,
                    'message': _('Please enter a discount code')
                }
            
            # Get the partner
            if partner_id:
                partner = request.env['res.partner'].browse(partner_id)
            else:
                partner = request.env.user.partner_id
            
            if not partner.exists():
                return {
                    'success': False,
                    'message': _('Partner not found')
                }
            
            # Search for the discount by code
            discount = request.env['popcorn.discount'].search([
                ('code', '=', code),
                ('active', '=', True)
            ], limit=1)
            
            if not discount:
                return {
                    'success': False,
                    'message': _('Invalid discount code')
                }
            
            # Check if discount is currently valid
            if not discount.is_valid:
                return {
                    'success': False,
                    'message': _('This discount code has expired or reached its usage limit')
                }
            
            # Check usage limit per customer
            if discount.usage_limit_per_customer > 0:
                # Count how many times this customer has used this discount
                usage_count = request.env['popcorn.membership'].search_count([
                    ('partner_id', '=', partner.id),
                    ('applied_discount_id', '=', discount.id)
                ])
                
                if usage_count >= discount.usage_limit_per_customer:
                    return {
                        'success': False,
                        'message': _('You have already used this discount code the maximum number of times')
                    }
            
            # Validate for membership plan
            if plan_id:
                plan = request.env['popcorn.membership.plan'].browse(int(plan_id))
                if not plan.exists():
                    return {
                        'success': False,
                        'message': _('Invalid membership plan')
                    }
                
                # Check if discount applies to this plan
                if discount.membership_plan_ids and plan not in discount.membership_plan_ids:
                    return {
                        'success': False,
                        'message': _('This discount code is not valid for the selected membership plan')
                    }
                
                # Check customer type restrictions
                if discount.customer_type != 'all':
                    is_first_timer = partner.is_first_timer
                    if discount.customer_type == 'first_timer' and not is_first_timer:
                        return {
                            'success': False,
                            'message': _('This discount is only available for first-time customers')
                        }
                    elif discount.customer_type == 'existing' and is_first_timer:
                        return {
                            'success': False,
                            'message': _('This discount is only available for existing customers')
                        }
                    elif discount.customer_type == 'new' and is_first_timer:
                        return {
                            'success': False,
                            'message': _('This discount is only available for new customers')
                        }
                
                # Calculate discounted price
                original_price = plan.price_normal
                if partner.is_first_timer and plan.price_first_timer > 0:
                    original_price = plan.price_first_timer
                
                discounted_price = discount.get_discounted_price(plan, original_price, partner)
                extra_days = discount.get_extra_days(plan, partner)
                
                discount_amount = original_price - discounted_price
                
                return {
                    'success': True,
                    'message': _('Discount code applied successfully!'),
                    'discount': {
                        'id': discount.id,
                        'name': discount.name,
                        'code': discount.code,
                        'discount_type': discount.discount_type,
                        'discount_value': discount.discount_value,
                        'extra_days': extra_days,
                    },
                    'pricing': {
                        'original_price': original_price,
                        'discounted_price': discounted_price,
                        'discount_amount': discount_amount,
                        'currency_symbol': plan.currency_id.symbol,
                    }
                }
            
            # Validate for event
            elif event_id:
                event = request.env['event.event'].browse(int(event_id))
                if not event.exists():
                    return {
                        'success': False,
                        'message': _('Invalid event')
                    }
                
                # Check event type restriction
                if discount.event_type:
                    if event.club_type != discount.event_type:
                        event_type_name = dict(event._fields['club_type'].selection).get(event.club_type, 'this event type')
                        return {
                            'success': False,
                            'message': _('This discount is only valid for %s clubs, not %s') % (
                                dict(discount._fields['event_type'].selection).get(discount.event_type, ''),
                                event_type_name
                            )
                        }
                
                # Check customer type restrictions
                if discount.customer_type != 'all':
                    is_first_timer = partner.is_first_timer
                    if discount.customer_type == 'first_timer' and not is_first_timer:
                        return {
                            'success': False,
                            'message': _('This discount is only available for first-time customers')
                        }
                    elif discount.customer_type == 'existing' and is_first_timer:
                        return {
                            'success': False,
                            'message': _('This discount is only available for existing customers')
                        }
                    elif discount.customer_type == 'new' and is_first_timer:
                        return {
                            'success': False,
                            'message': _('This discount is only available for new customers')
                        }
                
                # Calculate discounted price for event
                original_price = event.event_price or 0
                
                # Apply discount calculation
                if discount.discount_type == 'percentage':
                    discount_amount = original_price * (discount.discount_value / 100)
                    discounted_price = max(0, original_price - discount_amount)
                elif discount.discount_type == 'fixed_amount':
                    discount_amount = min(discount.discount_value, original_price)
                    discounted_price = max(0, original_price - discount.discount_value)
                else:
                    discount_amount = 0
                    discounted_price = original_price
                
                return {
                    'success': True,
                    'message': _('Discount code applied successfully!'),
                    'discount': {
                        'id': discount.id,
                        'name': discount.name,
                        'code': discount.code,
                        'discount_type': discount.discount_type,
                        'discount_value': discount.discount_value,
                    },
                    'pricing': {
                        'original_price': original_price,
                        'discounted_price': discounted_price,
                        'discount_amount': discount_amount,
                        'currency_symbol': event.currency_id.symbol,
                    }
                }
            
            return {
                'success': False,
                'message': _('Please specify either a membership plan or event')
            }
            
        except Exception as e:
            _logger.error(f"Error validating discount code: {str(e)}")
            return {
                'success': False,
                'message': _('Error validating discount code: %s') % str(e)
            }
    
    @http.route('/popcorn/discount/remove', type='json', auth='user', methods=['POST'])
    def remove_discount_code(self):
        """Remove applied discount code from session"""
        try:
            # Clear discount from session
            if 'applied_discount_id' in request.session:
                del request.session['applied_discount_id']
            if 'applied_discount_code' in request.session:
                del request.session['applied_discount_code']
            
            return {
                'success': True,
                'message': _('Discount code removed')
            }
            
        except Exception as e:
            _logger.error(f"Error removing discount code: {str(e)}")
            return {
                'success': False,
                'message': _('Error removing discount code: %s') % str(e)
            }

