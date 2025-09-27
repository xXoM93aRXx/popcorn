from odoo import models, fields, api, _
from odoo.exceptions import AccessError
from odoo.http import request
import logging
from datetime import timedelta

_logger = logging.getLogger(__name__)


class EventEvent(models.Model):
    _inherit = 'event.event'
    
    host_id = fields.Many2one(
        'res.partner',
        string='Host',
        help='Select the host for this event'
    )
    
    cancellation_deadline_hours = fields.Integer(
        string='Cancellation Deadline (Hours)',
        default=24,
        help='Number of hours before the event start time when users can cancel their registration'
    )
    
    event_price = fields.Float(
        string='Event Price',
        digits='Product Price',
        help='Price for attending this event'
    )
    
    hide_after_minutes = fields.Integer(
        string='Hide After Minutes',
        default=15,
        help='Number of minutes after event start when the event should disappear from the website. Set to 0 to never hide.'
    )
    
    # Club type classification (computed, not stored in UI)
    club_type = fields.Selection([
        ('regular_offline', 'Regular Offline'),
        ('regular_online', 'Regular Online'),
        ('spclub', 'Special Club')
    ], string='Club Type', compute='_compute_club_type', store=False, 
       help='Automatically determined club type for membership validation')
    
    # Computed fields for website template (not stored, computed on demand)
    host_name = fields.Char(
        string='Host Name',
        compute='_compute_host_info',
        store=False,
        help='Host name for website display'
    )
    
    # Searchable host name field for search functionality
    host_search_name = fields.Char(
        string='Host Search Name',
        compute='_compute_host_search_name',
        store=True,
        help='Host name for search functionality'
    )
    
    # Seat availability and waitlist information (depends on seats_limited field)
    seats_available = fields.Integer(
        string='Seats Available',
        compute='_compute_seat_availability',
        store=False,
        help='Number of available seats'
    )
    
    seats_taken = fields.Integer(
        string='Seats Taken',
        compute='_compute_seat_availability',
        store=False,
        help='Number of seats taken'
    )
    
    waitlist_count = fields.Integer(
        string='Waitlist Count',
        compute='_compute_waitlist_info',
        store=False,
        help='Number of people on waitlist'
    )
    
    # User's waitlist position (for current user)
    user_waitlist_position = fields.Integer(
        string='Your Waitlist Position',
        compute='_compute_user_waitlist_position',
        store=False,
        help='Current user\'s position on the waitlist'
    )
    
    host_image = fields.Binary(
        string='Host Image',
        compute='_compute_host_info',
        store=False,
        help='Host image for website display'
    )
    
    host_function = fields.Char(
        string='Host Function',
        compute='_compute_host_info',
        store=False,
        help='Host job title/function for website display'
    )
    
    host_bio = fields.Text(
        string='Host Bio',
        compute='_compute_host_info',
        store=False,
        help='Host biography for website display'
    )
    
    # Location computed fields to avoid res.partner access
    event_city = fields.Char(
        string='Event City',
        compute='_compute_location_info',
        store=False,
        help='Event city for website display'
    )
    
    event_country_name = fields.Char(
        string='Event Country',
        compute='_compute_location_info',
        store=False,
        help='Event country name for website display'
    )
    
    event_country_flag = fields.Char(
        string='Event Country Flag',
        compute='_compute_location_info',
        store=False,
        help='Event country flag URL for website display'
    )
    
    is_online_event = fields.Boolean(
        string='Is Online Event',
        compute='_compute_location_info',
        store=False,
        help='Whether this is an online event'
    )
    
    # User registration status fields
    has_conflicting_registration = fields.Boolean(
        string='Has Conflicting Registration',
        compute='_compute_has_conflicting_registration',
        store=False,
        help='Whether the current user has a conflicting registration for another event at the same time'
    )
    
    conflicting_event = fields.Many2one(
        'event.event',
        string='Conflicting Event',
        compute='_compute_has_conflicting_registration',
        store=False,
        help='The event that conflicts with this one'
    )

    @api.depends('tag_ids', 'is_online_event')
    def _compute_club_type(self):
        """Compute club type from tags or event properties"""
        for event in self:
            # Try to determine from tags
            if event.tag_ids:
                type_tag = event.tag_ids.filtered(
                    lambda tag: tag.category_id.name == 'Type'
                )
                if type_tag:
                    tag_name = type_tag.name.lower()
                    if 'offline' in tag_name:
                        event.club_type = 'regular_offline'
                    elif 'online' in tag_name:
                        event.club_type = 'regular_online'
                    elif 'sp' in tag_name or 'special' in tag_name:
                        event.club_type = 'spclub'
                    else:
                        event.club_type = False
                else:
                    event.club_type = False
            else:
                event.club_type = False
            
            # Fallback to event properties if no tags
            if not event.club_type:
                if hasattr(event, 'is_online_event') and event.is_online_event:
                    event.club_type = 'regular_online'
                else:
                    event.club_type = 'regular_offline'
    
    def is_in_freeze_period(self, partner):
        """Check if this event falls within any of the partner's freeze periods"""
        if not partner or not self.date_begin:
            return False, None
        
        # Get all frozen memberships for this partner
        frozen_memberships = self.env['popcorn.membership'].sudo().search([
            ('partner_id', '=', partner.id),
            ('freeze_active', '=', True)
        ])
        
        if not frozen_memberships:
            return False, None
        
        # Convert event datetime to date for comparison
        event_date = self.date_begin.date() if self.date_begin else None
        
        # Check if event date falls within any freeze period
        for membership in frozen_memberships:
            if membership.freeze_start and membership.freeze_end:
                # Event is frozen if it's during the freeze period
                # Event is frozen if it's during the freeze period (exclusive of end date)
                # If freeze ends on Sept 10, events on Sept 11 should be bookable
                is_frozen = (membership.freeze_start <= event_date and event_date < membership.freeze_end)
                
                # For debugging - let's log this
                print(f"Event {self.name} on {event_date}, freeze period: {membership.freeze_start} to {membership.freeze_end}, is_frozen: {is_frozen}")
                
                if is_frozen:
                    return True, membership
        
        return False, None
    
    @api.depends('host_id')
    def _compute_host_info(self):
        """Compute host name, image, function, and bio from host_id"""
        for event in self:
            try:
                if event.host_id:
                    # Use sudo() to bypass access rights for reading basic fields
                    host = event.host_id.sudo()
                    event.host_name = host.name or ''
                    event.host_image = host.image_128 or False
                    event.host_function = host.function or 'Host'
                    event.host_bio = host.host_bio or ''
                else:
                    event.host_name = ''
                    event.host_image = False
                    event.host_function = ''
                    event.host_bio = ''
            except:
                # If there's any access issue, set default values
                event.host_name = ''
                event.host_image = False
                event.host_function = ''
                event.host_bio = ''
    
    @api.depends('host_id')
    def _compute_host_search_name(self):
        """Compute searchable host name for search functionality"""
        for event in self:
            try:
                if event.host_id:
                    # Use sudo() to bypass access rights for reading basic fields
                    host = event.host_id.sudo()
                    event.host_search_name = host.name or ''
                else:
                    event.host_search_name = ''
            except:
                # If there's any access issue, set default values
                event.host_search_name = ''
    
    @api.depends('address_id')
    def _compute_location_info(self):
        """Compute location information to avoid direct res.partner access"""
        for event in self:
            try:
                if event.address_id:
                    # Use sudo() to bypass access rights for reading basic fields
                    address = event.address_id.sudo()
                    event.event_city = address.city or ''
                    if address.country_id:
                        country = address.country_id.sudo()
                        event.event_country_name = country.name or ''
                        event.event_country_flag = country.image_url or ''
                    else:
                        event.event_country_name = ''
                        event.event_country_flag = ''
                    event.is_online_event = False
                else:
                    event.event_city = ''
                    event.event_country_name = ''
                    event.event_country_flag = ''
                    event.is_online_event = True
            except:
                # If there's any access issue, set default values
                event.event_city = ''
                event.event_country_name = ''
                event.event_country_flag = ''
                event.is_online_event = True

    @api.model
    def create(self, vals):
        """Override create to automatically set is_host field when host is assigned"""
        event = super().create(vals)
        
        # If a host is assigned, mark them as a host
        if event.host_id:
            event.host_id.is_host = True
            
        return event
    
    def write(self, vals):
        """Override write to automatically set is_host field when host is assigned and promote waitlist"""
        # Store original seats_max to check if capacity increased
        original_seats_max = self.seats_max if hasattr(self, 'seats_max') else None
        
        result = super().write(vals)
        
        # If host_id is being set, mark the partner as a host
        if 'host_id' in vals and vals['host_id']:
            host_partner = self.env['res.partner'].browse(vals['host_id'])
            host_partner.is_host = True
        
        # If seats_max increased, trigger auto-promotion via computed field
        if 'seats_max' in vals and original_seats_max is not None:
            new_seats_max = vals['seats_max']
            if new_seats_max > original_seats_max:
                _logger.info(f"Event {self.id}: Seats increased from {original_seats_max} to {new_seats_max}, triggering auto-promotion")
                # Trigger the computed field to recalculate and auto-promote
                self._compute_seat_availability()
            
        return result
    
    @api.depends('tag_ids', 'tag_ids.category_id.controls_card_color')
    def _compute_background_color(self):
        for event in self:
            bg_color = '#ffffff'  # default white
            text_color = '#000000'  # default black text
            for tag in event.tag_ids:
                if tag.category_id.controls_card_color and tag.color:
                    # Odoo stores colors as integers, convert to hex
                    # The color field contains a numeric value that represents the color
                    bg_color = self._int_to_hex_color(tag.color)
                    # Calculate text color based on background brightness
                    text_color = self._get_contrasting_text_color(bg_color)
                    break
            event.background_color = bg_color
            event.text_color = text_color
    
    def _int_to_hex_color(self, color_int):
        """Convert Odoo's integer color value to hex color"""
        # Odoo color values are typically stored as integers
        # We need to convert this to a proper hex color
        # Mapping shifted by one to align with the 12 color blocks
        color_mapping = {
            0: '#ffffff',   # White
            1: '#ffb3ba',   # Light Pink
            2: '#ffcc99',   # Light Orange
            3: '#ffff99',   # Light Yellow
            4: '#b3d9ff',   # Light Blue
            5: '#e6ccff',   # Light Purple
            6: '#ffd9b3',   # Light Peach
            7: '#b3ffcc',   # Light Green
            8: '#cce6ff',   # Light Lavender
            9: '#ffb3d9',  # Light Pink
            10: '#ccffcc',  # Light Green
            11: '#e6ccff',  # Light Purple
        }
        return color_mapping.get(color_int, '#ffffff')
    
    def _get_contrasting_text_color(self, hex_color):
        """Calculate whether to use white or black text based on background brightness"""
        # Remove # if present
        hex_color = hex_color.lstrip('#')
        
        # Convert hex to RGB
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        
        # Calculate relative luminance (standard formula)
        # Convert to sRGB and apply gamma correction
        def to_srgb(c):
            c = c / 255.0
            if c <= 0.03928:
                return c / 12.92
            else:
                return ((c + 0.055) / 1.055) ** 2.4
        
        r_srgb = to_srgb(r)
        g_srgb = to_srgb(g)
        b_srgb = to_srgb(b)
        
        # Calculate relative luminance
        luminance = 0.2126 * r_srgb + 0.7152 * g_srgb + 0.0722 * b_srgb
        
        # Use white text on dark backgrounds, black text on light backgrounds
        # Threshold of 0.5 provides good contrast
        if luminance > 0.5:
            return '#000000'  # Black text on light backgrounds
        else:
            return '#ffffff'  # White text on dark backgrounds
    
    background_color = fields.Char(
        string='Background Color',
        compute='_compute_background_color',
        store=False,
        help='Background color for the event card based on tags'
    )
    
    text_color = fields.Char(
        string='Text Color',
        compute='_compute_background_color',
        store=False,
        help='Automatically calculated text color for optimal contrast'
    )
    
    def can_register_with_membership(self, membership):
        """Check if a specific membership can be used for this event"""
        self.ensure_one()
        
        if not membership or not self.club_type:
            return False
        
        # Check club type permissions
        if self.club_type == 'regular_offline' and not membership.plan_allowed_regular_offline:
            return False
        elif self.club_type == 'regular_online' and not membership.plan_allowed_regular_online:
            return False
        elif self.club_type == 'spclub' and not membership.plan_allowed_spclub:
            return False
        
        # Check if membership has sufficient quota
        if membership.plan_quota_mode == 'unlimited':
            return True
        elif membership.plan_quota_mode == 'bucket_counts':
            if self.club_type == 'regular_offline' and membership.remaining_offline <= 0:
                return False
            elif self.club_type == 'regular_online' and membership.remaining_online <= 0:
                return False
            elif self.club_type == 'spclub' and membership.remaining_sp <= 0:
                return False
        elif membership.plan_quota_mode == 'points':
            # Get points from membership plan
            plan = membership.membership_plan_id
            if self.club_type == 'regular_offline':
                points_needed = plan.points_per_offline
            elif self.club_type == 'regular_online':
                points_needed = plan.points_per_online
            elif self.club_type == 'spclub':
                points_needed = plan.points_per_sp
            else:
                points_needed = 0
            
            if membership.points_remaining < points_needed:
                return False
        
        return True

    def can_cancel_registration(self, registration):
        """Check if a registration can be cancelled based on the cancellation deadline"""
        self.ensure_one()
        
        if not self.date_begin or not registration:
            return False
        
        # Check if the event has already started
        now = fields.Datetime.now()
        if now >= self.date_begin:
            return False
        
        # Calculate the cancellation deadline
        cancellation_deadline = self.date_begin - timedelta(hours=self.cancellation_deadline_hours or 24)
        
        # Check if current time is before the cancellation deadline
        return now < cancellation_deadline
    
    def promote_waitlist_registrations(self):
        """Manually promote waitlist registrations if seats become available"""
        for event in self:
            if not event.seats_limited:
                continue
            
            # Calculate how many spots are available
            confirmed_registrations = event.registration_ids.filtered(
                lambda r: r.state in ['open', 'confirmed', 'done'] and not r.is_on_waitlist
            )
            available_spots = max(0, event.seats_max - len(confirmed_registrations))
            
            # Promote waitlist registrations up to available spots
            waitlist_registrations = event.registration_ids.filtered(
                lambda r: r.is_on_waitlist and r.state == 'draft'
            ).sorted('waitlist_position')
            
            for i, reg in enumerate(waitlist_registrations[:available_spots]):
                reg.write({
                    'is_on_waitlist': False,
                    'waitlist_position': 0,
                    'state': 'open'
                })
                
                # Consume membership quota
                if reg.membership_id and reg.consumption_state == 'pending':
                    reg._consume_membership_quota()
                
                # Log the promotion
                try:
                    if reg and reg.exists():
                        reg.message_post(
                            body=_('Promoted from waitlist to confirmed registration')
                        )
                except Exception as e:
                    _logger.warning(f"Could not post message to registration {reg.id}: {e}")
                    # Continue processing even if message posting fails
            
            # Update remaining waitlist positions
            if waitlist_registrations:
                remaining_waitlist = waitlist_registrations[available_spots:]
                for i, reg in enumerate(remaining_waitlist, 1):
                    reg.write({'waitlist_position': i})
    
    def _auto_promote_waitlist(self):
        """Automatically promote waitlist registrations when seats become available"""
        self.ensure_one()
        
        if not self.seats_limited or self.seats_available <= 0:
            _logger.info(f"Event {self.id}: No auto-promotion needed (seats_limited={self.seats_limited}, seats_available={self.seats_available})")
            return
        
        # Get waitlist registrations in order
        waitlist_registrations = self.registration_ids.filtered(
            lambda r: r.is_on_waitlist and r.state == 'draft'
        ).sorted('waitlist_position')
        
        # Promote up to the number of available seats
        promotions_needed = min(self.seats_available, len(waitlist_registrations))
        
        _logger.info(f"Event {self.id}: Found {len(waitlist_registrations)} waitlist registrations, promoting {promotions_needed}")
        
        for i in range(promotions_needed):
            reg = waitlist_registrations[i]
            reg.write({
                'is_on_waitlist': False,
                'waitlist_position': 0,
                'state': 'open'
            })
            
            # Consume membership quota
            if reg.membership_id and reg.consumption_state == 'pending':
                reg._consume_membership_quota()
            
            # Log the promotion
            try:
                if reg and reg.exists():
                    reg.message_post(
                        body=_('Automatically promoted from waitlist to confirmed registration')
                    )
            except Exception as e:
                _logger.warning(f"Could not post message to registration {reg.id}: {e}")
                # Continue processing even if message posting fails
        
        # Update remaining waitlist positions
        if promotions_needed > 0:
            remaining_waitlist = waitlist_registrations[promotions_needed:]
            for i, reg in enumerate(remaining_waitlist, 1):
                reg.write({'waitlist_position': i})
    
    @api.model
    def _search_get_detail(self, website, order, options):
        """Override to add host search functionality"""
        # Get the base search detail from the parent method
        search_detail = super()._search_get_detail(website, order, options)
        
        # Add host search field to search_fields
        if 'search_fields' in search_detail:
            search_detail['search_fields'].append('host_search_name')
        
        # Add host field to fetch_fields
        if 'fetch_fields' in search_detail:
            search_detail['fetch_fields'].append('host_search_name')
        
        # Add host mapping
        if 'mapping' in search_detail:
            search_detail['mapping']['host'] = {
                'name': 'host_search_name', 
                'type': 'text', 
                'match': True
            }
        
        return search_detail
    
    @api.depends('seats_limited', 'seats_max', 'registration_ids', 'registration_ids.state')
    def _compute_seat_availability(self):
        """Compute seat availability based on seats_limited and registrations"""
        for event in self:
            if not event.seats_limited:
                # If seats are not limited, show unlimited
                event.seats_available = -1  # -1 means unlimited
                event.seats_taken = 0
            else:
                # Count confirmed registrations (excluding cancelled and draft)
                confirmed_registrations = event.registration_ids.filtered(
                    lambda r: r.state in ['open', 'confirmed', 'done'] and not r.is_on_waitlist
                )
                event.seats_taken = len(confirmed_registrations)
                event.seats_available = max(0, event.seats_max - event.seats_taken)
                
                # Auto-promote waitlist registrations if seats become available
                if event.seats_available > 0:
                    _logger.info(f"Auto-promoting waitlist for event {event.id}: {event.seats_available} seats available")
                    event._auto_promote_waitlist()
    
    @api.depends('registration_ids', 'registration_ids.is_on_waitlist')
    def _compute_waitlist_info(self):
        """Compute waitlist count"""
        for event in self:
            waitlist_registrations = event.registration_ids.filtered('is_on_waitlist')
            event.waitlist_count = len(waitlist_registrations)
    
    @api.depends('registration_ids', 'registration_ids.partner_id', 'registration_ids.is_on_waitlist')
    def _compute_user_waitlist_position(self):
        """Compute current user's waitlist position"""
        for event in self:
            event.user_waitlist_position = 0
            
            # Only compute for logged-in users
            if hasattr(self.env, 'user') and self.env.user and self.env.user.partner_id:
                user_partner = self.env.user.partner_id
                
                # Find user's waitlist registration
                user_waitlist_reg = event.registration_ids.filtered(
                    lambda r: r.partner_id == user_partner and r.is_on_waitlist
                )
                
                if user_waitlist_reg:
                    # Count registrations before this user on the waitlist
                    all_waitlist_regs = event.registration_ids.filtered(
                        lambda r: r.is_on_waitlist
                    ).sorted('waitlist_position')
                    
                    for i, reg in enumerate(all_waitlist_regs, 1):
                        if reg.partner_id == user_partner:
                            event.user_waitlist_position = i
                            break
    
    @api.depends('registration_ids', 'registration_ids.partner_id', 'registration_ids.state')
    def _compute_has_conflicting_registration(self):
        """Check if current user has conflicting registrations for overlapping events"""
        for event in self:
            event.has_conflicting_registration = False
            event.conflicting_event = False
            
            # Only check for logged-in users
            if request and request.env.user and request.env.user.id != request.env.ref('base.public_user').id:
                current_user_partner = request.env.user.partner_id
                
                # Check if current user has any registrations for events that overlap with this event
                if event.date_begin and event.date_end:
                    # Find all events where the user has ACTIVE registrations that overlap with this event's time
                    # First, find all active registrations for this user
                    active_registrations = request.env['event.registration'].search([
                        ('partner_id', '=', current_user_partner.id),
                        ('state', 'in', ['open', 'done'])  # Only active registrations
                    ])
                    
                    # Get the event IDs from these active registrations
                    active_event_ids = active_registrations.mapped('event_id.id')
                    
                    # Now find events that overlap in time with the current event
                    overlapping_events = request.env['event.event'].search([
                        ('id', '!=', event.id),  # Exclude current event
                        ('id', 'in', active_event_ids),  # Only events where user has active registrations
                        ('website_published', '=', True),
                        ('date_begin', '<', event.date_end),  # Other event starts before this one ends
                        ('date_end', '>', event.date_begin),  # Other event ends after this one starts
                    ])
                    
                    if overlapping_events:
                        event.has_conflicting_registration = True
                        event.conflicting_event = overlapping_events[0]  # Show the first conflicting event
    
    
    def action_mark_as_ended(self):
        """Mark this event as ended"""
        self.ensure_one()
        # Find the "Ended" stage
        ended_stage = self.env['event.stage'].search([('name', '=', 'Ended')], limit=1)
        if ended_stage:
            self.write({'stage_id': ended_stage.id})
            self.message_post(
                body=_('Event automatically marked as ended 15 minutes after completion')
            )
        else:
            _logger.warning('Could not find "Ended" stage for event')
        return True
    
    @api.model
    def _auto_mark_ended_events(self):
        """Automatically mark events as ended 15 minutes after they finish"""
        now = fields.Datetime.now()
        
        # Find events that ended 15 minutes ago but are not yet marked as done
        cutoff_time = now - timedelta(minutes=15)
        
        # Search for events that:
        # 1. Have an end date
        # 2. Ended at least 15 minutes ago
        # 3. Are not already in the "Ended" stage
        events_to_end = self.search([
            ('date_end', '!=', False),
            ('date_end', '<=', cutoff_time),
            ('stage_id.name', '!=', 'Ended')
        ])
        
        if events_to_end:
            # Find the "Ended" stage
            ended_stage = self.env['event.stage'].search([('name', '=', 'Ended')], limit=1)
            if ended_stage:
                # Mark all found events as ended
                events_to_end.write({'stage_id': ended_stage.id})
                
                # Log the action for each event
                for event in events_to_end:
                    event.message_post(
                        body=_('Event automatically marked as ended 15 minutes after completion')
                    )
                
                _logger.info(f'Automatically marked {len(events_to_end)} events as ended')
            else:
                _logger.warning('Could not find "Ended" stage for events')
        
        return len(events_to_end)
    
    def write(self, vals):
        """Override write to handle automatic staff registration when event is published"""
        result = super().write(vals)
        
        # Check if the event is being published or if it's already published
        if 'is_published' in vals and vals['is_published']:
            for event in self:
                event._auto_register_staff_members()
        elif 'is_published' not in vals:
            # If is_published is not being changed, check if event is already published
            for event in self:
                if event.is_published:
                    event._auto_register_staff_members()
        
        return result
    
    def _auto_register_staff_members(self):
        """Automatically register all staff members for this event"""
        if not self.exists():
            return
            
        # Find all staff members
        staff_members = self.env['res.partner'].search([
            ('book_club_automatically', '=', True),
            ('active', '=', True)
        ])
        
        if not staff_members:
            _logger.info(f'No contacts with automatic booking enabled found for event {self.name}')
            return
        
        registrations_created = 0
        for staff in staff_members:
            # Check if staff member is already registered for this event
            existing_registration = self.env['event.registration'].search([
                ('event_id', '=', self.id),
                ('partner_id', '=', staff.id)
            ], limit=1)
            
            if not existing_registration:
                try:
                    # Create registration for staff member
                    self.env['event.registration'].create({
                        'event_id': self.id,
                        'partner_id': staff.id,
                        'name': staff.name,
                        'email': staff.email,
                        'phone': staff.phone,
                        'state': 'open',  # Automatically confirmed
                        'is_auto_booked': True,  # Mark as auto-booked registration
                    })
                    registrations_created += 1
                    _logger.info(f'Automatically registered contact {staff.name} for event {self.name}')
                except Exception as e:
                    _logger.error(f'Failed to register contact {staff.name} for event {self.name}: {str(e)}')
        
        if registrations_created > 0:
            self.message_post(
                body=_('Automatically registered %d contacts for this event.') % registrations_created
            )
            _logger.info(f'Automatically registered {registrations_created} contacts for event {self.name}')