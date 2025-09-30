# -*- coding: utf-8 -*-

from odoo import http, fields, _
from odoo.http import request
from odoo.exceptions import ValidationError
from odoo.osv import expression
import json
import werkzeug
import logging
from datetime import timedelta
from werkzeug.utils import redirect
from werkzeug.urls import url_quote
from odoo.addons.portal.controllers.portal import CustomerPortal

_logger = logging.getLogger(__name__)


class PopcornEventController(http.Controller):
    """Controller for Popcorn Club membership-gated event registration"""
    
    @http.route(['/event', '/event/page/<int:page>', '/events', '/events/page/<int:page>'], type='http', auth="public", website=True, methods=['GET', 'POST'])
    def events_list(self, page=1, **searches):
        """Override events list to show ALL events on one page without pagination"""
        from odoo.addons.website_event.controllers.main import WebsiteEventController
        from odoo.addons.website.controllers.main import QueryURL
        
        # Call the original controller method but override the step parameter
        original_controller = WebsiteEventController()
        
        # Store original method
        original_method = original_controller.events
        
        def events_without_pagination(self, page=1, **searches):
            """Events method showing all events without pagination"""
            Event = request.env['event.event']
            SudoEventType = request.env['event.type'].sudo()

            searches.setdefault('search', '')
            searches.setdefault('date', 'upcoming')
            searches.setdefault('tags', '')
            searches.setdefault('type', 'all')
            searches.setdefault('country', 'all')
            searches.setdefault('day_of_week', '')

            website = request.website

            # OVERRIDE: Show all events without pagination
            step = 100  # Not used since we show all events

            # Add day_of_week to search options
            search_options = self._get_events_search_options(**searches)
            search_options['day_of_week'] = searches.get('day_of_week')
            options = search_options
            order = 'date_begin'
            if searches.get('date', 'upcoming') == 'old':
                order = 'date_begin desc'
            order = 'is_published desc, ' + order + ', id desc'
            search = searches.get('search')
            
            # Use original search logic but with limit=None to get all events
            event_count, details, fuzzy_search_term = website._search_with_fuzzy("events", search,
                limit=None, order=order, options=options)  # Remove limit to get all events
            
            if details:
                event_details = details[0]
                events = event_details.get('results', Event)
            else:
                # Fallback to direct search - exclude events based on their hide_after_minutes setting
                domain = [
                    ('website_published', '=', True)
                ]
                events = Event.search(domain, order=order)
                event_count = len(events)
                fuzzy_search_term = search
                event_details = {'results': events}
            
            # Filter events based on their hide_after_minutes setting
            current_time = fields.Datetime.now()
            filtered_events = []
            
            for event in events:
                # If hide_after_minutes is 0, never hide the event
                if event.hide_after_minutes == 0:
                    filtered_events.append(event)
                else:
                    # Calculate cutoff time based on event's hide_after_minutes setting
                    cutoff_time = current_time - timedelta(minutes=event.hide_after_minutes)
                    if event.date_begin > cutoff_time:
                        filtered_events.append(event)
            
            # Apply day of week filter if specified (support multiple days)
            if searches.get('day_of_week'):
                selected_days = searches.get('day_of_week').split(',') if isinstance(searches.get('day_of_week'), str) else searches.get('day_of_week')
                if selected_days and selected_days != ['']:
                    day_filtered_events = []
                    for event in filtered_events:
                        if event.day_of_week in selected_days:
                            day_filtered_events.append(event)
                    filtered_events = day_filtered_events
            
            events = Event.browse([e.id for e in filtered_events])
            event_count = len(events)
            
            # Remove pagination slicing - show all events
            # events = events[(page - 1) * step:page * step]  # Commented out to show all events

            # count by domains without self search
            domain_search = [('name', 'ilike', fuzzy_search_term or searches['search'])] if searches['search'] else []

            # Safe access to event_details with fallbacks
            no_date_domain = event_details.get('no_date_domain', [])
            dates = event_details.get('dates', [['upcoming', 'Upcoming', [], 0], ['old', 'Past', [], 0]])
            for date in dates:
                if date[0] not in ['all', 'old']:
                    date[3] = Event.search_count(expression.AND(no_date_domain) + domain_search + date[2])

            no_country_domain = event_details.get('no_country_domain', [])
            countries = event_details.get('countries', [['all', 'All Countries', [], 0]])
            for country in countries:
                if country[0] != 'all':
                    country[3] = Event.search_count(expression.AND(no_country_domain) + domain_search + country[2])

            no_type_domain = event_details.get('no_type_domain', [])
            types = event_details.get('types', [['all', 'All Types', [], 0]])
            for event_type in types:
                if event_type[0] != 'all':
                    event_type[3] = Event.search_count(expression.AND(no_type_domain) + domain_search + event_type[2])

            no_tag_domain = event_details.get('no_tag_domain', [])
            tags = event_details.get('tags', [['all', 'All Tags', [], 0]])
            for tag in tags:
                if tag[0] != 'all':
                    tag[3] = Event.search_count(expression.AND(no_tag_domain) + domain_search + tag[2])

            # Keep only the search results count
            search_results = event_details.get('search_results', ['search', 'Search Results', [], event_count])
            search_results[3] = event_count

            search_tags = event_details.get('search_tags', [])
            current_date = event_details.get('current_date', 'upcoming')
            current_type = None
            current_country = None

            if searches["type"] != 'all':
                current_type = SudoEventType.browse(int(searches['type']))

            if searches["country"] != 'all' and searches["country"] != 'online':
                current_country = request.env['res.country'].browse(int(searches['country']))

            # Disable pagination - set pager to None
            pager = None

            keep = QueryURL('/event', **{
                key: value for key, value in searches.items() if (
                    key == 'search' or
                    (value != 'upcoming' if key == 'date' else value != 'all'))
                })

            searches['search'] = fuzzy_search_term or search

            # Prepare day of week options for the filter
            day_of_week_options = [
                ('0', 'Monday'),
                ('1', 'Tuesday'),
                ('2', 'Wednesday'),
                ('3', 'Thursday'),
                ('4', 'Friday'),
                ('5', 'Saturday'),
                ('6', 'Sunday'),
            ]
            
            # Parse selected days
            selected_days = []
            if searches.get('day_of_week'):
                selected_days = searches.get('day_of_week').split(',') if isinstance(searches.get('day_of_week'), str) else searches.get('day_of_week')
                selected_days = [day.strip() for day in selected_days if day.strip()]
            
            values = {
                'current_date': current_date,
                'current_country': current_country,
                'current_type': current_type,
                'event_ids': events,  # event_ids used in website_event_track so we keep name as it is
                'dates': dates,
                'categories': request.env['event.tag.category'].search([
                    ('is_published', '=', True), '|', ('website_id', '=', website.id), ('website_id', '=', False)
                ]),
                'countries': countries,
                'day_of_week_options': day_of_week_options,
                'selected_days': selected_days,
                'pager': pager,
                'searches': searches,
                'search_tags': search_tags,
                'keep': keep,
                'search_count': event_count,
                'original_search': fuzzy_search_term and search,
                'website': website
            }

            return request.render("website_event.index", values)

        # Apply the patch
        original_controller.events = events_without_pagination.__get__(original_controller, WebsiteEventController)
        
        try:
            return original_controller.events(page=page, **searches)
        finally:
            # Restore original method
            original_controller.events = original_method
    
    
    def _check_membership_access(self, event):
        """
        Check if current user has access to register for this event.
        Returns (has_access, redirect_url, error_message)
        """
        # Check if user is logged in (public user means not logged in)
        if request.env.user.id == request.env.ref('base.public_user').id:
            return False, None, _('Please log in to register for events')
        
        # Get the partner for the current user
        partner = request.env.user.sudo().partner_id
        if not partner:
            return False, None, _('User profile not found')
        
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
            return False, '/memberships', _('Check out the membership plans for big savings and awesome benefits!')
        
        # Check if any membership allows this event type
        event_club_type = self._get_event_club_type(event)
        if not event_club_type:
            return True, None, None  # No club type restriction, allow access
        
        # Check if any membership allows this club type
        for membership in all_usable_memberships:
            if self._can_membership_attend_event(membership, event_club_type):
                return True, None, None
        
        return False, '/memberships', _('Your membership does not allow %s clubs') % event_club_type.replace("_", " ").title()
    
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
            return _("Unlimited membership - no consumption")
        elif membership.plan_quota_mode == 'bucket_counts':
            if club_type == 'regular_offline':
                return _("1 offline session consumed (remaining: %s)") % membership.remaining_offline
    
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
            return _("Unlimited membership - no consumption")
        elif membership.plan_quota_mode == 'bucket_counts':
            if club_type == 'regular_offline':
                return _("1 offline session consumed (remaining: %s)") % membership.remaining_offline
            elif club_type == 'regular_online':
                return _("1 online session consumed (remaining: %s)") % membership.remaining_online
            elif club_type == 'spclub':
                return _("1 special club session consumed (remaining: %s)") % membership.remaining_sp
        elif membership.plan_quota_mode == 'points':
            plan = membership.membership_plan_id
            points_needed = (plan.points_per_offline if club_type == 'regular_offline' 
                           else plan.points_per_online if club_type == 'regular_online' 
                           else plan.points_per_sp)
            return _("%s points consumed (remaining: %s)") % (points_needed, membership.points_remaining)
        return _("Unknown consumption type")
    
    @http.route(['/membership'], type='http', auth="public", website=True)
    def membership_required(self, **kwargs):
        """Display membership required page"""
        # Clear any error messages to prevent loops
        if 'error_message' in request.session:
            del request.session['error_message']
        
        return request.render('popcorn.membership_required_page')
    
    @http.route(['/popcorn/event/<model("event.event"):event>/register'], type='http', auth="public", website=True)
    def event_register(self, event, **kwargs):
        """Override event registration page to show membership and direct purchase options"""
        # Check if user is logged in
        if request.env.user.id == request.env.ref('base.public_user').id:
            # Redirect to login with return URL pointing to the registration page
            registration_url = f'/popcorn/event/{event.id}/register'
            return redirect('/web/login?redirect=' + registration_url)
        
        # User is logged in, check membership access and show registration options page
        has_access, redirect_url, error_message = self._check_membership_access(event)
        
        values = {
            'event': event,
            'has_membership_access': has_access,
            'membership_error': error_message,
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
        return {'status': 'success', 'message': _('Registration form available')}
    
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
                            error_message = _('Insufficient points. You need %s points but have %s remaining') % (points_needed, membership.points_remaining)
                            quota_issue_found = True
                            break
                    elif membership.plan_quota_mode == 'bucket_counts':
                        if event_club_type == 'regular_offline' and membership.remaining_offline < 1:
                            error_message = _('No offline sessions remaining. You have %s offline sessions left') % membership.remaining_offline
                            quota_issue_found = True
                            break
                        elif event_club_type == 'regular_online' and membership.remaining_online < 1:
                            error_message = _('No online sessions remaining. You have %s online sessions left') % membership.remaining_online
                            quota_issue_found = True
                            break
                        elif event_club_type == 'spclub' and membership.remaining_sp < 1:
                            error_message = _('No special club sessions remaining. You have %s special club sessions left') % membership.remaining_sp
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
                        error_message = _('Your membership does not allow %s clubs') % event_club_type.replace("_", " ").title()
                    else:
                        # All checks passed but something else is wrong
                        error_message = _('Insufficient quota for this club')
            else:
                error_message = _('No suitable membership found for this club')
            
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
        
        # Create the registration (consumption is now handled automatically in create method)
        try:
            registration = request.env['event.registration'].sudo().create(registration_vals)
        except ValidationError as e:
            # Catch validation errors and redirect back with error message
            error_param = url_quote(str(e))
            return redirect(f'/popcorn/event/{event.id}/register?error=' + error_param)
        
        # Check if registration was added to waitlist
        is_waitlist = registration.is_on_waitlist
        waitlist_position = registration.waitlist_position if is_waitlist else 0
        
        # Get consumption text only if not on waitlist
        consumption_text = ""
        if not is_waitlist:
            consumption_text = self._get_consumption_text(best_membership, event_club_type)
        
        # Show success page
        values = {
            'event': event,
            'partner': partner,
            'best_membership': best_membership,
            'registration': registration,
            'event_club_type': event_club_type,
            'consumption_text': consumption_text,
            'is_waitlist': is_waitlist,
            'waitlist_position': waitlist_position,
        }
        
        # Clear UI caches to ensure fresh data
        request.env['ir.ui.view'].clear_caches()
        
        return request.render('popcorn.event_registration_success_page', values)
    
    @http.route(['/popcorn/event/<model("event.event"):event>/purchase/direct'], type='http', auth="user", website=True, methods=['POST'])
    def event_direct_purchase(self, event, purchase_type='membership', **kwargs):
        """Handle direct event purchase - either membership or direct payment"""
        # Check if user is logged in
        if request.env.user.id == request.env.ref('base.public_user').id:
            return redirect('/web/login?redirect=' + request.httprequest.url)
        
        # Get the partner for the current user
        partner = request.env.user.sudo().partner_id
        if not partner:
            error_message = _('User profile not found')
            error_param = url_quote(error_message)
            return redirect(f'/popcorn/event/{event.id}/register?error=' + error_param)
        
        # Check if user is already registered for this event
        existing_registration = request.env['event.registration'].sudo().search([
            ('event_id', '=', event.id),
            ('partner_id', '=', partner.id),
            ('state', 'in', ['open', 'confirmed'])
        ])
        
        if existing_registration:
            error_message = _('You are already registered for this club')
            error_param = url_quote(error_message)
            return redirect(f'/popcorn/event/{event.id}/register?error=' + error_param)
        
        if purchase_type == 'membership':
            # Flow 1: Redirect to membership plans
            return request.redirect('/memberships')
        
        elif purchase_type == 'direct_payment':
            # Flow 2: Direct payment for the event - redirect to dedicated event checkout
            # Check if event has a price set
            if not event.event_price or event.event_price <= 0:
                error_message = _('This club is not available for direct purchase')
                error_param = url_quote(error_message)
                return redirect(f'/popcorn/event/{event.id}/register?error=' + error_param)
            
            # Redirect to dedicated event checkout page
            return request.redirect(f'/popcorn/event/{event.id}/checkout')
        
        else:
            # Default: redirect to membership plans
            return request.redirect('/memberships')
    
    @http.route(['/popcorn/event/<model("event.event"):event>/purchase/membership'], type='http', auth="user", website=True, methods=['POST'])
    def event_purchase_membership(self, event, **kwargs):
        """Handle event purchase by redirecting to membership plans"""
        return self.event_direct_purchase(event, purchase_type='membership', **kwargs)
    
    @http.route(['/popcorn/event/<model("event.event"):event>/purchase/direct-payment'], type='http', auth="user", website=True, methods=['POST'])
    def event_purchase_direct_payment(self, event, **kwargs):
        """Handle direct payment for event without membership"""
        return self.event_direct_purchase(event, purchase_type='direct_payment', **kwargs)
    
    @http.route(['/popcorn/event/<model("event.event"):event>/checkout'], type='http', auth="user", website=True)
    def event_checkout(self, event, **kwargs):
        """Display event checkout page"""
        # Check if user is logged in
        if request.env.user.id == request.env.ref('base.public_user').id:
            return redirect('/web/login?redirect=' + request.httprequest.url)
        
        # Check if event has a price set
        if not event.event_price or event.event_price <= 0:
            return request.not_found()
        
        # Check if user is already registered for this event
        partner = request.env.user.sudo().partner_id
        existing_registration = request.env['event.registration'].sudo().search([
            ('event_id', '=', event.id),
            ('partner_id', '=', partner.id),
            ('state', 'in', ['open', 'confirmed'])
        ])
        
        if existing_registration:
            return request.render('popcorn.event_already_registered_page', {
                'event': event,
                'registration': existing_registration
            })
        
        values = {
            'event': event,
            'partner': partner,
        }
        
        return request.render('popcorn.event_checkout_page', values)
    
    @http.route(['/popcorn/event/<model("event.event"):event>/process_checkout'], type='http', auth="user", website=True, methods=['POST'])
    def event_process_checkout(self, event, **kwargs):
        """Process event checkout and initiate payment transaction"""
        # Check if user is logged in
        if request.env.user.id == request.env.ref('base.public_user').id:
            return redirect('/web/login?redirect=' + request.httprequest.url)
        
        # Check if event has a price set
        if not event.event_price or event.event_price <= 0:
            return request.not_found()
        
        partner = request.env.user.sudo().partner_id
        
        # Check if user is already registered for this event
        existing_registration = request.env['event.registration'].sudo().search([
            ('event_id', '=', event.id),
            ('partner_id', '=', partner.id),
            ('state', 'in', ['open', 'confirmed'])
        ])
        
        if existing_registration:
            return request.render('popcorn.event_already_registered_page', {
                'event': event,
                'registration': existing_registration
            })
        
        try:
            # Validate form data
            if not kwargs.get('payment_method_id'):
                return request.redirect(f'/popcorn/event/{event.id}/checkout?error=missing_payment_method')
            
            if not kwargs.get('terms_accepted'):
                return request.redirect(f'/popcorn/event/{event.id}/checkout?error=terms_not_accepted')
            
            # Get payment method/provider ID
            payment_method_id = kwargs.get('payment_method_id')
            
            # Check if it's a manual payment (fallback)
            if payment_method_id == 'manual':
                # For manual payment, create registration directly but mark as pending payment
                registration_vals = {
                    'event_id': event.id,
                    'partner_id': partner.id,
                    'name': partner.name,
                    'email': partner.email,
                    'phone': partner.phone,
                    'state': 'draft',
                }
                
                registration = request.env['event.registration'].sudo().create(registration_vals)
                
                # Log the manual payment request
                registration.message_post(
                    body=_('Manual payment requested for club: %s. Price: $%s. Payment method: Manual') % (event.name, event.event_price)
                )
                
                # Redirect to success page with pending payment status
                return request.redirect(f'/popcorn/event/{event.id}/purchase/success?registration_id={registration.id}&payment_pending=true')
            
            # Otherwise, it should be a payment provider ID
            try:
                provider_id = int(payment_method_id)
                
                # Use payment.provider (Odoo 18)
                payment_provider = None
                try:
                    payment_provider = request.env['payment.provider'].browse(provider_id)
                    
                    if not payment_provider or not payment_provider.exists() or payment_provider.state != 'enabled':
                        return request.redirect(f'/popcorn/event/{event.id}/checkout?error=invalid_payment_method')
                except Exception as e:
                    _logger.error(f"Failed to access payment provider: {str(e)}")
                    return request.redirect(f'/popcorn/event/{event.id}/checkout?error=payment_access_denied')
                    
            except (ValueError, TypeError):
                return request.redirect(f'/popcorn/event/{event.id}/checkout?error=invalid_payment_method')
            
            # Store event purchase details in session for after payment
            request.session['event_purchase_details'] = {
                'event_id': event.id,
                'partner_id': partner.id,
                'event_price': event.event_price,
                'payment_provider_id': payment_provider.id,
                'payment_provider_name': payment_provider.name,
            }
            
            _logger.info(f"Stored pending event purchase in session: {request.session['event_purchase_details']}")
            
            # Handle different payment methods based on provider name
            _logger.info(f"Payment provider name: '{payment_provider.name}', lowercase: '{payment_provider.name.lower()}'")
            if payment_provider.name.lower() in ['bank transfer', 'bank_transfer']:
                # For bank transfer, create registration immediately but mark as pending payment
                registration_vals = {
                    'event_id': event.id,
                    'partner_id': partner.id,
                    'name': partner.name,
                    'email': partner.email,
                    'phone': partner.phone,
                    'state': 'draft',
                }
                
                registration = request.env['event.registration'].sudo().create(registration_vals)
                
                # Log the bank transfer payment request
                registration.message_post(
                    body=_('Bank transfer payment requested for club: %s. Price: $%s. Payment method: %s') % (event.name, event.event_price, payment_provider.name)
                )
                
                # Redirect to success page with pending payment status
                return request.redirect(f'/popcorn/event/{event.id}/purchase/success?registration_id={registration.id}&payment_pending=true')
            elif payment_provider.name.lower() in ['wechat', 'wechat pay', 'wechatpay']:
                # For WeChat payments, redirect to WeChat OAuth2 flow
                _logger.info(f"Creating WeChat payment transaction for event purchase, provider: {payment_provider.name}")
                
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
                
                # Create payment transaction with unique reference (NO registration created yet)
                import time
                timestamp = int(time.time())
                
                payment_transaction = request.env['payment.transaction'].sudo().create({
                    'provider_id': payment_provider.id,
                    'payment_method_id': payment_method.id,
                    'amount': event.event_price,
                    'currency_id': event.currency_id.id if hasattr(event, 'currency_id') and event.currency_id else request.env.ref('base.USD').id,
                    'partner_id': partner.id,
                    'reference': f'EVENT-{event.id}-{partner.id}-{timestamp}',
                    'state': 'draft',
                })
                
                _logger.info(f"WeChat event payment transaction created with ID: {payment_transaction.id}")
                
                # Store transaction ID and event purchase data in session for callback (NO registration created yet)
                request.session['payment_transaction_id'] = payment_transaction.id
                # event_purchase_details is already stored in session above
                
                # Store the event purchase data in session for WeChat success callback
                request.session['wechat_pending_event_purchase'] = {
                    'event_id': event.id,
                    'partner_id': partner.id,
                    'event_price': event.event_price,
                    'payment_provider_id': payment_provider.id,
                    'payment_provider_name': payment_provider.name,
                }
                
                # Redirect to WeChat OAuth2 flow
                wechat_oauth_url = f'/payment/wechat/oauth2/authorize?transaction_id={payment_transaction.reference}'
                _logger.info(f"Redirecting to WeChat OAuth2 for event purchase: {wechat_oauth_url}")
                return request.redirect(wechat_oauth_url)
            else:
                # For all other online payments (Stripe/PayPal/etc), create payment transaction and redirect to gateway
                _logger.info(f"Creating payment transaction for event purchase, provider: {payment_provider.name}")
                
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
                
                # Create payment transaction with unique reference (NO registration created yet)
                import time
                timestamp = int(time.time())
                
                payment_transaction = request.env['payment.transaction'].sudo().create({
                    'provider_id': payment_provider.id,
                    'payment_method_id': payment_method.id,
                    'amount': event.event_price,
                    'currency_id': event.currency_id.id if hasattr(event, 'currency_id') and event.currency_id else request.env.ref('base.USD').id,
                    'partner_id': partner.id,
                    'reference': f'EVENT-{event.id}-{partner.id}-{timestamp}',
                    'state': 'draft',
                })
                
                _logger.info(f"Event payment transaction created with ID: {payment_transaction.id}")
                
                # Store transaction ID and event purchase data in session for callback (NO registration created yet)
                request.session['payment_transaction_id'] = payment_transaction.id
                # event_purchase_details is already stored in session above
                
                # Let the payment gateway handle the payment flow
                try:
                    payment_link = payment_transaction._get_specific_rendering_values(None)
                    if payment_link and 'action_url' in payment_link:
                        _logger.info(f"Redirecting to payment gateway for event purchase: {payment_link['action_url']}")
                        return request.redirect(payment_link['action_url'])
                except Exception as e:
                    _logger.warning(f"Failed to get payment link for event: {str(e)}")
                
                # Fallback: if no payment link available, redirect to payment failed page
                _logger.warning("No payment link available for event purchase, redirecting to payment failed page")
                request.session.pop('event_purchase_details', None)
                return request.redirect(f'/popcorn/event/{event.id}/checkout?error=gateway_unavailable')
            
        except Exception as e:
            _logger.error(f"Failed to process event checkout: {str(e)}")
            return request.redirect(f'/popcorn/event/{event.id}/checkout?error=processing_failed')
    
    @http.route(['/popcorn/event/<model("event.event"):event>/checkout/success'], type='http', auth="user", website=True)
    def event_checkout_success(self, event, **kwargs):
        """Display event checkout success page"""
        registration_id = kwargs.get('registration_id')
        registration = None
        
        if registration_id:
            registration = request.env['event.registration'].sudo().browse(int(registration_id))
        
        values = {
            'event': event,
            'registration': registration,
            'partner': request.env.user.sudo().partner_id,
            'purchase_price': event.event_price,
        }
        
        return request.render('popcorn.event_checkout_success_page', values)
    
    @http.route(['/popcorn/event/<model("event.event"):event>/purchase/success'], type='http', auth="user", website=True)
    def event_purchase_success(self, event, **kwargs):
        """Display success page after event purchase"""
        registration_id = kwargs.get('registration_id')
        payment_success = kwargs.get('payment_success')
        transaction_id_param = kwargs.get('transaction_id')
        registration = None
        
        # Handle WeChat payment success redirect
        if payment_success == 'true' and transaction_id_param:
            _logger.info(f"=== WeChat event payment success redirect ===")
            _logger.info(f"Event ID: {event.id}")
            _logger.info(f"Transaction ID: {transaction_id_param}")
            _logger.info(f"Session keys: {list(request.session.keys())}")
            _logger.info(f"WeChat pending event purchase in session: {bool(request.session.get('wechat_pending_event_purchase'))}")
            _logger.info(f"Regular event purchase details in session: {bool(request.session.get('event_purchase_details'))}")
            
            # Get pending event purchase data from session (try both keys)
            pending_event_purchase = request.session.get('wechat_pending_event_purchase')
            if not pending_event_purchase:
                _logger.warning("No WeChat pending event purchase found, trying regular event purchase details")
                pending_event_purchase = request.session.get('event_purchase_details')
                
            if not pending_event_purchase:
                _logger.error("No pending event purchase found in session (neither WeChat nor regular)")
                _logger.error(f"Session contents: {dict(request.session)}")
                return request.redirect(f'/popcorn/event/{event.id}/checkout?error=session_expired')
            
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
                return request.redirect(f'/popcorn/event/{event.id}/checkout?error=transaction_not_found')
            
            _logger.info(f"Found transaction: {transaction.id}, State: {transaction.state}, Provider: {transaction.provider_id.name if transaction.provider_id else 'None'}")
            
            # Mark transaction as done (WeChat payment was successful)
            transaction.write({'state': 'done'})
            
            # Create event registration now
            _logger.info(f"Creating event registration with data: {pending_event_purchase}")
            partner = request.env['res.partner'].sudo().browse(pending_event_purchase['partner_id'])
            
            _logger.info(f"Partner exists: {partner.exists()}")
            _logger.info(f"Partner name: {partner.name if partner.exists() else 'N/A'}")
            
            if not partner.exists():
                _logger.error(f"Invalid partner - Partner ID: {pending_event_purchase.get('partner_id')}")
                return request.redirect(f'/popcorn/event/{event.id}/checkout?error=invalid_data')
            
            # Create the event registration (using only standard fields)
            _logger.info("Creating event registration")
            registration_vals = {
                'event_id': event.id,
                'partner_id': partner.id,
                'name': partner.name,
                'email': partner.email,
                'phone': partner.phone,
                'state': 'open',
            }
            
            registration = request.env['event.registration'].sudo().create(registration_vals)
            _logger.info(f"Event registration created with ID: {registration.id}, State: {registration.state}")
            
            registration.message_post(
                body=_('Direct purchase registration for event: %s. Price: %s. Payment successful via %s. Transaction: %s. Event registration created and activated.') % (event.name, pending_event_purchase['event_price'], transaction.provider_id.name, transaction.reference)
            )
            _logger.info(f"Event registration message posted")
            
            # Clear session data
            request.session.pop('payment_transaction_id', None)
            request.session.pop('event_purchase_details', None)
            request.session.pop('wechat_pending_event_purchase', None)
            
            _logger.info(f"WeChat event payment successful. Registration created with ID: {registration.id}")
            _logger.info(f"Final registration details - ID: {registration.id}, State: {registration.state}, Partner: {registration.partner_id.name}")
            
            # Continue to show success page with the created registration
            # (don't redirect, just continue with the existing registration)
        
        # Regular success page handling
        if registration_id:
            registration = request.env['event.registration'].sudo().browse(int(registration_id))
        
        values = {
            'event': event,
            'partner': request.env.user.partner_id,
            'registration': registration,
            'purchase_price': event.event_price,
        }
        
        return request.render('popcorn.event_direct_purchase_success_page', values)
    
    @http.route(['/popcorn/shop/cart/update_json'], type='json', auth="public")
    def cart_update_json(self, product_id, add_qty=1, set_qty=0, **kwargs):
        """Custom cart update for event ticket products"""
        # This route is now just for reference, the main logic is in cart_update_json_redirect
        return {'status': 'success', 'message': 'Custom cart update'}
    
    def _check_membership_access_for_product(self, product):
        """Check membership access for a specific product"""
        # Check if user is logged in (public user means not logged in)
        if request.env.user.id == request.env.ref('base.public_user').id:
            return False, '/web/login?redirect=' + request.httprequest.url, _('Please log in to purchase event tickets')
        
        # Get the partner for the current user
        partner = request.env.user.sudo().partner_id
        if not partner:
            return False, '/web/login?redirect=' + request.httprequest.url, _('User profile not found')
        
        # Check if user has any active memberships
        active_memberships = request.env['popcorn.membership'].sudo().search([
            ('partner_id', '=', partner.id),
            ('state', 'in', ['active', 'frozen'])
        ])
        
        if not active_memberships:
            return False, '/memberships', _('Check out the membership plans for big savings and awesome benefits!')
        
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
            success_message = _('Registration has been successfully cancelled.')
        elif kwargs.get('error') == 'cancellation_failed':
            error_message = kwargs.get('message', _('Failed to cancel registration. Please try again.'))
        
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
            error_message = _('Freeze duration must be at least the minimum required days.')
        elif kwargs.get('error') == 'freeze_max_days':
            error_message = _('Freeze duration exceeds the maximum allowed days.')
        elif kwargs.get('error') == 'invalid_freeze_days':
            error_message = _('Invalid freeze duration specified.')
        elif kwargs.get('error') == 'freeze_failed':
            error_message = _('Failed to freeze membership. Please try again.')
        elif kwargs.get('error') == 'unfreeze_failed':
            error_message = _('Failed to unfreeze membership. Please try again.')
        elif kwargs.get('error') == 'cancellation_failed':
            error_message = kwargs.get('message', _('Failed to cancel registration. Please try again.'))
        elif kwargs.get('success') == 'freeze_applied':
            success_message = _('Membership has been successfully frozen.')
        elif kwargs.get('success') == 'unfreeze_applied':
            success_message = _('Membership has been successfully unfrozen.')
        elif kwargs.get('success') == 'registration_cancelled':
            success_message = _('Registration has been successfully cancelled.')
        
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



    @http.route(['/event/<model("event.event"):event>', '/event/<model("event.event"):event>/<string:page>'], type='http', auth="public", website=True)
    def event(self, event, page='main', **kwargs):
        """Override event detail page to ensure proper access control"""
        from odoo.addons.website_event.controllers.main import WebsiteEventController
        
        # Ensure we can access the event with sudo() to avoid access issues
        try:
            # Pre-check event access with sudo() to ensure it exists and is accessible
            accessible_event = request.env['event.event'].sudo().browse(event.id)
            if not accessible_event.exists():
                _logger.error(f"Event {event.id} not found or not accessible")
                return request.not_found()
            
            # Log successful access
            _logger.info(f"Event detail page accessed for event {event.id}: {event.name}")
            
        except Exception as e:
            _logger.error(f"Error accessing event {event.id}: {str(e)}")
            return request.not_found()
        
        # Call the original event detail method
        response = WebsiteEventController().event(event=event, page=page, **kwargs)
        
        return response

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
                return request.redirect('/my/clubs?error=cancellation_failed&message=' + url_quote(_('Registration not found')))
            
            # Cancel the registration
            registration.action_cancel_registration()
            
            # Redirect with success message
            return request.redirect('/my/clubs?success=registration_cancelled')
            
        except Exception as e:
            _logger.error(f"Failed to cancel registration {registration_id}: {str(e)}")
            # Redirect with error message
            error_param = url_quote(str(e))
            return request.redirect('/my/clubs?error=cancellation_failed&message=' + error_param)
    
    @http.route(['/my/clubs/cancel-conflicting'], type='http', auth="user", website=True, methods=['POST'])
    def cancel_conflicting_registration(self, **kwargs):
        """Cancel a conflicting registration via AJAX"""
        try:
            # Debug logging
            _logger.info(f"Cancel conflicting registration called with params: {request.params}")
            _logger.info(f"Cancel conflicting registration called with kwargs: {kwargs}")
            
            # Get data from request - in Odoo 18, use request.params for JSON data
            event_id = request.params.get('event_id')
            
            _logger.info(f"Event ID from request: {event_id}")
            
            if not event_id:
                _logger.warning("No event_id provided in request")
                return request.make_json_response({'success': False, 'message': 'Event ID is required'})
            
            # Get the current user's registration for this event
            registration = request.env['event.registration'].sudo().search([
                ('event_id', '=', int(event_id)),
                ('partner_id', '=', request.env.user.partner_id.id),
                ('state', 'in', ['open', 'confirmed'])
            ], limit=1)
            
            _logger.info(f"Found registration: {registration}")
            
            if not registration:
                _logger.warning(f"No registration found for event {event_id} and partner {request.env.user.partner_id.id}")
                return request.make_json_response({'success': False, 'message': 'Registration not found'})
            
            # Cancel the registration
            registration.action_cancel_registration()
            
            _logger.info(f"Successfully cancelled registration {registration.id}")
            return request.make_json_response({'success': True, 'message': 'Registration cancelled successfully'})
            
        except Exception as e:
            _logger.error(f"Failed to cancel conflicting registration: {str(e)}")
            return request.make_json_response({'success': False, 'message': str(e)})