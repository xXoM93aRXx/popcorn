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
        
        values = {
            'membership_plans': membership_plans,
            'error_message': error_message,
            'is_first_timer': is_first_timer,
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
        
        values = {
            'plan': plan,
            'is_upgrade': is_upgrade,
            'upgrade_details': upgrade_details,
            'is_first_timer': is_first_timer,
        }
        
        return request.render('popcorn.membership_checkout_page', values)
    
    @http.route(['/memberships/<model("popcorn.membership.plan"):plan>/process_checkout'], type='http', auth="public", website=True, methods=['POST'])
    def process_membership_checkout(self, plan, **post):
        """Process the checkout form and initiate payment transaction"""
        # Check if user is logged in (public user means not logged in)
        if request.env.user.id == request.env.ref('base.public_user').id:
            return request.redirect('/web/login?redirect=' + request.httprequest.url)
        
        try:
            # Validate form data
            if not post.get('name') or not post.get('phone') or not post.get('payment_method_id'):
                return request.redirect('/memberships/%s/checkout?error=missing_fields' % plan.id)
            
            if not post.get('terms_accepted'):
                return request.redirect('/memberships/%s/checkout?error=terms_not_accepted' % plan.id)
            
            # Update or create partner information
            partner = request.env.user.partner_id
            partner_vals = {
                'name': post.get('name'),
                'phone': post.get('phone'),
            }
            
            partner.write(partner_vals)
            
            # Get payment method/provider ID
            payment_method_id = post.get('payment_method_id')
            
            # Check if it's a manual payment (fallback)
            if payment_method_id == 'manual':
                # For manual payment, create membership directly but mark as pending payment
                membership = self._create_membership_from_plan(plan, partner)
                membership.write({'state': 'pending_payment'})
                
                # Log the manual payment request
                membership.message_post(
                    body=_('Manual payment requested. Payment method: Manual')
                )
                
                # Redirect to success page with pending payment status
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
            
            # Check if this is an upgrade
            upgrade_details = request.session.get('upgrade_details', {})
            is_upgrade = upgrade_details.get('is_upgrade', False)
            
            # Calculate the amount to charge
            if is_upgrade:
                amount = upgrade_details.get('upgrade_price', 0)
            else:
                # Determine price based on first-timer status
                if partner.is_first_timer and plan.price_first_timer > 0:
                    amount = plan.price_first_timer
                else:
                    amount = plan.price_normal
            
            # Store membership details in session for after payment
            request.session['pending_membership'] = {
                'plan_id': plan.id,
                'partner_id': partner.id,
                'amount': amount,
                'payment_provider_id': payment_provider.id,
                'payment_provider_name': payment_provider.name,
                'is_upgrade': is_upgrade,
                'upgrade_details': upgrade_details if is_upgrade else None,
            }
            
            # Handle different payment methods based on provider name
            if payment_provider.name.lower() in ['bank transfer', 'bank_transfer']:
                # For bank transfer, create membership immediately but mark as pending payment
                membership = self._create_membership_from_plan(plan, partner)
                membership.write({'state': 'pending_payment'})
                
                # Log the bank transfer payment request
                membership.message_post(
                    body=_('Bank transfer payment requested. Payment method: %s') % payment_provider.name
                )
                
                # Redirect to success page with pending payment status
                return request.redirect('/memberships/success?membership_id=%s&payment_pending=true' % membership.id)
            else:
                # For online payments (Stripe/PayPal), create payment transaction and redirect to gateway
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
                
                # Store transaction ID in session for callback
                request.session['payment_transaction_id'] = payment_transaction.id
                # pending_membership is already stored in session above
                
                # Try to get payment link for all providers (including WeChat)
                try:
                    payment_link = payment_transaction._get_specific_rendering_values(None)
                    if payment_link and 'action_url' in payment_link:
                        _logger.info(f"Redirecting to payment gateway: {payment_link['action_url']}")
                        return request.redirect(payment_link['action_url'])
                except Exception as e:
                    _logger.warning(f"Failed to get payment link: {str(e)}")
                
                # Fallback: create membership directly if no payment link available
                _logger.warning("No payment link available, creating membership directly")
                membership = self._create_membership_from_plan(plan, partner)
                membership.message_post(
                    body=_('Membership purchased through %s payment. Amount: %s') % (payment_provider.name, amount)
                )
                request.session.pop('pending_membership', None)
                return request.redirect('/memberships/success?membership_id=%s' % membership.id)
            
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
                    membership = self._create_membership_from_plan(plan, partner)
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
            # Get transaction ID from session
            transaction_id = request.session.get('payment_transaction_id')
            pending_membership = request.session.get('pending_membership')
            
            if not transaction_id or not pending_membership:
                _logger.error("No transaction ID or pending membership found in session")
                return request.redirect('/memberships?error=session_expired')
            
            # Get the transaction
            transaction = request.env['payment.transaction'].sudo().browse(transaction_id)
            
            if not transaction.exists():
                _logger.error(f"Transaction {transaction_id} not found")
                return request.redirect('/memberships?error=transaction_not_found')
            
            # Check payment status
            if transaction.state == 'done':
                # Payment successful - create membership
                plan = request.env['popcorn.membership.plan'].browse(pending_membership['plan_id'])
                partner = request.env['res.partner'].browse(pending_membership['partner_id'])
                
                if pending_membership['is_upgrade']:
                    membership = self._create_upgrade_membership(plan, partner, pending_membership['upgrade_details'])
                    membership.message_post(
                        body=_('Membership upgraded through %s payment. Transaction: %s') % (transaction.provider_id.name, transaction.reference)
                    )
                    redirect_url = '/my/cards/upgrade/success?membership_id=%s' % membership.id
                else:
                    membership = self._create_membership_from_plan(plan, partner)
                    membership.message_post(
                        body=_('Membership purchased through %s payment. Transaction: %s') % (transaction.provider_id.name, transaction.reference)
                    )
                    redirect_url = '/memberships/success?membership_id=%s' % membership.id
                
                # Clear session data
                request.session.pop('payment_transaction_id', None)
                request.session.pop('pending_membership', None)
                request.session.pop('upgrade_details', None)
                
                _logger.info(f"Payment successful. Membership created with ID: {membership.id}")
                return request.redirect(redirect_url)
                
            elif transaction.state == 'cancel':
                # Payment cancelled
                _logger.info(f"Payment cancelled for transaction {transaction_id}")
                request.session.pop('payment_transaction_id', None)
                request.session.pop('pending_membership', None)
                return request.redirect('/memberships?error=payment_cancelled')
                
            else:
                # Payment pending or failed
                _logger.warning(f"Payment not completed for transaction {transaction_id}. State: {transaction.state}")
                return request.redirect('/memberships?error=payment_pending')
                
        except Exception as e:
            _logger.error(f"Failed to handle payment callback: {str(e)}")
            return request.redirect('/memberships?error=callback_failed')

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
        
        membership_id = post.get('membership_id')
        membership = None
        
        if membership_id:
            membership = request.env['popcorn.membership'].browse(int(membership_id))
        
        values = {
            'membership': membership,
        }
        
        return request.render('popcorn.membership_success_page', values)
    
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
    
    def _create_membership_from_plan(self, plan, partner):
        """Create a membership directly from a plan (bypassing sales orders)"""
        # Determine price tier
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
        
        # Create membership values
        membership_vals = {
            'partner_id': partner.id,
            'membership_plan_id': plan.id,
            'state': 'pending',
            'purchase_price_paid': purchase_price,
            'price_tier': price_tier,
            'purchase_channel': 'online',
        }
        
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

