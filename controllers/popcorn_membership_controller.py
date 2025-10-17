# -*- coding: utf-8 -*-

from odoo import http, _
from odoo.http import request
import json
import logging
from odoo import fields

_logger = logging.getLogger(__name__)

class PopcornMembershipController(http.Controller):
    """Controller for standalone membership purchase"""
    
    @http.route(['/memberships'], type='http', auth="public", website=True)
    def memberships_list(self, **post):
        """Display all available membership plans"""
        # Check if user is logged in (public user means not logged in)
        if request.env.user.id == request.env.ref('base.public_user').id:
            return request.redirect('/web/login?redirect=' + request.httprequest.url)
        
        # Get all active membership plans
        membership_plans = request.env['popcorn.membership.plan'].search([
            ('active', '=', True)
        ], order='sequence, name')
        
        # Get error message from URL parameter if present
        error_message = request.params.get('error', '')
        
        if error_message:
            # URL decode the error message
            import urllib.parse
            error_message = urllib.parse.unquote(error_message)
        
        # Also check for session-based error message
        if not error_message and 'error_message' in request.session:
            error_message = request.session['error_message']
            # Clear the session error message to prevent it from showing again
            del request.session['error_message']
        
        
        # Check if user is a first-timer
        is_first_timer = request.env.user.partner_id.is_first_timer
        
        # Get discount information for each plan
        plan_discounts = {}
        for plan in membership_plans:
            available_discounts = plan.get_available_discounts(request.env.user.partner_id)
            best_price, best_discount, extra_days = plan.get_best_discount_with_extra_days(request.env.user.partner_id)
            
            plan_discounts[plan.id] = {
                'available_discounts': available_discounts,
                'best_price': best_price,
                'best_discount': best_discount,
                'original_price': plan.price_normal,
                'first_timer_price': plan.price_first_timer,
                'extra_days': extra_days,
            }
        
        values = {
            'membership_plans': membership_plans,
            'error_message': error_message,
            'is_first_timer': is_first_timer,
            'plan_discounts': plan_discounts,
        }
        
        return request.render('popcorn.membership_plans_website_page', values)
    
    @http.route(['/memberships/website'], type='http', auth="public", website=True)
    def memberships_website_page(self, **post):
        """Display membership plans as a website page (editable by website editor)"""
        # Check if user is logged in (public user means not logged in)
        if request.env.user.id == request.env.ref('base.public_user').id:
            return request.redirect('/web/login?redirect=' + request.httprequest.url)
        
        return request.render('popcorn.membership_plans_website_page')
    
    @http.route(['/memberships/<model("popcorn.membership.plan"):plan>'], type='http', auth="public", website=True)
    def membership_plan_detail(self, plan, **post):
        """Display detailed information about a specific membership plan"""
        # Check if user is logged in (public user means not logged in)
        if request.env.user.id == request.env.ref('base.public_user').id:
            return request.redirect('/web/login?redirect=' + request.httprequest.url)
        
        
        values = {
            'plan': plan,
            'benefits': plan.get_membership_benefits(),
        }
        
        return request.render('popcorn.membership_plan_detail_page', values)
    
    @http.route(['/memberships/<model("popcorn.membership.plan"):plan>/checkout'], type='http', auth="public", website=True)
    def membership_checkout(self, plan, **post):
        """Display checkout page for membership purchase"""
        # Check if user is logged in (public user means not logged in)
        if request.env.user.id == request.env.ref('base.public_user').id:
            return request.redirect('/web/login?redirect=' + request.httprequest.url)
        
        # Check if this is an upgrade
        is_upgrade = post.get('upgrade') == 'true'
        upgrade_details = None
        
        if is_upgrade:
            upgrade_details = request.session.get('upgrade_details', {})
            if not upgrade_details or upgrade_details.get('target_plan_id') != plan.id:
                return request.redirect('/my/cards')
        
        # Check if user is a first-timer
        is_first_timer = request.env.user.partner_id.is_first_timer
        
        # Get discount information for this plan (including extra days)
        best_price, best_discount, extra_days = plan.get_best_discount_with_extra_days(request.env.user.partner_id)
        plan_discounts = {
            plan.id: {
                'best_price': best_price,
                'best_discount': best_discount,
                'original_price': plan.price_normal,
                'extra_days': extra_days,
            }
        }
        
        values = {
            'plan': plan,
            'is_upgrade': is_upgrade,
            'upgrade_details': upgrade_details,
            'is_first_timer': is_first_timer,
            'plan_discounts': plan_discounts,
        }
        
        return request.render('popcorn.membership_checkout_page', values)
    
    @http.route(['/memberships/<model("popcorn.membership.plan"):plan>/process_checkout'], type='http', auth="public", website=True, methods=['POST'])
    def process_membership_checkout(self, plan, **post):
        """Process the checkout form and initiate payment transaction"""
        # Check if user is logged in (public user means not logged in)
        if request.env.user.id == request.env.ref('base.public_user').id:
            return request.redirect('/web/login?redirect=' + request.httprequest.url)
        
        try:
            # Check if this is an upgrade
            upgrade_details = request.session.get('upgrade_details', {})
            is_upgrade = upgrade_details.get('is_upgrade', False)
            
            # Check if user wants to use popcorn money
            use_popcorn_money = post.get('use_popcorn_money') == 'on'
            partner = request.env.user.partner_id
            
            # Ensure partner exists (important for internal users)
            if not partner or not partner.exists():
                _logger.error(f"User {request.env.user.login} does not have a partner record")
                return request.redirect('/memberships/%s/checkout?error=no_partner' % plan.id)
            
            popcorn_money_balance = partner.popcorn_money_balance
            
            # Update or create partner information
            partner_vals = {
                'name': post.get('name'),
                'phone': post.get('phone'),
            }
            
            partner.write(partner_vals)
            
            # Get customer signature if provided
            customer_signature = post.get('customer_signature')
            
            # Get applied discount ID from coupon code (if any)
            applied_discount_id = post.get('applied_discount_id')
            applied_discount = None
            
            if applied_discount_id:
                try:
                    applied_discount = request.env['popcorn.discount'].browse(int(applied_discount_id))
                    if not applied_discount.exists() or not applied_discount.is_valid:
                        applied_discount = None
                except (ValueError, TypeError):
                    applied_discount = None
            
            # Calculate the amount to charge
            if is_upgrade:
                amount = upgrade_details.get('upgrade_price', 0)
            else:
                # Use coupon discount if applied, otherwise use automatic best discount
                if applied_discount:
                    original_price = plan.price_normal
                    if partner.is_first_timer and plan.price_first_timer > 0:
                        original_price = plan.price_first_timer
                    amount = applied_discount.get_discounted_price(plan, original_price, partner)
                    best_discount = applied_discount
                else:
                    # Use discount system to determine best price
                    best_price, best_discount = plan.get_best_discount_price(partner)
                    amount = best_price
            
            # Calculate how much popcorn money to use and remaining amount
            popcorn_money_to_use = 0
            remaining_amount = amount
            
            if use_popcorn_money and popcorn_money_balance > 0:
                popcorn_money_to_use = min(popcorn_money_balance, amount)
                remaining_amount = amount - popcorn_money_to_use
            
            # Validate form data
            if not post.get('name') or not post.get('phone'):
                return request.redirect('/memberships/%s/checkout?error=missing_fields' % plan.id)
            
            if not post.get('payment_method_id') and remaining_amount > 0:
                return request.redirect('/memberships/%s/checkout?error=missing_payment_method' % plan.id)
            
            if not post.get('terms_accepted'):
                return request.redirect('/memberships/%s/checkout?error=terms_not_accepted' % plan.id)
            
            # Get payment method/provider ID
            payment_method_id = post.get('payment_method_id')
            
            # If popcorn money covers the full amount, treat as manual payment
            if remaining_amount <= 0:
                payment_method_id = 'manual'
            
            # Check if it's a manual payment (fallback)
            if payment_method_id == 'manual':
                # Handle upgrade vs new membership
                if is_upgrade:
                    # Upgrade existing membership
                    membership = self._create_upgrade_membership(plan, partner, upgrade_details)
                    _logger.info(f"Upgrade membership created with ID: {membership.id}")
                    
                    # Clear upgrade details from session
                    if 'upgrade_details' in request.session:
                        del request.session['upgrade_details']
                    
                    # Deduct popcorn money if used
                    if use_popcorn_money and popcorn_money_to_use > 0:
                        _logger.info(f"Deducting popcorn money: {popcorn_money_to_use}")
                        partner.deduct_popcorn_money(popcorn_money_to_use, f'Membership upgrade: {plan.display_name}')
                    
                    # Log the upgrade
                    if remaining_amount <= 0:
                        payment_message = _('Membership upgrade completed using Popcorn Money. Price: %s%s. Popcorn money used: %s%s. No additional payment required.') % (plan.currency_id.symbol, amount, plan.currency_id.symbol, popcorn_money_to_use)
                    else:
                        payment_message = _('Manual payment requested for upgrade. Payment method: Manual')
                        if use_popcorn_money and popcorn_money_to_use > 0:
                            payment_message += _('. Popcorn money used: %s%s. Remaining: %s%s') % (plan.currency_id.symbol, popcorn_money_to_use, plan.currency_id.symbol, remaining_amount)
                    
                    membership.message_post(body=payment_message)
                    
                    # Redirect to upgrade success page
                    if remaining_amount <= 0:
                        return request.redirect('/my/cards/upgrade/success?membership_id=%s&payment_completed=true' % membership.id)
                    else:
                        return request.redirect('/my/cards/upgrade/success?membership_id=%s&payment_pending=true' % membership.id)
                else:
                    # Create new membership
                    membership = self._create_membership_from_plan(plan, partner, customer_signature=customer_signature)
                    
                    # Respect the plan's activation policy instead of forcing state
                    if remaining_amount <= 0:
                        # Fully paid with Popcorn Money - follow plan's activation policy
                        if plan.activation_policy == 'immediate':
                            membership.write({'state': 'active', 'activation_date': fields.Date.today()})
                            _logger.info("Membership activated immediately (plan policy)")
                        elif plan.activation_policy == 'first_attendance':
                            membership.write({'state': 'pending'})  # Will be activated on first event registration
                            _logger.info("Membership set to pending (will activate on first event registration)")
                        elif plan.activation_policy == 'manual':
                            membership.write({'state': 'pending'})  # Requires manual activation
                            _logger.info("Membership set to pending (requires manual activation)")
                    else:
                        # Partial payment - mark as pending payment
                        membership.write({'state': 'pending_payment'})
                        _logger.info("Membership set to pending_payment (partial payment)")
                    
                    _logger.info(f"Membership created: {membership.id} with state: {membership.state}, activation_date: {membership.activation_date}")
                    
                    # Deduct popcorn money if used
                    if use_popcorn_money and popcorn_money_to_use > 0:
                        _logger.info(f"Deducting popcorn money: {popcorn_money_to_use}")
                        partner.deduct_popcorn_money(popcorn_money_to_use, f'Membership purchase: {plan.display_name}')
                    
                    # Log the payment request
                    if remaining_amount <= 0:
                        payment_message = _('Membership purchase completed using Popcorn Money. Price: %s%s. Popcorn money used: %s%s. No additional payment required.') % (plan.currency_id.symbol, amount, plan.currency_id.symbol, popcorn_money_to_use)
                    else:
                        payment_message = _('Manual payment requested. Payment method: Manual')
                        if use_popcorn_money and popcorn_money_to_use > 0:
                            payment_message += _('. Popcorn money used: %s%s. Remaining: %s%s') % (plan.currency_id.symbol, popcorn_money_to_use, plan.currency_id.symbol, remaining_amount)
                    
                    membership.message_post(body=payment_message)
                    
                    # Redirect based on payment status
                    if remaining_amount <= 0:
                        return request.redirect('/memberships/success?membership_id=%s&payment_completed=true' % membership.id)
                    else:
                        return request.redirect('/memberships/success?membership_id=%s&payment_pending=true' % membership.id)
            
            # Otherwise, it should be a payment provider ID
            try:
                provider_id = int(payment_method_id)
                
                # Use payment.provider (Odoo 18)
                payment_provider = None
                try:
                    payment_provider = request.env['payment.provider'].browse(provider_id)
                    
                    if not payment_provider or not payment_provider.exists() or payment_provider.state != 'enabled':
                        return request.redirect('/memberships/%s/checkout?error=invalid_payment_method' % plan.id)
                except Exception as e:
                    _logger.error(f"Failed to access payment provider: {str(e)}")
                    return request.redirect('/memberships/%s/checkout?error=payment_access_denied' % plan.id)
                    
            except (ValueError, TypeError):
                return request.redirect('/memberships/%s/checkout?error=invalid_payment_method' % plan.id)
            
            # Check if this is an event purchase
            is_event_purchase = request.params.get('event_purchase') == 'true'
            
            # Store membership details in session for after payment
            request.session['pending_membership'] = {
                'plan_id': plan.id,
                'partner_id': partner.id,
                'amount': amount,
                'payment_provider_id': payment_provider.id,
                'payment_provider_name': payment_provider.name,
                'is_upgrade': is_upgrade,
                'upgrade_details': upgrade_details if is_upgrade else None,
                'is_event_purchase': is_event_purchase,
                'use_popcorn_money': use_popcorn_money,
                'popcorn_money_to_use': popcorn_money_to_use,
                'remaining_amount': remaining_amount,
                'customer_signature': customer_signature,
                'applied_discount_id': applied_discount.id if applied_discount else None,
            }
            
            _logger.info(f"Stored pending membership in session: {request.session['pending_membership']}")
            
            # Handle different payment methods based on provider name
            _logger.info(f"Payment provider name: '{payment_provider.name}', lowercase: '{payment_provider.name.lower()}'")
            if payment_provider.name.lower() in ['bank transfer', 'bank_transfer']:
                # For bank transfer, create membership immediately but mark as pending payment
                membership = self._create_membership_from_plan(plan, partner, customer_signature=customer_signature, applied_discount=applied_discount)
                membership.write({'state': 'pending_payment'})
                
                # Log the bank transfer payment request
                membership.message_post(
                    body=_('Bank transfer payment requested. Payment method: %s') % payment_provider.name
                )
                
                # Redirect to success page with pending payment status
                return request.redirect('/memberships/success?membership_id=%s&payment_pending=true' % membership.id)
            elif payment_provider.name.lower() in ['wechat', 'wechat pay', 'wechatpay']:
                # For WeChat payments, redirect to WeChat OAuth2 flow
                _logger.info(f"Creating WeChat payment transaction for provider: {payment_provider.name}")
                
                # Get or create a default payment method for the provider
                payment_method = request.env['payment.method'].sudo().search([
                    ('provider_ids', 'in', payment_provider.id),
                    ('active', '=', True)
                ], limit=1)
                
                if not payment_method:
                    # Create a default payment method for this provider
                    payment_method = request.env['payment.method'].sudo().create({
                        'name': f'{payment_provider.name} Payment',
                        'code': payment_provider.code.lower().replace(' ', '_'),
                        'provider_ids': [(6, 0, [payment_provider.id])],
                        'active': True,
                    })
                
                # Create payment transaction with unique reference (NO membership created yet)
                import time
                timestamp = int(time.time())
                
                payment_transaction = request.env['payment.transaction'].sudo().create({
                    'provider_id': payment_provider.id,
                    'payment_method_id': payment_method.id,
                    'amount': remaining_amount,
                    'currency_id': plan.currency_id.id,
                    'partner_id': partner.id,
                    'reference': f'MEMBERSHIP-{plan.id}-{partner.id}-{timestamp}',
                    'state': 'draft',
                })
                
                _logger.info(f"WeChat payment transaction created with ID: {payment_transaction.id}")
                
                # Store transaction ID and membership data in session for callback (NO membership created yet)
                request.session['payment_transaction_id'] = payment_transaction.id
                # pending_membership is already stored in session above
                
                # Store the membership data in session for WeChat success callback
                request.session['wechat_pending_membership'] = {
                    'plan_id': plan.id,
                    'partner_id': partner.id,
                    'amount': amount,
                    'payment_provider_id': payment_provider.id,
                    'payment_provider_name': payment_provider.name,
                    'is_upgrade': is_upgrade,
                    'upgrade_details': upgrade_details if is_upgrade else None,
                    'use_popcorn_money': use_popcorn_money,
                    'popcorn_money_to_use': popcorn_money_to_use,
                    'remaining_amount': remaining_amount,
                }
                
                # Redirect to WeChat OAuth2 flow
                wechat_oauth_url = f'/payment/wechat/oauth2/authorize?transaction_id={payment_transaction.reference}'
                _logger.info(f"Redirecting to WeChat OAuth2: {wechat_oauth_url}")
                return request.redirect(wechat_oauth_url)
            elif payment_provider.name.lower() in ['alipay']:
                # For Alipay payments, create transaction and redirect to Alipay WAP payment
                _logger.info(f"Creating Alipay payment transaction for provider: {payment_provider.name}")
                
                # Get or create a default payment method for the provider
                payment_method = request.env['payment.method'].sudo().search([
                    ('provider_ids', 'in', payment_provider.id),
                    ('active', '=', True)
                ], limit=1)
                
                if not payment_method:
                    # Create a default payment method for this provider
                    payment_method = request.env['payment.method'].sudo().create({
                        'name': f'{payment_provider.name} Payment',
                        'code': payment_provider.code.lower().replace(' ', '_'),
                        'provider_ids': [(6, 0, [payment_provider.id])],
                        'active': True,
                    })
                
                # Create payment transaction with unique reference (NO membership created yet)
                import time
                timestamp = int(time.time())
                
                # Prepare pending purchase data to store in transaction (for webhook processing)
                import json
                pending_purchase_json = json.dumps({
                    'type': 'membership',
                    'plan_id': plan.id,
                    'partner_id': partner.id,
                    'amount': amount,
                    'popcorn_money_to_use': popcorn_money_to_use,
                    'remaining_amount': remaining_amount,
                    'is_upgrade': is_upgrade,
                    'upgrade_details': upgrade_details if is_upgrade else None,
                    'use_popcorn_money': use_popcorn_money,
                })
                
                payment_transaction = request.env['payment.transaction'].sudo().create({
                    'provider_id': payment_provider.id,
                    'payment_method_id': payment_method.id,
                    'amount': remaining_amount,
                    'currency_id': plan.currency_id.id,
                    'partner_id': partner.id,
                    'reference': f'MEMBERSHIP-{plan.id}-{partner.id}-{timestamp}',
                    'state': 'draft',
                    'pending_purchase_data': pending_purchase_json,  # Store for webhook processing
                })
                
                _logger.info(f"Alipay payment transaction created with ID: {payment_transaction.id}")
                _logger.info(f"Pending purchase data stored in transaction for webhook processing")
                
                # Store transaction ID and membership data in session for callback (NO membership created yet)
                request.session['payment_transaction_id'] = payment_transaction.id
                # pending_membership is already stored in session above
                
                # Get Alipay payment URL
                alipay_payment_url = payment_transaction._get_payment_link()
                
                if not alipay_payment_url:
                    _logger.error("Failed to get Alipay payment URL")
                    return request.redirect('/memberships/payment/failed?error=gateway_unavailable')
                
                # Redirect to Alipay payment page
                _logger.info(f"Redirecting to Alipay payment: {alipay_payment_url[:100]}...")
                from werkzeug.utils import redirect
                return redirect(alipay_payment_url, code=302)
            else:
                # For all other online payments (Stripe/PayPal/etc), create payment transaction and redirect to gateway
                _logger.info(f"Creating payment transaction for provider: {payment_provider.name}")
                
                # Get or create a default payment method for the provider
                payment_method = request.env['payment.method'].sudo().search([
                    ('provider_ids', 'in', payment_provider.id),
                    ('active', '=', True)
                ], limit=1)
                
                if not payment_method:
                    # Create a default payment method for this provider
                    payment_method = request.env['payment.method'].sudo().create({
                        'name': f'{payment_provider.name} Payment',
                        'code': payment_provider.code.lower().replace(' ', '_'),
                        'provider_ids': [(6, 0, [payment_provider.id])],
                        'active': True,
                    })
                
                # Create payment transaction with unique reference (NO membership created yet)
                import time
                timestamp = int(time.time())
                
                payment_transaction = request.env['payment.transaction'].sudo().create({
                    'provider_id': payment_provider.id,
                    'payment_method_id': payment_method.id,
                    'amount': remaining_amount,
                    'currency_id': plan.currency_id.id,
                    'partner_id': partner.id,
                    'reference': f'MEMBERSHIP-{plan.id}-{partner.id}-{timestamp}',
                    'state': 'draft',
                })
                
                _logger.info(f"Payment transaction created with ID: {payment_transaction.id}")
                
                # Store transaction ID and membership data in session for callback (NO membership created yet)
                request.session['payment_transaction_id'] = payment_transaction.id
                # pending_membership is already stored in session above
                
                # Let the payment gateway handle the payment flow
                try:
                    payment_link = payment_transaction._get_specific_rendering_values(None)
                    if payment_link and 'action_url' in payment_link:
                        _logger.info(f"Redirecting to payment gateway: {payment_link['action_url']}")
                        return request.redirect(payment_link['action_url'])
                except Exception as e:
                    _logger.warning(f"Failed to get payment link: {str(e)}")
                
                # Fallback: if no payment link available, redirect to payment failed page
                _logger.warning("No payment link available, redirecting to payment failed page")
                request.session.pop('pending_membership', None)
                return request.redirect('/memberships/payment/failed?error=gateway_unavailable')
            
        except Exception as e:
            _logger.error(f"Failed to process checkout: {str(e)}")
            return request.redirect('/memberships/%s/checkout?error=processing_failed' % plan.id)
    
    @http.route(['/memberships/payment/process'], type='http', auth="public", website=True, methods=['GET', 'POST'])
    def membership_payment_process(self, **post):
        """Process payment simulation and create membership upon successful payment"""
        try:
            # Get payment method and details from URL parameters
            payment_method = request.params.get('method')
            plan_id = request.params.get('plan_id')
            amount = request.params.get('amount')
            
            if not payment_method or not plan_id:
                return request.redirect('/memberships?error=payment_failed')
            
            # Get pending membership details from session
            pending_membership = request.session.get('pending_membership')
            if not pending_membership:
                return request.redirect('/memberships?error=session_expired')
            
            # Get the plan and partner
            plan = request.env['popcorn.membership.plan'].browse(int(plan_id))
            partner = request.env['res.partner'].browse(pending_membership['partner_id'])
            
            if not plan.exists() or not partner.exists():
                return request.redirect('/memberships?error=invalid_data')
            
            # Get the payment provider
            payment_provider = None
            try:
                payment_provider = request.env['payment.provider'].browse(pending_membership['payment_provider_id'])
                
                if not payment_provider or not payment_provider.exists():
                    return request.redirect('/memberships?error=payment_provider_not_found')
            except Exception as e:
                _logger.error(f"Failed to access payment provider in processing: {str(e)}")
                # Use fallback provider name from session
                payment_provider = type('obj', (object,), {'name': pending_membership.get('payment_provider_name', 'Unknown Provider')})
            
            # Create actual payment transaction
            _logger.info(f"Creating payment transaction for provider: {payment_provider.name}")
            
            # Get or create a default payment method for the provider
            payment_method = request.env['payment.method'].sudo().search([
                ('provider_ids', 'in', payment_provider.id),
                ('active', '=', True)
            ], limit=1)
            
            if not payment_method:
                # Create a default payment method for this provider
                payment_method = request.env['payment.method'].sudo().create({
                    'name': f'{payment_provider.name} Payment',
                    'code': payment_provider.code.lower().replace(' ', '_'),
                    'provider_ids': [(6, 0, [payment_provider.id])],
                    'active': True,
                })
            
            # Create payment transaction with unique reference
            import time
            timestamp = int(time.time())
            payment_transaction = request.env['payment.transaction'].sudo().create({
                'provider_id': payment_provider.id,
                'payment_method_id': payment_method.id,
                'amount': amount,
                'currency_id': plan.currency_id.id,
                'partner_id': partner.id,
                'reference': f'MEMBERSHIP-{plan.id}-{partner.id}-{timestamp}',
                'state': 'draft',
            })
            
            _logger.info(f"Payment transaction created with ID: {payment_transaction.id}")
            
            # Generate payment link and redirect to actual payment gateway
            payment_link = payment_transaction._get_specific_rendering_values(None)
            
            if payment_link and 'action_url' in payment_link:
                # Store transaction ID in session for callback
                request.session['payment_transaction_id'] = payment_transaction.id
                request.session['pending_membership'] = pending_membership  # Keep membership data
                
                _logger.info(f"Redirecting to payment gateway: {payment_link['action_url']}")
                return request.redirect(payment_link['action_url'])
            else:
                # Fallback: create membership directly if no payment link available
                _logger.warning("No payment link available, creating membership directly")
                
                # Create the membership
                if pending_membership['is_upgrade']:
                    # Handle upgrade
                    membership = self._create_upgrade_membership(plan, partner, pending_membership['upgrade_details'])
                    _logger.info(f"Upgrade membership created with ID: {membership.id}")
                    
                    # Clear upgrade details from session
                    request.session.pop('upgrade_details', None)
                    
                    # Log the upgrade
                    membership.message_post(
                        body=_('Membership upgraded through %s payment. Amount: %s') % (payment_provider.name, amount)
                    )
                    
                    # Clear pending membership from session
                    request.session.pop('pending_membership', None)
                    
                    _logger.info(f"Redirecting to upgrade success page: /my/cards/upgrade/success?membership_id={membership.id}")
                    # Redirect to upgrade success page
                    return request.redirect('/my/cards/upgrade/success?membership_id=%s' % membership.id)
                else:
                    # Create regular membership
                    membership = self._create_membership_from_plan(plan, partner, customer_signature=pending_membership.get('customer_signature'))
                    _logger.info(f"Regular membership created with ID: {membership.id}")
                    
                    # Log the purchase
                    membership.message_post(
                        body=_('Membership purchased through %s payment. Amount: %s') % (payment_provider.name, amount)
                    )
                    
                    # Clear pending membership from session
                    request.session.pop('pending_membership', None)
                    
                    _logger.info(f"Redirecting to success page: /memberships/success?membership_id={membership.id}")
                    # Redirect to success page
                    return request.redirect('/memberships/success?membership_id=%s' % membership.id)
                
        except Exception as e:
            _logger.error(f"Failed to process payment: {str(e)}")
            # Clear session data on error
            request.session.pop('pending_membership', None)
            return request.redirect('/memberships?error=payment_processing_failed')

    @http.route(['/memberships/payment/callback'], type='http', auth="public", website=True, methods=['GET', 'POST'])
    def membership_payment_callback(self, **post):
        """Handle payment callback from payment gateway"""
        try:
            # Check if this is a WeChat payment success redirect (from JavaScript)
            payment_success = post.get('payment_success')
            transaction_id_param = post.get('transaction_id')
            
            # Check if this is an event purchase redirect (from event checkout)
            is_event_purchase_redirect = request.session.get('event_purchase_details') or request.session.get('wechat_pending_event_purchase')
            
            if payment_success == 'true' and transaction_id_param:
                # This is a WeChat payment success redirect from JavaScript
                _logger.info(f"WeChat payment success redirect for transaction: {transaction_id_param}")
                
                # Handle event purchase redirect FIRST
                if is_event_purchase_redirect:
                    _logger.info("Redirecting to event purchase success handler")
                    return self._handle_event_purchase_redirect(transaction_id_param)
                
                # Get pending membership data from session
                pending_membership = request.session.get('pending_membership')
                if not pending_membership:
                    _logger.error("No pending membership found in session for WeChat callback")
                    return request.redirect('/memberships/payment/failed?error=session_expired')
                
                # Get the transaction
                transaction = request.env['payment.transaction'].sudo().browse(int(transaction_id_param))
                if not transaction.exists():
                    _logger.error(f"Transaction {transaction_id_param} not found")
                    return request.redirect('/memberships/payment/failed?error=transaction_not_found')
                
                # Mark transaction as done (WeChat payment was successful)
                transaction.write({'state': 'done'})
                
                # Create membership now
                plan = request.env['popcorn.membership.plan'].browse(pending_membership['plan_id'])
                partner = request.env['res.partner'].browse(pending_membership['partner_id'])
                
                # Deduct popcorn money if used
                if pending_membership.get('use_popcorn_money') and pending_membership.get('popcorn_money_to_use', 0) > 0:
                    partner.deduct_popcorn_money(pending_membership['popcorn_money_to_use'], f'Membership purchase: {plan.display_name}')
                
                if pending_membership['is_upgrade']:
                    membership = self._create_upgrade_membership(plan, partner, pending_membership['upgrade_details'])
                    membership.write({
                        'payment_transaction_id': transaction.id,
                        'payment_reference': transaction.reference
                    })
                    payment_message = _('Payment successful via %s. Transaction: %s. Membership upgraded and activated.') % (transaction.provider_id.name, transaction.reference)
                    if pending_membership.get('use_popcorn_money') and pending_membership.get('popcorn_money_to_use', 0) > 0:
                        payment_message += _('. Popcorn money used: %s%s. Remaining: %s%s') % (plan.currency_id.symbol, pending_membership['popcorn_money_to_use'], plan.currency_id.symbol, pending_membership.get('remaining_amount', 0))
                    membership.message_post(body=payment_message)
                    redirect_url = '/my/cards/upgrade/success?membership_id=%s' % membership.id
                else:
                    membership = self._create_membership_from_plan(plan, partner, customer_signature=pending_membership.get('customer_signature') if 'pending_membership' in locals() else None)
                    
                    # Respect the plan's activation policy
                    membership_vals = {
                        'payment_transaction_id': transaction.id,
                        'payment_reference': transaction.reference,
                    }
                    
                    if plan.activation_policy == 'immediate':
                        membership_vals['state'] = 'active'
                        membership_vals['activation_date'] = fields.Date.today()
                    elif plan.activation_policy == 'first_attendance':
                        membership_vals['state'] = 'pending'  # Will be activated on first event registration
                    elif plan.activation_policy == 'manual':
                        membership_vals['state'] = 'pending'  # Requires manual activation
                    
                    membership.write(membership_vals)
                    payment_message = _('Payment successful via %s. Transaction: %s. Membership created and activated.') % (transaction.provider_id.name, transaction.reference)
                    if pending_membership.get('use_popcorn_money') and pending_membership.get('popcorn_money_to_use', 0) > 0:
                        payment_message += _('. Popcorn money used: %s%s. Remaining: %s%s') % (plan.currency_id.symbol, pending_membership['popcorn_money_to_use'], plan.currency_id.symbol, pending_membership.get('remaining_amount', 0))
                    membership.message_post(body=payment_message)
                    redirect_url = '/memberships/success?membership_id=%s' % membership.id
                
                # Clear session data
                request.session.pop('payment_transaction_id', None)
                request.session.pop('pending_membership', None)
                request.session.pop('upgrade_details', None)
                
                _logger.info(f"WeChat payment successful. Membership created with ID: {membership.id}")
                return request.redirect(redirect_url)
            
            # Original callback logic for other payment gateways
            # Get transaction ID and pending membership data from session
            transaction_id = request.session.get('payment_transaction_id')
            pending_membership = request.session.get('pending_membership')
            
            if not transaction_id or not pending_membership:
                _logger.error("No transaction ID or pending membership found in session")
                return request.redirect('/memberships/payment/failed?error=session_expired')
            
            # Get the transaction
            transaction = request.env['payment.transaction'].sudo().browse(transaction_id)
            
            if not transaction.exists():
                _logger.error(f"Transaction {transaction_id} not found")
                return request.redirect('/memberships/payment/failed?error=transaction_not_found')
            
            # Check payment status
            if transaction.state == 'done':
                # Payment successful - create membership or event registration now
                plan = request.env['popcorn.membership.plan'].browse(pending_membership['plan_id'])
                partner = request.env['res.partner'].browse(pending_membership['partner_id'])
                
                # Deduct popcorn money if used
                if pending_membership.get('use_popcorn_money') and pending_membership.get('popcorn_money_to_use', 0) > 0:
                    _logger.info(f"Deducting popcorn money: {pending_membership['popcorn_money_to_use']}")
                    partner.deduct_popcorn_money(pending_membership['popcorn_money_to_use'], f'Membership purchase: {plan.display_name}')
                
                # Check if this is an event purchase
                if pending_membership.get('is_event_purchase', False):
                    # Handle event purchase
                    registration = self._handle_event_purchase(plan, partner, transaction.id, transaction.reference)
                    if registration:
                        redirect_url = f'/popcorn/event/{registration.event_id.id}/purchase/success?registration_id={registration.id}'
                    else:
                        redirect_url = '/memberships/payment/failed?error=event_registration_failed'
                elif pending_membership['is_upgrade']:
                    membership = self._create_upgrade_membership(plan, partner, pending_membership['upgrade_details'])
                    membership.write({
                        'payment_transaction_id': transaction.id,
                        'payment_reference': transaction.reference
                    })
                    payment_message = _('Payment successful via %s. Transaction: %s. Membership upgraded and activated.') % (transaction.provider_id.name, transaction.reference)
                    if pending_membership.get('use_popcorn_money') and pending_membership.get('popcorn_money_to_use', 0) > 0:
                        payment_message += _('. Popcorn money used: %s%s. Remaining: %s%s') % (plan.currency_id.symbol, pending_membership['popcorn_money_to_use'], plan.currency_id.symbol, pending_membership.get('remaining_amount', 0))
                    membership.message_post(body=payment_message)
                    redirect_url = '/my/cards/upgrade/success?membership_id=%s' % membership.id
                else:
                    membership = self._create_membership_from_plan(plan, partner, customer_signature=pending_membership.get('customer_signature') if 'pending_membership' in locals() else None)
                    
                    # Respect the plan's activation policy
                    membership_vals = {
                        'payment_transaction_id': transaction.id,
                        'payment_reference': transaction.reference,
                    }
                    
                    if plan.activation_policy == 'immediate':
                        membership_vals['state'] = 'active'
                        membership_vals['activation_date'] = fields.Date.today()
                    elif plan.activation_policy == 'first_attendance':
                        membership_vals['state'] = 'pending'  # Will be activated on first event registration
                    elif plan.activation_policy == 'manual':
                        membership_vals['state'] = 'pending'  # Requires manual activation
                    
                    membership.write(membership_vals)
                    payment_message = _('Payment successful via %s. Transaction: %s. Membership created and activated.') % (transaction.provider_id.name, transaction.reference)
                    if pending_membership.get('use_popcorn_money') and pending_membership.get('popcorn_money_to_use', 0) > 0:
                        payment_message += _('. Popcorn money used: %s%s. Remaining: %s%s') % (plan.currency_id.symbol, pending_membership['popcorn_money_to_use'], plan.currency_id.symbol, pending_membership.get('remaining_amount', 0))
                    membership.message_post(body=payment_message)
                    redirect_url = '/memberships/success?membership_id=%s' % membership.id
                
                # Clear session data
                request.session.pop('payment_transaction_id', None)
                request.session.pop('pending_membership', None)
                request.session.pop('upgrade_details', None)
                
                _logger.info(f"Payment successful. Membership created with ID: {membership.id}")
                return request.redirect(redirect_url)
                
            elif transaction.state == 'cancel':
                # Payment cancelled - no membership created
                _logger.info(f"Payment cancelled for transaction {transaction_id}")
                
                # Clear session data
                request.session.pop('payment_transaction_id', None)
                request.session.pop('pending_membership', None)
                request.session.pop('upgrade_details', None)
                
                return request.redirect('/memberships/payment/failed?error=payment_cancelled')
                
            else:
                # Payment pending or failed - no membership created
                _logger.warning(f"Payment not completed for transaction {transaction_id}. State: {transaction.state}")
                
                # Clear session data
                request.session.pop('payment_transaction_id', None)
                request.session.pop('pending_membership', None)
                request.session.pop('upgrade_details', None)
                
                return request.redirect('/memberships/payment/failed?error=payment_failed')
                
        except Exception as e:
            _logger.error(f"Failed to handle payment callback: {str(e)}")
            return request.redirect('/memberships/payment/failed?error=callback_failed')

    def _find_membership_by_transaction_reference(self, transaction_reference):
        """Find membership by transaction reference"""
        try:
            # Parse transaction reference: MEMBERSHIP-{plan_id}-{partner_id}-{timestamp}
            if not transaction_reference.startswith('MEMBERSHIP-'):
                return None
            
            parts = transaction_reference.split('-')
            if len(parts) < 3:
                return None
            
            partner_id = int(parts[2])
            
            # Find pending membership for this partner
            membership = request.env['popcorn.membership'].sudo().search([
                ('partner_id', '=', partner_id),
                ('state', '=', 'pending_payment'),
                ('purchase_channel', '=', 'online')
            ], order='create_date desc', limit=1)
            
            return membership
            
        except (ValueError, IndexError) as e:
            _logger.error("Failed to parse transaction reference %s: %s", transaction_reference, str(e))
            return None
        except Exception as e:
            _logger.error("Failed to find membership for transaction %s: %s", transaction_reference, str(e))
            return None

    @http.route(['/memberships/<model("popcorn.membership.plan"):plan>/purchase'], type='http', auth="public", website=True)
    def membership_purchase(self, plan, **post):
        """Handle membership purchase"""
        # Check if user is logged in (public user means not logged in)
        if request.env.user.id == request.env.ref('base.public_user').id:
            return request.redirect('/web/login?redirect=' + request.httprequest.url)
        
        if request.httprequest.method == 'POST':
            # Handle the purchase
            try:
                # Create a direct membership purchase
                membership = self._create_membership_from_plan(plan, request.env.user.partner_id)
                
                # Redirect to success page
                return request.redirect('/memberships/success')
                
            except Exception as e:
                _logger.error(f"Failed to create membership: {str(e)}")
                return request.redirect('/memberships/error')
        
        # Display purchase form
        values = {
            'plan': plan,
        }
        
        return request.render('popcorn.membership_purchase_page', values)
    
    @http.route(['/memberships/success'], type='http', auth="public", website=True)
    def membership_success(self, **post):
        """Display success page after membership purchase"""
        # Check if user is logged in (public user means not logged in)
        if request.env.user.id == request.env.ref('base.public_user').id:
            return request.redirect('/web/login?redirect=' + request.httprequest.url)
        
        # Check if this is an event purchase redirect (from WeChat JavaScript)
        payment_success = post.get('payment_success')
        transaction_id_param = post.get('transaction_id')
        is_event_purchase_redirect = request.session.get('event_purchase_details') or request.session.get('wechat_pending_event_purchase')
        
        if payment_success == 'true' and transaction_id_param and is_event_purchase_redirect:
            _logger.info(f"Event purchase redirect detected in membership success route, redirecting to event handler")
            return self._handle_event_purchase_redirect(transaction_id_param)
        
        membership_id = post.get('membership_id')
        membership = None
        
        # Handle WeChat payment success redirect
        if payment_success == 'true' and transaction_id_param:
            _logger.info(f"=== WeChat payment success redirect ===")
            _logger.info(f"Transaction ID: {transaction_id_param}")
            _logger.info(f"Session keys: {list(request.session.keys())}")
            _logger.info(f"WeChat pending membership in session: {bool(request.session.get('wechat_pending_membership'))}")
            _logger.info(f"Regular pending membership in session: {bool(request.session.get('pending_membership'))}")
            
            # Get pending membership data from session (try both keys)
            pending_membership = request.session.get('wechat_pending_membership')
            if not pending_membership:
                _logger.warning("No WeChat pending membership found, trying regular pending membership")
                pending_membership = request.session.get('pending_membership')
                
            if not pending_membership:
                _logger.error("No pending membership found in session (neither WeChat nor regular)")
                _logger.error(f"Session contents: {dict(request.session)}")
                return request.redirect('/memberships/payment/failed?error=session_expired')
            
            # Get the transaction
            transaction = None
            _logger.info(f"Looking for transaction with ID/reference: {transaction_id_param}")
            
            try:
                # First try as integer ID
                transaction = request.env['payment.transaction'].sudo().browse(int(transaction_id_param))
                _logger.info(f"Tried as integer ID, found: {transaction.exists() if transaction else False}")
                if not transaction.exists():
                    transaction = None
            except (ValueError, TypeError) as e:
                _logger.info(f"Failed to parse as integer ID: {e}")
                pass
            
            # If not found as ID, try as reference
            if not transaction or not transaction.exists():
                _logger.info(f"Trying to find by reference: {transaction_id_param}")
                transaction = request.env['payment.transaction'].sudo().search([
                    ('reference', '=', transaction_id_param),
                    ('provider_code', '=', 'wechat')
                ], limit=1)
                _logger.info(f"Found by reference: {transaction.exists() if transaction else False}")
            
            if not transaction or not transaction.exists():
                _logger.error(f"WeChat transaction {transaction_id_param} not found")
                # Let's also search without provider_code filter
                all_transactions = request.env['payment.transaction'].sudo().search([
                    ('reference', '=', transaction_id_param)
                ])
                _logger.error(f"Found {len(all_transactions)} transactions with reference {transaction_id_param}")
                for t in all_transactions:
                    _logger.error(f"  Transaction ID: {t.id}, Provider: {t.provider_id.name if t.provider_id else 'None'}, Code: {t.provider_code}")
                return request.redirect('/memberships/payment/failed?error=transaction_not_found')
            
            _logger.info(f"Found transaction: {transaction.id}, State: {transaction.state}, Provider: {transaction.provider_id.name if transaction.provider_id else 'None'}")
            
            # Mark transaction as done (WeChat payment was successful)
            transaction.write({'state': 'done'})
            
            # Create membership now
            _logger.info(f"Creating membership with data: {pending_membership}")
            plan = request.env['popcorn.membership.plan'].browse(pending_membership['plan_id'])
            partner = request.env['res.partner'].browse(pending_membership['partner_id'])
            
            # Deduct popcorn money if used
            if pending_membership.get('use_popcorn_money') and pending_membership.get('popcorn_money_to_use', 0) > 0:
                partner.deduct_popcorn_money(pending_membership['popcorn_money_to_use'], f'Membership purchase: {plan.display_name}')
            
            _logger.info(f"Plan exists: {plan.exists()}, Partner exists: {partner.exists()}")
            _logger.info(f"Plan name: {plan.name if plan.exists() else 'N/A'}, Partner name: {partner.name if partner.exists() else 'N/A'}")
            
            if not plan.exists() or not partner.exists():
                _logger.error(f"Invalid plan or partner - Plan ID: {pending_membership.get('plan_id')}, Partner ID: {pending_membership.get('partner_id')}")
                return request.redirect('/memberships/payment/failed?error=invalid_data')
            
            if pending_membership.get('is_upgrade', False):
                _logger.info("Creating upgrade membership")
                membership = self._create_upgrade_membership(plan, partner, pending_membership['upgrade_details'])
                membership.write({
                    'payment_transaction_id': transaction.id,
                    'payment_reference': transaction.reference
                })
                membership.message_post(
                    body=_('Payment successful via %s. Transaction: %s. Membership upgraded and activated.') % (transaction.provider_id.name, transaction.reference)
                )
                # Clear upgrade details from session
                request.session.pop('upgrade_details', None)
                _logger.info(f"Upgrade membership created with ID: {membership.id}")
            else:
                _logger.info("Creating regular membership")
                membership = self._create_membership_from_plan(plan, partner, customer_signature=pending_membership.get('customer_signature') if 'pending_membership' in locals() else None)
                _logger.info(f"Membership created with ID: {membership.id}, State: {membership.state}")
                
                membership_vals = {
                    'payment_transaction_id': transaction.id,
                    'payment_reference': transaction.reference,
                }
                
                if plan.activation_policy == 'immediate':
                    membership_vals['state'] = 'active'
                    membership_vals['activation_date'] = fields.Date.today()
                elif plan.activation_policy == 'first_attendance':
                    membership_vals['state'] = 'pending'  # Will be activated on first event registration
                elif plan.activation_policy == 'manual':
                    membership_vals['state'] = 'pending'  # Requires manual activation
                
                membership.write(membership_vals)
                _logger.info(f"Membership updated - State: {membership.state}, Activation Date: {membership.activation_date}")
                
                membership.message_post(
                    body=_('Payment successful via %s. Transaction: %s. Membership created and activated.') % (transaction.provider_id.name, transaction.reference)
                )
                _logger.info(f"Membership message posted")
            
            # Clear session data
            request.session.pop('payment_transaction_id', None)
            request.session.pop('pending_membership', None)
            request.session.pop('wechat_pending_membership', None)
            
            _logger.info(f"WeChat payment successful. Membership created with ID: {membership.id}")
            _logger.info(f"Final membership details - ID: {membership.id}, State: {membership.state}, Partner: {membership.partner_id.name}")
            
            # Continue to show success page with the created membership
            # (don't redirect, just continue with the existing membership)
        
        # Regular success page handling
        if membership_id:
            membership = request.env['popcorn.membership'].browse(int(membership_id))
        
        values = {
            'membership': membership,
        }
        
        return request.render('popcorn.membership_success_page', values)
    
    @http.route(['/memberships/wechat/success'], type='http', auth="public", website=True)
    def wechat_membership_success(self, **post):
        """Handle WeChat payment success and create membership"""
        # Check if user is logged in (public user means not logged in)
        if request.env.user.id == request.env.ref('base.public_user').id:
            return request.redirect('/web/login?redirect=' + request.httprequest.url)
        
        try:
            transaction_id_param = post.get('transaction_id')
            _logger.info(f"=== WeChat membership success route called ===")
            _logger.info(f"Transaction ID: {transaction_id_param}")
            _logger.info(f"All POST params: {post}")
            _logger.info(f"Session keys: {list(request.session.keys())}")
            _logger.info(f"WeChat pending membership in session: {bool(request.session.get('wechat_pending_membership'))}")
            _logger.info(f"Regular pending membership in session: {bool(request.session.get('pending_membership'))}")
            
            if not transaction_id_param:
                _logger.error("WeChat membership success failed - Transaction ID required")
                return request.redirect('/memberships/payment/failed?error=transaction_id_required')
            
            # Get WeChat pending membership data from session
            wechat_pending_membership = request.session.get('wechat_pending_membership')
            
            # Fallback to regular pending membership if WeChat one not found
            if not wechat_pending_membership:
                _logger.warning("No WeChat pending membership found, trying regular pending membership")
                wechat_pending_membership = request.session.get('pending_membership')
                
            if not wechat_pending_membership:
                _logger.error("No pending membership found in session (neither WeChat nor regular)")
                _logger.error(f"Session contents: {dict(request.session)}")
                return request.redirect('/memberships/payment/failed?error=session_expired')
            
            # Get the transaction
            transaction = None
            _logger.info(f"Looking for transaction with ID/reference: {transaction_id_param}")
            
            try:
                # First try as integer ID
                transaction = request.env['payment.transaction'].sudo().browse(int(transaction_id_param))
                _logger.info(f"Tried as integer ID, found: {transaction.exists() if transaction else False}")
                if not transaction.exists():
                    transaction = None
            except (ValueError, TypeError) as e:
                _logger.info(f"Failed to parse as integer ID: {e}")
                pass
            
            # If not found as ID, try as reference
            if not transaction or not transaction.exists():
                _logger.info(f"Trying to find by reference: {transaction_id_param}")
                transaction = request.env['payment.transaction'].sudo().search([
                    ('reference', '=', transaction_id_param),
                    ('provider_code', '=', 'wechat')
                ], limit=1)
                _logger.info(f"Found by reference: {transaction.exists() if transaction else False}")
            
            if not transaction or not transaction.exists():
                _logger.error(f"WeChat transaction {transaction_id_param} not found")
                # Let's also search without provider_code filter
                all_transactions = request.env['payment.transaction'].sudo().search([
                    ('reference', '=', transaction_id_param)
                ])
                _logger.error(f"Found {len(all_transactions)} transactions with reference {transaction_id_param}")
                for t in all_transactions:
                    _logger.error(f"  Transaction ID: {t.id}, Provider: {t.provider_id.name if t.provider_id else 'None'}, Code: {t.provider_code}")
                return request.redirect('/memberships/payment/failed?error=transaction_not_found')
            
            _logger.info(f"Found transaction: {transaction.id}, State: {transaction.state}, Provider: {transaction.provider_id.name if transaction.provider_id else 'None'}")
            
            # Mark transaction as done (WeChat payment was successful)
            transaction.write({'state': 'done'})
            
            # Create membership now
            _logger.info(f"Creating membership with data: {wechat_pending_membership}")
            plan = request.env['popcorn.membership.plan'].browse(wechat_pending_membership['plan_id'])
            partner = request.env['res.partner'].browse(wechat_pending_membership['partner_id'])
            
            # Deduct popcorn money if used
            if wechat_pending_membership.get('use_popcorn_money') and wechat_pending_membership.get('popcorn_money_to_use', 0) > 0:
                partner.deduct_popcorn_money(wechat_pending_membership['popcorn_money_to_use'], f'Membership purchase: {plan.display_name}')
            
            _logger.info(f"Plan exists: {plan.exists()}, Partner exists: {partner.exists()}")
            _logger.info(f"Plan name: {plan.name if plan.exists() else 'N/A'}, Partner name: {partner.name if partner.exists() else 'N/A'}")
            
            if not plan.exists() or not partner.exists():
                _logger.error(f"Invalid plan or partner - Plan ID: {wechat_pending_membership.get('plan_id')}, Partner ID: {wechat_pending_membership.get('partner_id')}")
                return request.redirect('/memberships/payment/failed?error=invalid_data')
            
            if wechat_pending_membership.get('is_upgrade', False):
                _logger.info("Creating upgrade membership")
                membership = self._create_upgrade_membership(plan, partner, wechat_pending_membership['upgrade_details'])
                membership.write({
                    'payment_transaction_id': transaction.id,
                    'payment_reference': transaction.reference
                })
                payment_message = _('Payment successful via %s. Transaction: %s. Membership upgraded and activated.') % (transaction.provider_id.name, transaction.reference)
                if wechat_pending_membership.get('use_popcorn_money') and wechat_pending_membership.get('popcorn_money_to_use', 0) > 0:
                    payment_message += _('. Popcorn money used: %s%s. Remaining: %s%s') % (plan.currency_id.symbol, wechat_pending_membership['popcorn_money_to_use'], plan.currency_id.symbol, wechat_pending_membership.get('remaining_amount', 0))
                membership.message_post(body=payment_message)
                # Clear upgrade details from session
                request.session.pop('upgrade_details', None)
                _logger.info(f"Upgrade membership created with ID: {membership.id}")
            else:
                _logger.info("Creating regular membership")
                membership = self._create_membership_from_plan(plan, partner, customer_signature=wechat_pending_membership.get('customer_signature'))
                _logger.info(f"Membership created with ID: {membership.id}, State: {membership.state}")
                
                # Respect the plan's activation policy
                membership_vals = {
                    'payment_transaction_id': transaction.id,
                    'payment_reference': transaction.reference,
                }
                
                if plan.activation_policy == 'immediate':
                    membership_vals['state'] = 'active'
                    membership_vals['activation_date'] = fields.Date.today()
                elif plan.activation_policy == 'first_attendance':
                    membership_vals['state'] = 'pending'  # Will be activated on first event registration
                elif plan.activation_policy == 'manual':
                    membership_vals['state'] = 'pending'  # Requires manual activation
                
                membership.write(membership_vals)
                _logger.info(f"Membership updated - State: {membership.state}, Activation Date: {membership.activation_date}")
                
                membership.message_post(
                    body=_('Payment successful via %s. Transaction: %s. Membership created and activated.') % (transaction.provider_id.name, transaction.reference)
                )
                _logger.info(f"Membership message posted")
            
            # Clear session data
            request.session.pop('payment_transaction_id', None)
            request.session.pop('pending_membership', None)
            request.session.pop('wechat_pending_membership', None)
            
            _logger.info(f"WeChat payment successful. Membership created with ID: {membership.id}")
            _logger.info(f"Final membership details - ID: {membership.id}, State: {membership.state}, Partner: {membership.partner_id.name}")
            
            # Redirect to membership success page with membership_id
            redirect_url = '/memberships/success?membership_id=%s' % membership.id
            _logger.info(f"Redirecting to: {redirect_url}")
            return request.redirect(redirect_url)
            
        except Exception as e:
            _logger.error(f"Failed to handle WeChat membership success: {str(e)}", exc_info=True)
            _logger.error(f"Exception type: {type(e).__name__}")
            _logger.error(f"Session data before cleanup: {dict(request.session)}")
            # Clear session data on error
            request.session.pop('wechat_pending_membership', None)
            request.session.pop('pending_membership', None)
            return request.redirect('/memberships/payment/failed?error=processing_failed')
    
    @http.route(['/memberships/payment/failed'], type='http', auth="public", website=True)
    def membership_payment_failed(self, **post):
        """Display payment failed page"""
        # Check if user is logged in (public user means not logged in)
        if request.env.user.id == request.env.ref('base.public_user').id:
            return request.redirect('/web/login?redirect=' + request.httprequest.url)
        
        # Get error message from URL parameter
        error_message = post.get('error', '')
        
        # Map error codes to user-friendly messages
        error_messages = {
            'session_expired': 'Your payment session has expired. Please try again.',
            'transaction_not_found': 'Payment transaction not found. Please contact support.',
            'payment_cancelled': 'Payment was cancelled. No membership was created.',
            'payment_failed': 'Payment failed. No membership was created.',
            'gateway_unavailable': 'Payment gateway is currently unavailable. Please try again later.',
            'callback_failed': 'Payment processing failed. Please contact support.',
        }
        
        user_message = error_messages.get(error_message, 'Payment failed. Please try again.')
        
        values = {
            'error_message': user_message,
            'error_code': error_message,
        }
        
        return request.render('popcorn.membership_payment_failed_page', values)
    
    def _create_upgrade_membership(self, plan, partner, upgrade_details):
        """Upgrade an existing membership to a new plan"""
        membership_id = upgrade_details.get('membership_id')
        upgrade_price = upgrade_details.get('upgrade_price', 0)
        
        # Get the original membership
        original_membership = request.env['popcorn.membership'].browse(int(membership_id))
        
        # Store original plan name for logging
        original_plan_name = original_membership.membership_plan_id.name
        
        # Update the existing membership with the new plan and pricing
        upgrade_vals = {
            'membership_plan_id': plan.id,
            'purchase_price_paid': upgrade_price,
            'price_tier': 'first_timer' if original_membership.upgrade_discount_allowed else 'normal',
            'purchase_channel': 'online',  # Upgrades are processed through online checkout
            'upgrade_discount_allowed': original_membership.upgrade_discount_allowed,
        }
        
        # Update the existing membership
        original_membership.write(upgrade_vals)
        
        # Log the upgrade
        original_membership.message_post(
            body=_('Upgraded from %s to %s. Upgrade price: %s') % (
                original_plan_name,
                plan.name,
                upgrade_price
            )
        )
        
        return original_membership
    
    def _create_membership_from_plan(self, plan, partner, purchase_channel='online', price_tier=None, upgrade_discount_allowed=False, first_timer_customer=False, payment_transaction_id=None, payment_reference=None, customer_signature=None, applied_discount=None):
        """Create a membership directly from a plan (bypassing sales orders)"""
        # Determine price tier if not provided
        if price_tier is None:
            price_tier = 'first_timer'
            existing_memberships = request.env['popcorn.membership'].search([
                ('partner_id', '=', partner.id),
                ('state', 'in', ['active', 'frozen'])
            ], limit=1)
            
            if existing_memberships:
                price_tier = 'normal'
        
        # Determine purchase price
        if price_tier == 'first_timer' and plan.price_first_timer > 0:
            purchase_price = plan.price_first_timer
        else:
            purchase_price = plan.price_normal
        
        # Get best discount for this plan and customer (including extra days)
        if applied_discount:
            # Use the applied discount
            best_price = applied_discount.get_discounted_price(plan, purchase_price, partner)
            best_discount = applied_discount
            extra_days = applied_discount.get_extra_days(plan, partner)
        else:
            # Get best discount for this plan and customer (including extra days)
            best_price, best_discount, extra_days = plan.get_best_discount_with_extra_days(partner)
        
        # Create membership values
        membership_vals = {
            'partner_id': partner.id,
            'membership_plan_id': plan.id,
            'state': 'pending',
            'purchase_price_paid': best_price,
            'price_tier': 'discount' if best_discount else price_tier,
            'purchase_channel': purchase_channel,
            'upgrade_discount_allowed': upgrade_discount_allowed,
            'first_timer_customer': first_timer_customer,
            'applied_discount_id': best_discount.id if best_discount else False,
            'extra_days_extension': extra_days,
        }
        
        # Add payment information if provided
        if payment_transaction_id:
            membership_vals['payment_transaction_id'] = payment_transaction_id
        if payment_reference:
            membership_vals['payment_reference'] = payment_reference
        
        # Set activation date based on plan policy
        if plan.activation_policy == 'immediate':
            membership_vals['activation_date'] = fields.Date.today()
            membership_vals['state'] = 'active'
        elif plan.activation_policy == 'first_attendance':
            # Don't set activation_date yet - it will be set when first event is booked
            membership_vals['state'] = 'pending'
        elif plan.activation_policy == 'manual':
            # Don't set activation_date - requires manual activation
            membership_vals['state'] = 'pending'
        
        # Create the membership
        membership = request.env['popcorn.membership'].create(membership_vals)
        
        # Create discount usage record if discount was applied
        if best_discount:
            request.env['popcorn.discount.usage'].create_usage_record(
                discount_id=best_discount.id,
                partner_id=partner.id,
                original_price=purchase_price,
                discounted_price=best_price,
                currency_id=plan.currency_id.id,
                membership_plan_id=plan.id,
                membership_id=membership.id,
                extra_days=extra_days
            )
        
        # Increment discount usage if a discount was applied
        if best_discount:
            best_discount.action_increment_usage()
        
        # Create contract with signature if provided
        if customer_signature:
            contract_vals = {
                'membership_id': membership.id,
                'contract_type': 'standard',
                'state': 'draft',
                'customer_signature': customer_signature,
                'customer_signature_date': fields.Datetime.now(),
                'signed_by_customer': True,
            }
            contract = request.env['popcorn.contract'].sudo().create(contract_vals)
            membership.write({'contract_id': contract.id})
            membership.message_post(body=_('Contract created and signed by customer during checkout'))
        
        # Log the creation
        membership.message_post(
            body=_('Membership created directly from plan %s') % plan.name
        )
        
        if plan.activation_policy == 'immediate':
            membership.message_post(
                body=_('Membership automatically activated upon purchase')
            )
        elif plan.activation_policy == 'first_attendance':
            membership.message_post(
                body=_('Membership will be activated upon first event attendance')
            )
        elif plan.activation_policy == 'manual':
            membership.message_post(
                body=_('Membership requires manual activation by staff')
            )
        
        return membership
    
    def _handle_event_purchase_redirect(self, transaction_id_param):
        """Handle WeChat payment success redirect for event purchases"""
        try:
            _logger.info(f"=== _handle_event_purchase_redirect called ===")
            _logger.info(f"Transaction ID: {transaction_id_param}")
            _logger.info(f"Session keys: {list(request.session.keys())}")
            
            # Get pending event purchase data from session (try both keys)
            pending_event_purchase = request.session.get('wechat_pending_event_purchase')
            _logger.info(f"WeChat pending event purchase: {pending_event_purchase}")
            
            if not pending_event_purchase:
                _logger.warning("No WeChat pending event purchase found, trying regular event purchase details")
                pending_event_purchase = request.session.get('event_purchase_details')
                _logger.info(f"Regular event purchase details: {pending_event_purchase}")
                
            if not pending_event_purchase:
                _logger.error("No pending event purchase found in session (neither WeChat nor regular)")
                _logger.error(f"Session contents: {dict(request.session)}")
                return request.redirect('/event?error=session_expired')
            
            # Get the transaction
            transaction = None
            _logger.info(f"Looking for transaction with ID/reference: {transaction_id_param}")
            
            # First try as reference (since our transaction IDs are references like EVENT-27519-11-1758453437)
            transaction = request.env['payment.transaction'].sudo().search([
                ('reference', '=', transaction_id_param)
            ], limit=1)
            _logger.info(f"Found by reference: {transaction.exists() if transaction else False}")
            
            # If not found as reference, try as integer ID
            if not transaction or not transaction.exists():
                try:
                    _logger.info(f"Trying as integer ID: {transaction_id_param}")
                    transaction = request.env['payment.transaction'].sudo().browse(int(transaction_id_param))
                    _logger.info(f"Tried as integer ID, found: {transaction.exists() if transaction else False}")
                except (ValueError, TypeError) as e:
                    _logger.info(f"Failed to parse as integer ID: {e}")
                    pass
            
            if not transaction or not transaction.exists():
                _logger.error(f"WeChat transaction {transaction_id_param} not found")
                # Let's also search without provider_code filter for debugging
                all_transactions = request.env['payment.transaction'].sudo().search([
                    ('reference', '=', transaction_id_param)
                ])
                _logger.error(f"Found {len(all_transactions)} transactions with reference {transaction_id_param}")
                for t in all_transactions:
                    _logger.error(f"  Transaction ID: {t.id}, Provider: {t.provider_id.name if t.provider_id else 'None'}, Code: {t.provider_code}")
                return request.redirect('/event?error=transaction_not_found')
            
            _logger.info(f"Found transaction: {transaction.id}, State: {transaction.state}, Provider: {transaction.provider_id.name if transaction.provider_id else 'None'}")
            
            # Mark transaction as done (WeChat payment was successful)
            transaction.write({'state': 'done'})
            
            # Create event registration now
            _logger.info(f"Creating event registration with data: {pending_event_purchase}")
            event = request.env['event.event'].sudo().browse(pending_event_purchase['event_id'])
            partner = request.env['res.partner'].sudo().browse(pending_event_purchase['partner_id'])
            
            _logger.info(f"Event exists: {event.exists()}, Partner exists: {partner.exists()}")
            _logger.info(f"Event name: {event.name if event.exists() else 'N/A'}, Partner name: {partner.name if partner.exists() else 'N/A'}")
            
            if not event.exists() or not partner.exists():
                _logger.error(f"Invalid event or partner - Event ID: {pending_event_purchase.get('event_id')}, Partner ID: {pending_event_purchase.get('partner_id')}")
                return request.redirect('/event?error=invalid_data')
            
            # Deduct popcorn money if used
            if pending_event_purchase.get('use_popcorn_money') and pending_event_purchase.get('popcorn_money_to_use', 0) > 0:
                partner.deduct_popcorn_money(pending_event_purchase['popcorn_money_to_use'], f'Event registration: {event.name}')
            
            # CRITICAL: Apply discount if used (must mark discount as used to prevent reuse)
            applied_discount_id = pending_event_purchase.get('applied_discount_id')
            applied_discount = None
            if applied_discount_id:
                applied_discount = request.env['popcorn.discount'].sudo().browse(applied_discount_id)
                if applied_discount.exists():
                    _logger.info(f"Applying discount: {applied_discount.code}")
                    _logger.info(f"Discount usage count before: {applied_discount.usage_count}")
                    applied_discount.action_increment_usage()
                    _logger.info(f"Discount usage count after: {applied_discount.usage_count}")
                    
                    # Calculate discounted price (pass None for membership_plan since this is an event)
                    discounted_price = applied_discount.get_discounted_price(None, event.event_price, partner)
                    
                    # Create usage record
                    request.env['popcorn.discount.usage'].sudo().create({
                        'discount_id': applied_discount.id,
                        'partner_id': partner.id,
                        'original_price': event.event_price,
                        'discounted_price': discounted_price,
                        'currency_id': event.currency_id.id if event.currency_id else request.env.company.currency_id.id,
                        'event_id': event.id,
                        'extra_days': applied_discount.get_extra_days(None, partner)
                    })
                    _logger.info(f"✅ Discount usage record created for WeChat event payment")
            
            # Create the event registration (using only standard fields)
            _logger.info("Creating event registration with vals:")
            registration_vals = {
                'event_id': event.id,
                'partner_id': partner.id,
                'name': partner.name,
                'email': partner.email,
                'phone': partner.phone,
                'state': 'open',
                'payment_amount': pending_event_purchase.get('event_price', 0),
                'payment_transaction_id': transaction.id,
            }
            _logger.info(f"Registration vals: {registration_vals}")
            
            registration = request.env['event.registration'].sudo().create(registration_vals)
            _logger.info(f"Event registration created with ID: {registration.id}, State: {registration.state}, Payment Transaction: {transaction.id}")
            
            payment_message = _('Direct purchase registration for event: %s. Price: %s. Payment successful via %s. Transaction: %s. Event registration created and activated.') % (event.name, pending_event_purchase['event_price'], transaction.provider_id.name, transaction.reference)
            if pending_event_purchase.get('use_popcorn_money') and pending_event_purchase.get('popcorn_money_to_use', 0) > 0:
                payment_message += _('. Popcorn money used: %s%s. Remaining: %s%s') % (event.currency_id.symbol, pending_event_purchase['popcorn_money_to_use'], event.currency_id.symbol, pending_event_purchase.get('remaining_amount', 0))
            
            registration.message_post(body=payment_message)
            _logger.info(f"Event registration message posted")
            
            # Clear session data
            request.session.pop('payment_transaction_id', None)
            request.session.pop('event_purchase_details', None)
            request.session.pop('wechat_pending_event_purchase', None)
            
            _logger.info(f"WeChat event payment successful. Registration created with ID: {registration.id}")
            _logger.info(f"Final registration details - ID: {registration.id}, State: {registration.state}, Partner: {registration.partner_id.name}")
            
            # Redirect to event success page (same pattern as membership success)
            redirect_url = f'/popcorn/event/{event.id}/purchase/success?registration_id={registration.id}'
            _logger.info(f"Redirecting to event success page: {redirect_url}")
            return request.redirect(redirect_url)
            
        except Exception as e:
            _logger.error(f"Failed to handle event purchase redirect: {str(e)}", exc_info=True)
            # Clear session data on error
            request.session.pop('wechat_pending_event_purchase', None)
            request.session.pop('event_purchase_details', None)
            return request.redirect('/event?error=processing_failed')

    def _handle_event_purchase(self, plan, partner, payment_transaction_id=None, payment_reference=None):
        """Handle event purchase instead of membership creation"""
        # Get event purchase details from session
        event_purchase_details = request.session.get('event_purchase_details', {})
        
        if not event_purchase_details:
            _logger.error("No event purchase details found in session")
            return None
        
        # Get the event
        event = request.env['event.event'].sudo().browse(event_purchase_details['event_id'])
        if not event.exists():
            _logger.error(f"Event {event_purchase_details['event_id']} not found")
            return None
        
        # Deduct popcorn money if used
        if event_purchase_details.get('use_popcorn_money') and event_purchase_details.get('popcorn_money_to_use', 0) > 0:
            partner.deduct_popcorn_money(event_purchase_details['popcorn_money_to_use'], f'Event registration: {event.name}')
        
        # Create the event registration (using only standard fields)
        registration_vals = {
            'event_id': event.id,
            'partner_id': partner.id,
            'name': partner.name,
            'email': partner.email,
            'phone': partner.phone,
            'state': 'open',
        }
        
        # Create the registration
        registration = request.env['event.registration'].sudo().create(registration_vals)
        
        # Log the direct purchase
        registration.message_post(
            body=_('Direct purchase registration for club: %s. Price: %s%s') % (event.name, event.currency_id.symbol, event.event_price)
        )
        
        # Clear the session data
        request.session.pop('event_purchase_details', None)
        
        _logger.info(f"Event registration created with ID: {registration.id}")
        return registration

