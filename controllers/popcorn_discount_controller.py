# -*- coding: utf-8 -*-

import json
from odoo import http, _
from odoo.http import request


class PopcornDiscountController(http.Controller):
    """Controller for managing coupon/discount code validation and application."""

    @http.route('/popcorn/discount/validate', type='http', auth='user', methods=['POST'], website=True, csrf=True)
    def validate_discount_code(self, **post):
        """Validate a discount code and return discount details as JSON.

        The form sends:
            - code: The discount code to validate
            - plan_id: Optional membership plan ID for membership discounts
            - event_id: Optional event ID for event discounts
            - partner_id: Optional partner ID (defaults to current user's partner)
        """
        code = post.get('code')
        plan_id = post.get('plan_id')
        event_id = post.get('event_id')
        partner_id = post.get('partner_id')
        
        if not code:
            result = {
                'success': False,
                'message': _('Please enter a discount code')
            }
            return request.make_response(
                json.dumps(result),
                headers=[('Content-Type', 'application/json')]
            )

        # Get the partner
        if partner_id:
            partner = request.env['res.partner'].browse(int(partner_id))
        else:
            partner = request.env.user.partner_id

        if not partner.exists():
            result = {
                'success': False,
                'message': _('Partner not found')
            }
            return request.make_response(
                json.dumps(result),
                headers=[('Content-Type', 'application/json')]
            )

        # Search for the discount by code
        discount = request.env['popcorn.discount'].search([
            ('code', '=', code),
            ('active', '=', True)
        ], limit=1)

        if not discount:
            result = {
                'success': False,
                'message': _('Invalid discount code')
            }
            return request.make_response(
                json.dumps(result),
                headers=[('Content-Type', 'application/json')]
            )

        # Check if discount is currently valid
        if not discount._is_currently_valid():
            result = {
                'success': False,
                'message': _('This discount code has expired or reached its usage limit')
            }
            return request.make_response(
                json.dumps(result),
                headers=[('Content-Type', 'application/json')]
            )

        # Check if discount is restricted to a specific partner
        if discount.partner_id and discount.partner_id.id != partner.id:
            result = {
                'success': False,
                'message': _('This discount code is not valid for your account')
            }
            return request.make_response(
                json.dumps(result),
                headers=[('Content-Type', 'application/json')]
            )

        # Check usage limit per customer
        if discount.usage_limit_per_customer > 0:
            usage_count = request.env['popcorn.membership'].search_count([
                ('partner_id', '=', partner.id),
                ('applied_discount_id', '=', discount.id)
            ])

            if usage_count >= discount.usage_limit_per_customer:
                result = {
                    'success': False,
                    'message': _('You have already used this discount code the maximum number of times')
                }
                return request.make_response(
                    json.dumps(result),
                    headers=[('Content-Type', 'application/json')]
                )

        # Validate for membership plan
        if plan_id:
            # First-timer discounts (with partner_id) are ONLY for events, not memberships
            if discount.partner_id:
                result = {
                    'success': False,
                    'message': _('This discount code is only valid for event registrations, not memberships')
                }
                return request.make_response(
                    json.dumps(result),
                    headers=[('Content-Type', 'application/json')]
                )

            plan = request.env['popcorn.membership.plan'].browse(int(plan_id))
            if not plan.exists():
                result = {
                    'success': False,
                    'message': _('Invalid membership plan')
                }
                return request.make_response(
                    json.dumps(result),
                    headers=[('Content-Type', 'application/json')]
                )

            # Check if discount applies to this plan
            if discount.membership_plan_ids and plan not in discount.membership_plan_ids:
                result = {
                    'success': False,
                    'message': _('This discount code is not valid for the selected membership plan')
                }
                return request.make_response(
                    json.dumps(result),
                    headers=[('Content-Type', 'application/json')]
                )

            # Check customer type restrictions
            plan_event_type = 'regular_online' if not plan.allowed_regular_offline else None
            if not discount._customer_matches_types(partner, event_type=plan_event_type):
                if discount.customer_type == 'multiple' and discount.customer_type_ids:
                    type_names = ', '.join(discount.customer_type_ids.mapped('name'))
                    msg = _('This discount is only available for: %s') % type_names
                else:
                    msg = _('This discount is not available for your customer type')
                result = {'success': False, 'message': msg}
                return request.make_response(
                    json.dumps(result),
                    headers=[('Content-Type', 'application/json')]
                )

            # Calculate discounted price
            original_price = plan.price_normal
            if partner.is_first_timer and plan.price_first_timer > 0:
                original_price = plan.price_first_timer

            discounted_price = discount.get_discounted_price(plan, original_price, partner)
            extra_days = discount.get_extra_days(plan, partner)
            discount_amount = original_price - discounted_price

            result = {
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
            return request.make_response(
                json.dumps(result),
                headers=[('Content-Type', 'application/json')]
            )

        # Validate for event
        elif event_id:
            event = request.env['event.event'].browse(int(event_id))
            if not event.exists():
                result = {
                    'success': False,
                    'message': _('Invalid event')
                }
                return request.make_response(
                    json.dumps(result),
                    headers=[('Content-Type', 'application/json')]
                )

            # Check event type restriction
            if discount.event_type:
                if event.club_type != discount.event_type:
                    event_type_name = dict(event._fields['club_type'].selection).get(event.club_type, 'this event type')
                    result = {
                        'success': False,
                        'message': _('This discount is only valid for %s clubs, not %s') % (
                            dict(discount._fields['event_type'].selection).get(discount.event_type, ''),
                            event_type_name
                        )
                    }
                    return request.make_response(
                        json.dumps(result),
                        headers=[('Content-Type', 'application/json')]
                    )

            # Check customer type restrictions
            if not discount._customer_matches_types(partner, event_type=event.club_type):
                if discount.customer_type == 'multiple' and discount.customer_type_ids:
                    type_names = ', '.join(discount.customer_type_ids.mapped('name'))
                    msg = _('This discount is only available for: %s') % type_names
                else:
                    msg = _('This discount is not available for your customer type')
                result = {'success': False, 'message': msg}
                return request.make_response(
                    json.dumps(result),
                    headers=[('Content-Type', 'application/json')]
                )

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

            result = {
                'success': True,
                'message': _('Discount code applied successfully!'),
                'discount': {
                    'id': discount.id,
                    'name': discount.name,
                    'code': discount.code,
                    'discount_type': discount.discount_type,
                    'discount_value': discount.discount_value,
                    'is_first_timer_coupon': bool(discount.partner_id),
                },
                'pricing': {
                    'original_price': original_price,
                    'discounted_price': discounted_price,
                    'discount_amount': discount_amount,
                    'currency_symbol': event.currency_id.symbol,
                }
            }
            return request.make_response(
                json.dumps(result),
                headers=[('Content-Type', 'application/json')]
            )

        result = {
            'success': False,
            'message': _('Please specify either a membership plan or event')
        }
        return request.make_response(
            json.dumps(result),
            headers=[('Content-Type', 'application/json')]
        )

    @http.route('/popcorn/discount/remove', type='http', auth='user', methods=['POST'], website=True, csrf=True)
    def remove_discount_code(self, **post):
        """Remove applied discount code from session."""
        # Clear discount from session
        if 'applied_discount_id' in request.session:
            del request.session['applied_discount_id']
        if 'applied_discount_code' in request.session:
            del request.session['applied_discount_code']

        result = {
            'success': True,
            'message': _('Discount code removed')
        }
        return request.make_response(
            json.dumps(result),
            headers=[('Content-Type', 'application/json')]
        )
