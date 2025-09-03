# -*- coding: utf-8 -*-

from odoo import http, fields, _
from odoo.http import request
import json
import werkzeug
import logging
from werkzeug.utils import redirect
from werkzeug.urls import url_quote
from odoo.addons.portal.controllers.portal import CustomerPortal

_logger = logging.getLogger(__name__)


class PopcornEventController(http.Controller):
    """Controller for Popcorn Club membership-gated event registration"""
    
    def _check_membership_access(self, event):
        """
        Check if current user has access to register for this event.
        Returns (has_access, redirect_url, error_message)
        """
        # Check if user is logged in (public user means not logged in)
        if request.env.user.id == request.env.ref('base.public_user').id:
            return False, None, 'Please log in to register for events'
        
        # Get the partner for the current user
        partner = request.env.user.sudo().partner_id
        if not partner:
            return False, None, 'User profile not found'
        
        # Check if user has any active memberships or pending memberships with first_attendance policy
        active_memberships = request.env['popcorn.membership'].sudo().search([
            ('partner_id', '=', partner.id),
            ('state', 'in', ['active', 'frozen'])
        ])
        
        # Also include pending memberships with first_attendance activation policy
        pending_first_attendance = request.env['popcorn.membership'].sudo().search([
            ('partner_id', '=', partner.id),
            ('state', '=', 'pending'),
            ('membership_plan_id.activation_policy', '=', 'first_attendance')
        ])
        
        # Combine both sets
        all_usable_memberships = active_memberships | pending_first_attendance
        
        if not all_usable_memberships:
            return False, '/memberships', 'You need an active membership to register for events'
        
        # Check if any membership allows this event type
        event_club_type = self._get_event_club_type(event)
        if not event_club_type:
            return True, None, None  # No club type restriction, allow access
        
        # Check if any membership allows this club type
        for membership in all_usable_memberships:
            if self._can_membership_attend_event(membership, event_club_type):
                return True, None, None
        
        return False, '/memberships', f'Your membership does not allow {event_club_type.replace("_", " ").title()} events'
    
    def _get_event_club_type(self, event):
        """Determine the club type for an event based on its tags"""
        if not event.tag_ids:
            return False
        
        # Look for the tag with category "Type" to determine club type
        type_tag = event.tag_ids.sudo().filtered(
            lambda tag: tag.category_id.name == 'Type'
        )[:1]  # Safely grab the first record
        
        if type_tag:
            tag_name = type_tag.name.lower()
            if 'offline' in tag_name:
                return 'regular_offline'
            elif 'online' in tag_name:
                return 'regular_online'
            elif 'sp' in tag_name or 'special' in tag_name:
                return 'spclub'
        
        # Fallback: determine from event properties
        if hasattr(event, 'is_online_event') and event.is_online_event:
            return 'regular_online'
        
        return 'regular_offline'  # Default to offline
    
    def _can_membership_attend_event(self, membership, club_type):
        """Check if a membership can attend a specific club type event"""
        if not membership or not club_type:
            return False
        
        # First check if membership has sufficient quota
        if membership.plan_quota_mode == 'unlimited':
            # For unlimited, only check club type permissions
            pass
        elif membership.plan_quota_mode == 'bucket_counts':
            if club_type == 'regular_offline' and membership.remaining_offline < 1:
                return False
            elif club_type == 'regular_online' and membership.remaining_online < 1:
                return False
            elif club_type == 'spclub' and membership.remaining_sp < 1:
                return False
        elif membership.plan_quota_mode == 'points':
            # Calculate points needed for this club type
            plan = membership.membership_plan_id
            points_needed = (plan.points_per_offline if club_type == 'regular_offline' 
                           else plan.points_per_online if club_type == 'regular_online' 
                           else plan.points_per_sp)
            
            if membership.points_remaining < points_needed:
                return False
        
        # If quota check passes, then check club type permissions
        if club_type == 'regular_offline' and not membership.plan_allowed_regular_offline:
            return False
        elif club_type == 'regular_online' and not membership.plan_allowed_regular_online:
            return False
        elif club_type == 'spclub' and not membership.plan_allowed_spclub:
            return False
        
        return True
    
    def _get_best_membership_for_event(self, partner, event):
        """Find the best available membership for a specific event"""
        if not partner or not event:
            return False
        
        event_club_type = self._get_event_club_type(event)
        if not event_club_type:
            # If no specific club type is determined, default to regular_offline
            event_club_type = 'regular_offline'
        
        # Get all active memberships and pending memberships with first_attendance policy
        active_memberships = request.env['popcorn.membership'].sudo().search([
            ('partner_id', '=', partner.id),
            ('state', 'in', ['active', 'frozen'])
        ])
        
        pending_first_attendance = request.env['popcorn.membership'].sudo().search([
            ('partner_id', '=', partner.id),
            ('state', '=', 'pending'),
            ('membership_plan_id.activation_policy', '=', 'first_attendance')
        ])
        
        memberships = active_memberships | pending_first_attendance
        
        if not memberships:
            return False
        
        # Filter memberships that allow this club type and have sufficient quota
        compatible_memberships = []
        for membership in memberships:
            if self._can_membership_attend_event(membership, event_club_type):
                compatible_memberships.append(membership)
        
        if not compatible_memberships:
            return False
        
        # Sort by priority: unlimited > points > bucket_counts
        # For same type, prefer longer duration
        def get_quota_mode_priority(quota_mode):
            priority_map = {'unlimited': 3, 'points': 2, 'bucket_counts': 1}
            return priority_map.get(quota_mode, 0)
        
        compatible_memberships.sort(key=lambda m: (
            get_quota_mode_priority(m.plan_quota_mode),
            m.plan_duration_days or 0
        ), reverse=True)
        
        return compatible_memberships[0] if compatible_memberships else False
    
    def _get_consumption_text(self, membership, club_type):
        """Get human-readable text for membership consumption"""
        if membership.plan_quota_mode == 'unlimited':
            return "Unlimited membership - no consumption"
        elif membership.plan_quota_mode == 'bucket_counts':
            if club_type == 'regular_offline':
                return f"1 offline session consumed (remaining: {membership.remaining_offline})"
    
    def _is_event_in_freeze_period(self, event, partner):
        """Check if an event falls within any of the user's freeze periods"""
        if not partner or not event:
            return False, None
        
        # Get all frozen memberships for this partner
        frozen_memberships = request.env['popcorn.membership'].sudo().search([
            ('partner_id', '=', partner.id),
            ('freeze_active', '=', True)
        ])
        
        if not frozen_memberships:
            return False, None
        
        event_date = event.date_begin.date()
        
        # Check if event date falls within any freeze period
        for membership in frozen_memberships:
            if membership.freeze_start and membership.freeze_end:
                if membership.freeze_start <= event_date < membership.freeze_end:
                    return True, membership
        
        return False, None
    
    def _get_consumption_text(self, membership, club_type):
        """Get human-readable text for membership consumption"""
        if membership.plan_quota_mode == 'unlimited':
            return "Unlimited membership - no consumption"
        elif membership.plan_quota_mode == 'bucket_counts':
            if club_type == 'regular_offline':
                return f"1 offline session consumed (remaining: {membership.remaining_offline})"
            elif club_type == 'regular_online':
                return f"1 online session consumed (remaining: {membership.remaining_online})"
            elif club_type == 'spclub':
                return f"1 special club session consumed (remaining: {membership.remaining_sp})"
        elif membership.plan_quota_mode == 'points':
            plan = membership.membership_plan_id
            points_needed = (plan.points_per_offline if club_type == 'regular_offline' 
                           else plan.points_per_online if club_type == 'regular_online' 
                           else plan.points_per_sp)
            return f"{points_needed} points consumed (remaining: {membership.points_remaining})"
        return "Unknown consumption type"
    
    @http.route(['/membership'], type='http', auth="public", website=True)
    def membership_required(self, **kwargs):
        """Display membership required page"""
        # Clear any error messages to prevent loops
        if 'error_message' in request.session:
            del request.session['error_message']
        
        return request.render('popcorn.membership_required_page')
    
    @http.route(['/popcorn/event/<model("event.event"):event>/register'], type='http', auth="public", website=True)
    def event_register(self, event, **kwargs):
        """Override event registration page to check membership access"""
        # Check membership access
        has_access, redirect_url, error_message = self._check_membership_access(event)
        
        if not has_access:
            # Use Odoo's redirect mechanism with proper redirect URL
            if 'log in' in error_message.lower():
                # Redirect to login with return URL pointing to the event page, not registration
                event_url = f'/event/{event.id}'
                return redirect('/web/login?redirect=' + event_url)
            elif redirect_url:
                # Include error message in redirect URL
                error_param = url_quote(error_message) if error_message else ''
                return redirect(redirect_url + '?error=' + error_param)
            else:
                # Fallback redirect to memberships for membership with error message
                error_param = url_quote(error_message) if error_message else ''
                return redirect('/memberships?error=' + error_param)
        
        # User has access, proceed with normal registration
        values = {
            'event': event,
        }
        return request.render('popcorn.event_registration_access_page', values)
    
    @http.route(['/popcorn/event/<model("event.event"):event>/registration/new'], type='json', auth="public") 
    def event_registration_new(self, event, **kwargs):
        """Override event registration form to check membership access"""
        # Check membership access
        has_access, redirect_url, error_message = self._check_membership_access(event)
        
        if not has_access:
            if redirect_url:
                # Include error message in redirect URL
                error_param = url_quote(error_message) if error_message else ''
                return {
                    'redirect': redirect_url + '?error=' + error_param,
                    'error': error_message
                }
            else:
                # Include error message in redirect URL
                error_param = url_quote(error_message) if error_message else ''
                return {
                    'redirect': '/memberships?error=' + error_param,
                    'error': error_message
                }
        
        # User has access, proceed with normal registration form
        # Since we're not inheriting, we'll need to handle this differently
        # For now, return a simple response
        return {'status': 'success', 'message': 'Registration form available'}
    
    @http.route(['/popcorn/event/<model("event.event"):event>/registration/confirm'], type='http', auth="public", website=True, methods=['POST'])
    def event_registration_confirm(self, event, **kwargs):
        """Override event registration confirmation to auto-create attendee from membership"""
        # Check membership access
        has_access, redirect_url, error_message = self._check_membership_access(event)
        
        if not has_access:
            # Use Odoo's redirect mechanism with proper redirect URL
            if 'log in' in error_message.lower():
                # Redirect to login with return URL pointing to the event page, not registration
                event_url = f'/event/{event.id}'
                return redirect('/web/login?redirect=' + event_url)
            elif redirect_url:
                # Include error message in redirect URL
                error_param = url_quote(error_message) if error_message else ''
                return redirect(redirect_url + '?error=' + error_param)
            else:
                # Fallback redirect to memberships for membership with error message
                error_param = url_quote(error_message) if error_message else ''
                return redirect('/memberships?error=' + error_param)
        
        # Get the partner for the current user
        partner = request.env.user.sudo().partner_id
        
        # Find the best membership for this event
        best_membership = self._get_best_membership_for_event(partner, event)
        
        if not best_membership:
            # Check if user has memberships but they don't have sufficient quota
            event_club_type = self._get_event_club_type(event)
            if not event_club_type:
                event_club_type = 'regular_offline'  # Default fallback
            
            # Get all user's memberships
            all_memberships = request.env['popcorn.membership'].sudo().search([
                ('partner_id', '=', partner.id),
                ('state', 'in', ['active', 'frozen', 'pending'])
            ])
            
            # Debug: Log what memberships we found
            print(f"Found {len(all_memberships)} memberships for partner {partner.id}")
            for membership in all_memberships:
                print(f"Membership {membership.id}: {membership.membership_plan_id.name}, state={membership.state}")
            
            if all_memberships:
                # First check quota (points/sessions) for all memberships
                quota_issue_found = False
                for membership in all_memberships:
                    if membership.plan_quota_mode == 'points':
                        plan = membership.membership_plan_id
                        points_needed = (plan.points_per_offline if event_club_type == 'regular_offline' 
                                       else plan.points_per_online if event_club_type == 'regular_online' 
                                       else plan.points_per_sp)
                        if membership.points_remaining < points_needed:
                            error_message = f'Insufficient points. You need {points_needed} points but have {membership.points_remaining} remaining'
                            quota_issue_found = True
                            break
                    elif membership.plan_quota_mode == 'bucket_counts':
                        if event_club_type == 'regular_offline' and membership.remaining_offline < 1:
                            error_message = f'No offline sessions remaining. You have {membership.remaining_offline} offline sessions left'
                            quota_issue_found = True
                            break
                        elif event_club_type == 'regular_online' and membership.remaining_online < 1:
                            error_message = f'No online sessions remaining. You have {membership.remaining_online} online sessions left'
                            quota_issue_found = True
                            break
                        elif event_club_type == 'spclub' and membership.remaining_sp < 1:
                            error_message = f'No special club sessions remaining. You have {membership.remaining_sp} special club sessions left'
                            quota_issue_found = True
                            break
                
                if not quota_issue_found:
                    # If quota is sufficient, then check club type permissions
                    club_type_issue_found = False
                    for membership in all_memberships:
                        allows_club_type = False
                        if event_club_type == 'regular_offline':
                            allows_club_type = membership.plan_allowed_regular_offline
                        elif event_club_type == 'regular_online':
                            allows_club_type = membership.plan_allowed_regular_online
                        elif event_club_type == 'spclub':
                            allows_club_type = membership.plan_allowed_spclub
                        
                        if allows_club_type:
                            # Found a membership that allows this club type and has sufficient quota
                            club_type_issue_found = False
                            break
                        else:
                            club_type_issue_found = True
                    
                    if club_type_issue_found:
                        error_message = f'Your membership does not allow {event_club_type.replace("_", " ").title()} events'
                    else:
                        # All checks passed but something else is wrong
                        error_message = 'Insufficient quota for this event'
            else:
                error_message = 'No suitable membership found for this event'
            
            error_param = url_quote(error_message)
            return werkzeug.utils.redirect('/memberships?error=' + error_param)
        
        # Determine event club type for consumption
        event_club_type = self._get_event_club_type(event)
        if not event_club_type:
            event_club_type = 'regular_offline'  # Default fallback
        
        # Handle membership activation for "first attendance" policy
        if best_membership.state == 'pending' and best_membership.membership_plan_id.activation_policy == 'first_attendance':
            # Set activation date to event date (not current date)
            event_date = event.date_begin.date() if event.date_begin else fields.Date.today()
            best_membership.write({
                'state': 'active',
                'activation_date': event_date
            })
            # Log the activation
            best_membership.message_post(
                body=_('Membership activated upon first attendance for event: %s') % event.name
            )
        
        # Auto-create the registration with membership details
        registration_vals = {
            'event_id': event.id,
            'partner_id': partner.id,
            'name': partner.name,
            'email': partner.email,
            'phone': partner.phone,
            'membership_id': best_membership.id,
            'consumption_state': 'pending',  # was 'consumed'
            'state': 'open'
        }
        
        # Create the registration
        registration = request.env['event.registration'].sudo().create(registration_vals)
        
        # Let the model validate quota and mark consumed atomically
        registration.sudo().action_consume_membership()
        
        # Get consumption text
        consumption_text = self._get_consumption_text(best_membership, event_club_type)
        
        # Show success page
        values = {
            'event': event,
            'partner': partner,
            'best_membership': best_membership,
            'registration': registration,
            'event_club_type': event_club_type,
            'consumption_text': consumption_text,
        }
        
        # Clear UI caches to ensure fresh data
        request.env['ir.ui.view'].clear_caches()
        
        return request.render('popcorn.event_registration_success_page', values)
    
    @http.route(['/popcorn/shop/cart/update_json'], type='json', auth="public")
    def cart_update_json(self, product_id, add_qty=1, set_qty=0, **kwargs):
        """Custom cart update for event ticket products"""
        # This route is now just for reference, the main logic is in cart_update_json_redirect
        return {'status': 'success', 'message': 'Custom cart update'}
    
    def _check_membership_access_for_product(self, product):
        """Check membership access for a specific product"""
        # Check if user is logged in (public user means not logged in)
        if request.env.user.id == request.env.ref('base.public_user').id:
            return False, '/web/login?redirect=' + request.httprequest.url, 'Please log in to purchase event tickets'
        
        # Get the partner for the current user
        partner = request.env.user.sudo().partner_id
        if not partner:
            return False, '/web/login?redirect=' + request.httprequest.url, 'User profile not found'
        
        # Check if user has any active memberships
        active_memberships = request.env['popcorn.membership'].sudo().search([
            ('partner_id', '=', partner.id),
            ('state', 'in', ['active', 'frozen'])
        ])
        
        if not active_memberships:
            return False, '/memberships', 'You need an active membership to purchase event tickets'
        
        # For now, allow purchase if user has any active membership
        # You could add more specific logic here based on the product/event type
        return True, None, None


class PopcornPortalController(CustomerPortal):
    """Portal controller for Popcorn Club specific pages"""
    
    @http.route(['/my/clubs'], type='http', auth="user", website=True)
    def portal_my_clubs(self, **kwargs):
        """Display user's registered clubs"""
        partner = request.env.user.partner_id
        
        # Get current datetime for comparison
        now = fields.Datetime.now()
        
        # Get upcoming registrations (events that haven't ended yet)
        upcoming_registrations = request.env['event.registration'].sudo().search([
            ('partner_id', '=', partner.id),
            ('event_id.date_end', '>', now),  # Event hasn't ended yet
            ('state', 'in', ['open', 'confirmed', 'done'])
        ])
        
        # Get past registrations (events that have ended)
        past_registrations = request.env['event.registration'].sudo().search([
            ('partner_id', '=', partner.id),
            ('event_id.date_end', '<=', now),  # Event has ended
            ('state', 'in', ['open', 'confirmed', 'done'])
        ])
        

        
        # Sort the registrations manually
        upcoming_registrations = upcoming_registrations.sorted(key=lambda r: r.event_id.date_begin)
        past_registrations = past_registrations.sorted(key=lambda r: r.event_id.date_begin, reverse=True)
        
        # Handle success and error messages
        success_message = None
        error_message = None
        
        if kwargs.get('success') == 'registration_cancelled':
            success_message = 'Registration has been successfully cancelled.'
        elif kwargs.get('error') == 'cancellation_failed':
            error_message = kwargs.get('message', 'Failed to cancel registration. Please try again.')
        
        values = {
            'registrations': upcoming_registrations,
            'past_registrations': past_registrations,
            'page_name': 'my_clubs',
            'current_time': now,  # For debugging
            'success_message': success_message,
            'error_message': error_message,
        }
        
        return request.render('popcorn.portal_my_clubs_page', values)
    
    @http.route(['/my/cards'], type='http', auth="user", website=True)
    def portal_my_cards(self, **kwargs):
        """Display user's membership cards"""
        partner = request.env.user.partner_id
        
        # Get active memberships (active and frozen)
        active_memberships = request.env['popcorn.membership'].sudo().search([
            ('partner_id', '=', partner.id),
            ('state', 'in', ['active', 'frozen'])
        ], order='effective_end_date asc')
        
        # Get unactivated memberships
        unactivated_memberships = request.env['popcorn.membership'].sudo().search([
            ('partner_id', '=', partner.id),
            ('state', '=', 'pending')
        ], order='create_date desc')
        
        # Get expired memberships
        expired_memberships = request.env['popcorn.membership'].sudo().search([
            ('partner_id', '=', partner.id),
            ('state', '=', 'expired')
        ], order='effective_end_date desc')
        
        # Handle error messages
        error_message = None
        success_message = None
        
        if kwargs.get('error') == 'freeze_min_days':
            error_message = 'Freeze duration must be at least the minimum required days.'
        elif kwargs.get('error') == 'freeze_max_days':
            error_message = 'Freeze duration exceeds the maximum allowed days.'
        elif kwargs.get('error') == 'invalid_freeze_days':
            error_message = 'Invalid freeze duration specified.'
        elif kwargs.get('error') == 'freeze_failed':
            error_message = 'Failed to freeze membership. Please try again.'
        elif kwargs.get('error') == 'unfreeze_failed':
            error_message = 'Failed to unfreeze membership. Please try again.'
        elif kwargs.get('error') == 'cancellation_failed':
            error_message = kwargs.get('message', 'Failed to cancel registration. Please try again.')
        elif kwargs.get('success') == 'freeze_applied':
            success_message = 'Membership has been successfully frozen.'
        elif kwargs.get('success') == 'unfreeze_applied':
            success_message = 'Membership has been successfully unfrozen.'
        elif kwargs.get('success') == 'registration_cancelled':
            success_message = 'Registration has been successfully cancelled.'
        
        values = {
            'active_memberships': active_memberships,
            'unactivated_memberships': unactivated_memberships,
            'expired_memberships': expired_memberships,
            'page_name': 'my_cards',
            'current_date': fields.Date.today(),
            'error_message': error_message,
            'success_message': success_message,
        }
        
        return request.render('popcorn.portal_your_cards_page', values)
    
    @http.route(['/my/cards/<model("popcorn.membership"):membership>/upgrade'], type='http', auth="user", website=True)
    def portal_membership_upgrade(self, membership, **kwargs):
        """Display upgrade options for a membership"""
        # Check if user owns this membership
        if membership.partner_id.id != request.env.user.partner_id.id:
            return request.redirect('/my/cards')
        
        # Get available upgrade plans
        available_plans = self._get_available_upgrade_plans(membership)
        
        # Calculate upgrade prices
        upgrade_options = []
        for plan in available_plans:
            upgrade_price = self._calculate_upgrade_price(membership, plan)
            upgrade_options.append({
                'plan': plan,
                'upgrade_price': upgrade_price,
                'original_price': plan.price_first_timer if membership.upgrade_discount_allowed else plan.price_normal,
                'savings': round((plan.price_normal - upgrade_price), 2) if membership.upgrade_discount_allowed else 0
            })
        
        values = {
            'membership': membership,
            'upgrade_options': upgrade_options,
            'page_name': 'upgrade',
            'current_date': fields.Date.today(),
        }
        
        return request.render('popcorn.portal_membership_upgrade_page', values)
    
    @http.route(['/my/cards/<model("popcorn.membership"):membership>/upgrade/process'], type='http', auth="user", website=True, methods=['POST'])
    def portal_membership_upgrade_process(self, membership, **kwargs):
        """Process the upgrade request"""
        # Check if user owns this membership
        if membership.partner_id.id != request.env.user.partner_id.id:
            return request.redirect('/my/cards')
        
        target_plan_id = kwargs.get('target_plan_id')
        if not target_plan_id:
            return request.redirect('/my/cards')
        
        try:
            target_plan = request.env['popcorn.membership.plan'].browse(int(target_plan_id))
            if not target_plan.exists():
                return request.redirect('/my/cards')
            
            # Calculate upgrade price
            upgrade_price = self._calculate_upgrade_price(membership, target_plan)
            
            # Store upgrade details in session for checkout
            request.session['upgrade_details'] = {
                'membership_id': membership.id,
                'target_plan_id': target_plan.id,
                'upgrade_price': upgrade_price,
                'is_upgrade': True
            }
            
            # Redirect to checkout page
            return request.redirect(f'/memberships/{target_plan.id}/checkout?upgrade=true')
            
        except Exception as e:
            # Redirect back with error
            return request.redirect(f'/my/cards/{membership.id}/upgrade?error=upgrade_failed')
    
    def _get_available_upgrade_plans(self, membership):
        """Get available upgrade plans based on membership rules"""
        current_plan = membership.membership_plan_id
        
        # Get all active plans that can be upgraded to
        available_plans = request.env['popcorn.membership.plan'].search([
            ('active', '=', True),
            ('id', '!=', current_plan.id)
        ])
        
        # Filter based on upgrade rules
        filtered_plans = []
        for plan in available_plans:
            if self._can_upgrade_to(membership, plan):
                filtered_plans.append(plan)
        
        return filtered_plans
    
    def _can_upgrade_to(self, membership, target_plan):
        """Check if membership can upgrade to target plan"""
        current_plan = membership.membership_plan_id
        
        # Check if upgrade is allowed within time window
        if not self._is_within_upgrade_window(membership):
            return False
        
        # Check if user has upgrade discount ability
        if not membership.upgrade_discount_allowed:
            return False
        
        # Apply specific upgrade rules based on current plan type
        if current_plan.quota_mode == 'bucket_counts':
            # Experience/Online cards can upgrade to Gold or Freedom
            return target_plan.quota_mode in ['unlimited', 'points']
        
        elif current_plan.quota_mode == 'points':
            # Freedom card can upgrade to Gold cards (except 90 GR)
            if target_plan.quota_mode == 'unlimited':
                return '90 GR' not in target_plan.name
        
        elif current_plan.quota_mode == 'unlimited':
            # Gold cards can upgrade to higher Gold cards
            if target_plan.quota_mode == 'unlimited':
                return self._is_higher_gold_card(current_plan, target_plan)
        
        return False
    
    def _is_within_upgrade_window(self, membership):
        """Check if membership is within upgrade window from activation"""
        if not membership.activation_date:
            return False
        
        days_since_activation = (fields.Date.today() - membership.activation_date).days
        upgrade_window_days = membership.membership_plan_id.upgrade_window_days
        return days_since_activation <= upgrade_window_days
    
    def _is_higher_gold_card(self, current_plan, target_plan):
        """Check if target plan is a higher gold card"""
        # Extract duration from plan names
        current_duration = self._extract_duration_from_name(current_plan.name)
        target_duration = self._extract_duration_from_name(target_plan.name)
        
        if current_duration and target_duration:
            return target_duration > current_duration
        
        return False
    
    def _extract_duration_from_name(self, plan_name):
        """Extract duration from plan name (e.g., '90 GR' -> 90)"""
        import re
        match = re.search(r'(\d+)', plan_name)
        return int(match.group(1)) if match else None
    
    def _calculate_upgrade_price(self, membership, target_plan):
        """Calculate upgrade price based on membership rules"""
        current_plan = membership.membership_plan_id
        
        if current_plan.quota_mode == 'bucket_counts':
            return self._calculate_bucket_upgrade_price(membership, target_plan)
        elif current_plan.quota_mode == 'points':
            return self._calculate_freedom_upgrade_price(membership, target_plan)
        elif current_plan.quota_mode == 'unlimited':
            return self._calculate_gold_upgrade_price(membership, target_plan)
        
        return target_plan.price_first_timer
    
    def _calculate_bucket_upgrade_price(self, membership, target_plan):
        """Calculate upgrade price for Experience/Online cards"""
        current_plan = membership.membership_plan_id
        
        # Calculate remaining sessions
        used_offline = membership._count_used_sessions('regular_offline')
        used_online = membership._count_used_sessions('regular_online')
        used_sp = membership._count_used_sessions('spclub')
        
        total_used = used_offline + used_online + used_sp
        total_quota = (current_plan.quota_offline or 0) + (current_plan.quota_online or 0) + (current_plan.quota_sp or 0)
        sessions_left = max(0, total_quota - total_used)
        
        # Calculate unit value
        unit_value = membership.purchase_price_paid / total_quota if total_quota > 0 else 0
        
        # Calculate upgrade price
        upgrade_price = target_plan.price_first_timer - (unit_value * sessions_left)
        return round(max(0, upgrade_price), 2)
    
    def _calculate_freedom_upgrade_price(self, membership, target_plan):
        """Calculate upgrade price for Freedom card"""
        points_remaining = membership.points_remaining
        
        # Calculate unit value based on plan configuration
        unit_value = membership.purchase_price_paid / membership.membership_plan_id.unit_base_count
        
        # Calculate upgrade price
        upgrade_price = target_plan.price_first_timer - (unit_value * (points_remaining / membership.membership_plan_id.points_per_offline))
        return round(max(0, upgrade_price), 2)
    
    def _calculate_gold_upgrade_price(self, membership, target_plan):
        """Calculate upgrade price for Gold cards"""
        current_plan = membership.membership_plan_id
        if not membership.activation_date:
            return target_plan.price_first_timer
        
        # Calculate used days
        days_since_activation = (fields.Date.today() - membership.activation_date).days
        used_days = min(days_since_activation, current_plan.duration_days)
        
        # Calculate pro-rata prices
        old_daily_rate = membership.purchase_price_paid / current_plan.duration_days
        new_daily_rate = target_plan.price_first_timer / target_plan.duration_days
        
        # Calculate upgrade price
        old_remaining_value = old_daily_rate * (current_plan.duration_days - used_days)
        new_remaining_value = new_daily_rate * (target_plan.duration_days - used_days)
        
        upgrade_price = new_remaining_value - old_remaining_value
        return round(max(0, upgrade_price), 2)
    
    def _process_upgrade(self, membership, target_plan):
        """Process the upgrade and create new membership"""
        # Calculate upgrade price
        upgrade_price = self._calculate_upgrade_price(membership, target_plan)
        
        # Create new membership
        new_membership_vals = {
            'partner_id': membership.partner_id.id,
            'membership_plan_id': target_plan.id,
            'state': 'pending',  # Will be activated on first attendance
            'purchase_price_paid': upgrade_price,
            'price_tier': 'first_timer' if membership.upgrade_discount_allowed else 'normal',
            'purchase_channel': 'upgrade',
            'upgrade_discount_allowed': membership.upgrade_discount_allowed,
            'activation_policy': 'first_attendance',
        }
        
        new_membership = request.env['popcorn.membership'].create(new_membership_vals)
        
        # Log the upgrade
        new_membership.message_post(
            body=_('Upgraded from %s to %s. Upgrade price: %s') % (
                membership.membership_plan_id.name,
                target_plan.name,
                upgrade_price
            )
        )
        
        return new_membership
    
    @http.route(['/my/cards/upgrade/success'], type='http', auth="user", website=True)
    def portal_membership_upgrade_success(self, **kwargs):
        """Display upgrade success page"""
        membership_id = kwargs.get('membership_id')
        membership = None
        
        if membership_id:
            membership = request.env['popcorn.membership'].browse(int(membership_id))
            if membership.partner_id.id != request.env.user.partner_id.id:
                membership = None
        
        values = {
            'membership': membership,
            'page_name': 'upgrade_success',
        }
        
        return request.render('popcorn.portal_membership_upgrade_success_page', values)

    @http.route(['/my/cards/<model("popcorn.membership"):membership>/freeze'], type='http', auth="user", website=True, methods=['POST'])
    def portal_membership_freeze(self, membership, **kwargs):
        """Freeze a membership card"""
        _logger.info(f"Freeze request received for membership {membership.id} by user {request.env.user.id}")
        _logger.info(f"Request parameters: {kwargs}")
        _logger.info(f"CSRF token in request: {kwargs.get('csrf_token')}")
        
        # Check if user owns this membership
        if membership.partner_id.id != request.env.user.partner_id.id:
            return request.redirect('/my/cards')
        
        # Check if membership is active
        if membership.state != 'active':
            return request.redirect('/my/cards')
        
        # Check if membership plan allows freezing
        if not membership.membership_plan_id.freeze_allowed:
            return request.redirect('/my/cards')
        
        # Check if already frozen
        if membership.freeze_active:
            return request.redirect('/my/cards')
        
        try:
            freeze_days = int(kwargs.get('freeze_days', 0))
            _logger.info(f"Freeze days: {freeze_days}")
            
            # Validate freeze days
            if freeze_days < membership.membership_plan_id.freeze_min_days:
                _logger.warning(f"Freeze days {freeze_days} less than minimum {membership.membership_plan_id.freeze_min_days}")
                return request.redirect('/my/cards?error=freeze_min_days')
            
            if membership.freeze_total_days_used + freeze_days > membership.membership_plan_id.freeze_max_total_days:
                _logger.warning(f"Freeze days {freeze_days} + used {membership.freeze_total_days_used} exceeds maximum {membership.membership_plan_id.freeze_max_total_days}")
                return request.redirect('/my/cards?error=freeze_max_days')
            
            # Freeze the membership
            _logger.info(f"Calling action_freeze with {freeze_days} days")
            membership.action_freeze(freeze_days)
            
            # Log the action
            membership.message_post(
                body=_('Membership frozen for %s days by portal user') % freeze_days
            )
            
            _logger.info("Freeze successful")
            return request.redirect('/my/cards?success=freeze_applied')
            
        except (ValueError, TypeError) as e:
            _logger.error(f"Invalid freeze days: {e}")
            return request.redirect('/my/cards?error=invalid_freeze_days')
        except Exception as e:
            _logger.error(f"Freeze failed with exception: {e}")
            return request.redirect('/my/cards?error=freeze_failed')

    @http.route(['/my/cards/<model("popcorn.membership"):membership>/unfreeze'], type='http', auth="user", website=True, methods=['POST'])
    def portal_membership_unfreeze(self, membership, **kwargs):
        """Unfreeze a membership card"""
        _logger.info(f"Unfreeze request received for membership {membership.id} by user {request.env.user.id}")
        
        # Check if user owns this membership
        if membership.partner_id.id != request.env.user.partner_id.id:
            return request.redirect('/my/cards')
        
        # Check if membership is frozen
        if not membership.freeze_active:
            return request.redirect('/my/cards')
        
        try:
            # Unfreeze the membership
            membership.action_unfreeze()
            
            # Log the action
            membership.message_post(
                body=_('Membership unfrozen by portal user')
            )
            
            return request.redirect('/my/cards?success=unfreeze_applied')
            
        except Exception as e:
            return request.redirect('/my/cards?error=unfreeze_failed')

    @http.route(['/popcorn/event/freeze-info'], type='json', auth="user", website=True)
    def get_event_freeze_info(self, event_ids=None, **kwargs):
        """Get freeze information for events"""
        if not event_ids:
            return {}
        
        partner = request.env.user.partner_id
        if not partner:
            return {}
        
        events = request.env['event.event'].sudo().browse(event_ids)
        freeze_info = {}
        
        for event in events:
            is_frozen, frozen_membership = self._is_event_in_freeze_period(event, partner)
            freeze_info[event.id] = {
                'is_frozen': is_frozen,
                'frozen_membership': frozen_membership.name if frozen_membership else None,
                'freeze_start': frozen_membership.freeze_start.isoformat() if frozen_membership and frozen_membership.freeze_start else None,
                'freeze_end': frozen_membership.freeze_end.isoformat() if frozen_membership and frozen_membership.freeze_end else None,
            }
        
        return freeze_info

    @http.route(['/my/clubs/<int:registration_id>/cancel'], type='http', auth="user", website=True, methods=['POST'])
    def portal_cancel_registration(self, registration_id, **kwargs):
        """Cancel a club registration"""
        try:
            # Get the registration with sudo and check ownership
            registration = request.env['event.registration'].sudo().search([
                ('id', '=', registration_id),
                ('partner_id', '=', request.env.user.partner_id.id)
            ])
            
            if not registration:
                return request.redirect('/my/clubs?error=cancellation_failed&message=Registration not found')
            
            # Cancel the registration
            registration.action_cancel_registration()
            
            # Redirect with success message
            return request.redirect('/my/clubs?success=registration_cancelled')
            
        except Exception as e:
            _logger.error(f"Failed to cancel registration {registration_id}: {str(e)}")
            # Redirect with error message
            error_param = url_quote(str(e))
            return request.redirect('/my/clubs?error=cancellation_failed&message=' + error_param)
