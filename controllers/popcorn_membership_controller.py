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
        is_first_timer = request.env['popcorn.membership']._is_first_timer_customer(request.env.user.partner_id.id)
        
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
        is_first_timer = request.env['popcorn.membership']._is_first_timer_customer(request.env.user.partner_id.id)
        
        values = {
            'plan': plan,
            'is_upgrade': is_upgrade,
            'upgrade_details': upgrade_details,
            'is_first_timer': is_first_timer,
        }
        
        return request.render('popcorn.membership_checkout_page', values)
    
    @http.route(['/memberships/<model("popcorn.membership.plan"):plan>/process_checkout'], type='http', auth="public", website=True, methods=['POST'])
    def process_membership_checkout(self, plan, **post):
        """Process the checkout form and create membership"""
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
            
            # Get payment method
            payment_method_id = int(post.get('payment_method_id'))
            payment_method = request.env['payment.method'].browse(payment_method_id)
            
            # Validate payment method exists
            if not payment_method.exists():
                return request.redirect('/memberships/%s/checkout?error=invalid_payment_method' % plan.id)
            
            # Check if this is an upgrade
            upgrade_details = request.session.get('upgrade_details', {})
            is_upgrade = upgrade_details.get('is_upgrade', False)
            
            if is_upgrade:
                # Handle upgrade
                membership = self._create_upgrade_membership(plan, partner, upgrade_details)
                
                # Clear upgrade details from session
                request.session.pop('upgrade_details', None)
                
                # Log the upgrade
                membership.message_post(
                    body=_('Membership upgraded through checkout page. Payment method: %s') % payment_method.name
                )
                
                # Redirect to upgrade success page
                return request.redirect('/my/cards/upgrade/success?membership_id=%s' % membership.id)
            else:
                # Create regular membership
                membership = self._create_membership_from_plan(plan, partner)
                
                # Log the purchase
                membership.message_post(
                    body=_('Membership purchased through checkout page. Payment method: %s') % payment_method.name
                )
                
                # Redirect to success page
                return request.redirect('/memberships/success?membership_id=%s' % membership.id)
            
        except Exception as e:
            _logger.error(f"Failed to process checkout: {str(e)}")
            return request.redirect('/memberships/%s/checkout?error=processing_failed' % plan.id)
    
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

