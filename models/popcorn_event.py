from odoo import models, fields, api
import logging
from datetime import timedelta


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
        """Override write to automatically set is_host field when host is assigned"""
        result = super().write(vals)
        
        # If host_id is being set, mark the partner as a host
        if 'host_id' in vals and vals['host_id']:
            host_partner = self.env['res.partner'].browse(vals['host_id'])
            host_partner.is_host = True
            
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
