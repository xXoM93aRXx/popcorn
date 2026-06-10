# -*- coding: utf-8 -*-

import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)

class PopcornEventRegistration(models.Model):
    """Extends event registration with Popcorn Club specific logic"""
    _inherit = 'event.registration'
    
    # Club type field (computed from event)
    club_type = fields.Selection([
        ('regular_offline', 'Regular Offline'),
        ('regular_online', 'Regular Online'),
        ('spclub', 'Special Club'),
        ('social_experience', 'Social Experience'),
        ('free_for_members', 'Free for Members'),
    ], string='Club Type', compute='_compute_club_type', store=True)
    
    # Membership consumption
    membership_id = fields.Many2one('popcorn.membership', string='Membership Used', 
                                   domain="[('partner_id', '=', partner_id), ('state', 'in', ['active', 'frozen'])]")
    consumption_state = fields.Selection([
        ('pending', 'Pending'),
        ('consumed', 'Consumed'),
        ('cancelled', 'Cancelled')
    ], string='Consumption State', default='pending', tracking=True)
    
    # Points consumed (for points-based plans)
    points_consumed = fields.Integer(string='Points Consumed', compute='_compute_points_consumed', store=True)
    
    # Track if this registration was imported (not created through normal flow)
    is_imported = fields.Boolean(string='Imported Registration', default=False)
    
    # Waitlist functionality
    is_on_waitlist = fields.Boolean(string='On Waitlist', default=False)
    waitlist_position = fields.Integer(string='Waitlist Position', default=0)
    
    # Waitlist promotion tracking
    pending_wechat_notification = fields.Boolean(
        string='Pending WeChat Notification',
        default=False,
        help='Indicates if WeChat notification should be sent for this promotion'
    )
    
    # Computed field to check if cancellation is allowed
    can_cancel = fields.Boolean(string='Can Cancel', compute='_compute_can_cancel', store=False)
    
    # Staff registration field
    is_auto_booked = fields.Boolean(string='Auto Booked', default=False, 
                                   help='Indicates if this registration was automatically created for a contact with auto-booking enabled')
    
    # Referral tracking
    referral_id = fields.Many2one('popcorn.referral', string='Referral', 
                                 help='Referral that led to this registration')
    
    # Direct payment tracking
    payment_amount = fields.Float(
        string='Payment Amount',
        digits='Product Price',
        help='Amount paid for direct club registration (without membership)'
    )
    payment_transaction_id = fields.Many2one(
        'payment.transaction',
        string='Payment Transaction',
        readonly=True,
        help='Payment transaction for this registration (for single club purchases)'
    )
    
    # Computed fields for registration desk
    event_host = fields.Char(string='Host', related='event_id.host_id.name', readonly=True, store=True)
    event_start_time = fields.Datetime(string='Club Start Time', related='event_id.date_begin', readonly=True, store=True)
    is_late_attendance = fields.Boolean(
        string='Late Attendance',
        default=False,
        tracking=True,
        copy=False,
        help='Indicates this attendee arrived late at the registration desk.'
    )
    is_no_show_attendance = fields.Boolean(
        string='No Show',
        default=False,
        tracking=True,
        copy=False,
        help='Indicates this attendee did not show up.'
    )
    late_attendance_badge = fields.Char(
        string='Late',
        compute='_compute_late_attendance_badge',
        store=False
    )
    no_show_attendance_badge = fields.Char(
        string='No Show',
        compute='_compute_no_show_attendance_badge',
        store=False
    )
    late_no_show_incident = fields.Boolean(
        string='Late/No-show Incident',
        default=False,
        copy=False,
        help='Internal flag for attendance policy counting (late or no-show incident).'
    )
    late_no_show_incident_date = fields.Datetime(
        string='Late/No-show Incident Date',
        copy=False
    )
    quota_penalty_violation = fields.Boolean(
        string='Quota Penalty Violation',
        default=False,
        copy=False,
        help='Internal marker for bucket/points attendance penalty policy.'
    )
    quota_penalty_violation_date = fields.Datetime(
        string='Quota Penalty Violation Date',
        copy=False
    )
    quota_penalty_incident_type = fields.Selection([
        ('late', 'Late Attendance'),
        ('no_show', 'No Show'),
        ('cancel_window', 'Cancellation Window'),
    ], string='Quota Penalty Incident Type', copy=False)
    quota_penalty_applied = fields.Boolean(
        string='Quota Penalty Applied',
        default=False,
        copy=False,
        help='Whether quota/points penalty adjustment has already been applied for this registration.'
    )
    
    # Computed fields for notifications
    hours_until_event = fields.Float(string='Hours Until Event', compute='_compute_hours_until_event', store=False)
    event_name = fields.Char(string='Event Name', related='event_id.name', readonly=True)
    event_chinese_name = fields.Char(string='Event Chinese Name', related='event_id.event_chinese_name', readonly=True)
    event_venue_name = fields.Char(string='Venue Name', related='event_id.address_id.name', readonly=True)
    event_time_formatted = fields.Char(string='Event Time', compute='_compute_event_time_formatted', store=False)
    event_time_wechat = fields.Char(string='Event Time (WeChat)', compute='_compute_event_time_wechat', store=False, 
                                    help='Event time in 24-hour format (HH:mm) for WeChat template messages')
    event_datetime_wechat = fields.Char(string='Event Date and Time (WeChat)', compute='_compute_event_datetime_wechat', store=False,
                                        help='Event date and time formatted for WeChat (YYYY-MM-DD HH:mm format)')
    
    def _compute_hours_until_event(self):
        """Compute hours until event starts"""
        now = fields.Datetime.now()
        for registration in self:
            if registration.event_id and registration.event_id.date_begin:
                delta = registration.event_id.date_begin - now
                registration.hours_until_event = delta.total_seconds() / 3600
            else:
                registration.hours_until_event = 0
    
    def _compute_event_time_formatted(self):
        """Format event time for display in user's timezone"""
        for registration in self:
            if registration.event_id and registration.event_id.date_begin:
                try:
                    # Use Odoo's datetime context utilities for proper timezone handling
                    # This ensures the time is displayed in the correct timezone for the notification context
                    from odoo import fields
                    import pytz
                    from datetime import datetime
                    
                    # Get the datetime field value (always stored in UTC in Odoo)
                    date_begin = registration.event_id.date_begin
                    
                    # Get timezone - prefer context, then user's tz, then partner's tz
                    tz = (self._context.get('tz') or 
                          (self.env.user.tz if self.env and self.env.user else None) or
                          (registration.partner_id.tz if registration.partner_id else None) or
                          'UTC')
                    
                    # If timezone-naive, localize to UTC (Odoo stores as naive UTC)
                    if isinstance(date_begin, datetime):
                        if date_begin.tzinfo is None:
                            # Odoo stores datetimes as naive in UTC
                            date_begin = pytz.UTC.localize(date_begin)
                        
                        # Convert to target timezone
                        target_tz = pytz.timezone(tz)
                        local_time = date_begin.astimezone(target_tz)
                        
                        # Format as "HH:MM AM/PM"
                        registration.event_time_formatted = local_time.strftime('%I:%M %p')
                    else:
                        registration.event_time_formatted = ''
                except Exception as e:
                    _logger.error(f"Error formatting event_time_formatted for registration {registration.id}: {e}", exc_info=True)
                    registration.event_time_formatted = ''
            else:
                registration.event_time_formatted = ''
    
    def _compute_event_time_wechat(self):
        """Format event time in 24-hour format (HH:mm) for WeChat template messages"""
        for registration in self:
            if registration.event_id and registration.event_id.date_begin:
                try:
                    from odoo import fields
                    import pytz
                    from datetime import datetime
                    
                    # Get the datetime field value (always stored in UTC in Odoo)
                    date_begin = registration.event_id.date_begin
                    
                    # Get timezone - prefer context, then user's tz, then partner's tz
                    tz = (self._context.get('tz') or 
                          (self.env.user.tz if self.env and self.env.user else None) or
                          (registration.partner_id.tz if registration.partner_id else None) or
                          'UTC')
                    
                    # If timezone-naive, localize to UTC (Odoo stores as naive UTC)
                    if isinstance(date_begin, datetime):
                        if date_begin.tzinfo is None:
                            # Odoo stores datetimes as naive in UTC
                            date_begin = pytz.UTC.localize(date_begin)
                        
                        # Convert to target timezone
                        target_tz = pytz.timezone(tz)
                        local_time = date_begin.astimezone(target_tz)
                        
                        # Format as "HH:MM" (24-hour format) for WeChat
                        registration.event_time_wechat = local_time.strftime('%H:%M')
                    else:
                        registration.event_time_wechat = ''
                except Exception as e:
                    _logger.error(f"Error formatting event_time_wechat for registration {registration.id}: {e}", exc_info=True)
                    registration.event_time_wechat = ''
            else:
                registration.event_time_wechat = ''
    
    def _compute_event_datetime_wechat(self):
        """Format event date and time for WeChat template messages (YYYY-MM-DD HH:mm format)"""
        for registration in self:
            if registration.event_id and registration.event_id.date_begin:
                try:
                    import pytz
                    from datetime import datetime
                    
                    date_begin = registration.event_id.date_begin
                    
                    # Get timezone - prefer context, then user's tz, then partner's tz
                    tz = (self._context.get('tz') or 
                          (self.env.user.tz if self.env and self.env.user else None) or
                          (registration.partner_id.tz if registration.partner_id else None) or
                          'UTC')
                    
                    # If timezone-naive, localize to UTC (Odoo stores as naive UTC)
                    if isinstance(date_begin, datetime):
                        if date_begin.tzinfo is None:
                            date_begin = pytz.UTC.localize(date_begin)
                        
                        # Convert to target timezone
                        target_tz = pytz.timezone(tz)
                        local_time = date_begin.astimezone(target_tz)
                        
                        # Format as "YYYY-MM-DD HH:mm" (WeChat compatible format)
                        registration.event_datetime_wechat = local_time.strftime('%Y-%m-%d %H:%M')
                    else:
                        registration.event_datetime_wechat = ''
                except Exception as e:
                    _logger.error(f"Error formatting event_datetime_wechat for registration {registration.id}: {e}", exc_info=True)
                    registration.event_datetime_wechat = ''
            else:
                registration.event_datetime_wechat = ''

    @api.depends('is_late_attendance')
    def _compute_late_attendance_badge(self):
        for registration in self:
            registration.late_attendance_badge = 'Late' if registration.is_late_attendance else ''

    @api.depends('is_no_show_attendance')
    def _compute_no_show_attendance_badge(self):
        for registration in self:
            registration.no_show_attendance_badge = 'No Show' if registration.is_no_show_attendance else ''
    
    @api.depends('event_id.tag_ids')
    def _compute_club_type(self):
        """Compute club type from the event's Type tag"""
        for registration in self:
            _logger.info(f"[SOCIAL_EXPERIENCE_DEBUG] _compute_club_type called for registration {registration.id}")
            if registration.event_id and registration.event_id.tag_ids:
                # Look at all tags with category "Type" to determine club type
                type_tags = registration.event_id.tag_ids.filtered(
                    lambda tag: tag.category_id.name == 'Type'
                )
                if type_tags:
                    tag_names = [tag.name.lower() for tag in type_tags]
                    _logger.info(f"[SOCIAL_EXPERIENCE_DEBUG] Found type tags: {tag_names}")
                    # Free for Members wins when mixed with other Type tags
                    if any('free' in name for name in tag_names):
                        registration.club_type = 'free_for_members'
                    elif any('social' in name and 'experience' in name for name in tag_names):
                        registration.club_type = 'social_experience'
                        _logger.info(f"[SOCIAL_EXPERIENCE_DEBUG] Setting club_type to 'social_experience'")
                    elif any('sp' in name or 'special' in name for name in tag_names):
                        registration.club_type = 'spclub'
                    elif any('offline' in name for name in tag_names):
                        registration.club_type = 'regular_offline'
                    elif any('online' in name for name in tag_names):
                        registration.club_type = 'regular_online'
                    else:
                        registration.club_type = False
                else:
                    _logger.info(f"[SOCIAL_EXPERIENCE_DEBUG] No type tag found, using fallback")
                    # Fallback: determine from event properties
                    if hasattr(registration.event_id, 'is_online_event') and registration.event_id.is_online_event:
                        registration.club_type = 'regular_online'
                    else:
                        registration.club_type = 'regular_offline'
            else:
                # Default to offline if no tags
                registration.club_type = 'regular_offline'
                _logger.info(f"[SOCIAL_EXPERIENCE_DEBUG] No event_id or tag_ids, defaulting to 'regular_offline'")
            _logger.info(f"[SOCIAL_EXPERIENCE_DEBUG] Final club_type: {registration.club_type}")
    
    @api.depends(
        'club_type',
        'membership_id',
        'membership_id.membership_plan_id',
        'membership_id.membership_plan_id.points_per_offline',
        'membership_id.membership_plan_id.points_per_online',
        'membership_id.membership_plan_id.points_per_sp',
        'membership_id.membership_plan_id.points_per_social_experience',
    )
    def _compute_points_consumed(self):
        """Compute points consumed based on club type"""
        for registration in self:
            if not registration.club_type:
                registration.points_consumed = 0
                continue
            
            # Get points from membership plan if available
            if registration.membership_id and registration.membership_id.membership_plan_id:
                plan = registration.membership_id.membership_plan_id
                if registration.club_type == 'social_experience':
                    registration.points_consumed = plan.points_per_social_experience
                elif registration.club_type == 'regular_offline':
                    registration.points_consumed = plan.points_per_offline
                elif registration.club_type == 'regular_online':
                    registration.points_consumed = plan.points_per_online
                elif registration.club_type == 'spclub':
                    registration.points_consumed = plan.points_per_sp
                else:
                    registration.points_consumed = 0
            else:
                # Fallback to default values if no membership plan
                if registration.club_type == 'regular_offline':
                    registration.points_consumed = 3
                elif registration.club_type == 'regular_online':
                    registration.points_consumed = 2
                elif registration.club_type == 'spclub':
                    registration.points_consumed = 6
                else:
                    registration.points_consumed = 0
    
    @api.depends('event_id', 'event_id.date_begin', 'event_id.cancellation_deadline_hours')
    def _compute_can_cancel(self):
        """Compute whether this registration can be cancelled"""
        for registration in self:
            if not registration.event_id or not registration.event_id.date_begin:
                registration.can_cancel = False
                continue
            
            # Check if the event has already started
            now = fields.Datetime.now()
            if now >= registration.event_id.date_begin:
                registration.can_cancel = False
                continue
            
            # Calculate the cancellation deadline
            cancellation_deadline = registration.event_id.date_begin - timedelta(
                hours=registration.event_id.cancellation_deadline_hours or 24
            )
            
            # Check if current time is before the cancellation deadline
            registration.can_cancel = now < cancellation_deadline
    
    @api.constrains('membership_id', 'partner_id')
    def _check_membership_partner(self):
        """Ensure membership belongs to the registration partner"""
        for registration in self:
            if registration.membership_id and registration.membership_id.partner_id != registration.partner_id:
                raise ValidationError(_('Membership must belong to the registration partner'))
    

    
    def _events_overlap(self, event1, event2):
        """Check if two events overlap in time"""
        if not event1.date_begin or not event1.date_end or not event2.date_begin or not event2.date_end:
            return False
            
        # Events overlap if one starts before the other ends
        return (event1.date_begin < event2.date_end and event2.date_begin < event1.date_end)
    
    @api.constrains('membership_id', 'event_id')
    def _check_membership_event_compatibility(self):
        """Ensure membership plan allows this club type"""
        for registration in self:
            if registration.membership_id and registration.event_id:
                membership = registration.membership_id
                
                # Use the computed club_type field
                club_type = registration.club_type
                
                if club_type == 'regular_offline' and not membership.plan_allowed_regular_offline:
                    raise ValidationError(_('This membership plan does not allow regular offline events'))
                elif club_type == 'regular_online' and not membership.plan_allowed_regular_online:
                    raise ValidationError(_('This membership plan does not allow regular online events'))
                elif club_type == 'spclub' and not membership.plan_allowed_spclub:
                    raise ValidationError(_('This membership plan does not allow special club events'))
    
    @api.onchange('partner_id', 'event_id')
    def _onchange_partner_event(self):
        """Automatically select appropriate membership when partner or event changes"""
        if self.partner_id and self.event_id and self.club_type:
            # Find the best available membership for this event
            best_membership = self._find_best_membership()
            if best_membership:
                self.membership_id = best_membership
    
    def _find_best_membership(self):
        """Find the best available membership for this event"""
        if not self.partner_id or not self.event_id or not self.club_type:
            return False
        
        # Get all active memberships for this partner
        memberships = self.env['popcorn.membership'].search([
            ('partner_id', '=', self.partner_id.id),
            ('state', 'in', ['active', 'frozen'])
        ])
        
        if not memberships:
            return False
        
        # Filter memberships that allow this club type
        compatible_memberships = []
        for membership in memberships:
            if self._is_membership_compatible(membership):
                compatible_memberships.append(membership)
        
        if not compatible_memberships:
            return False
        
        # Sort by priority: unlimited > points > bucket_counts
        # For same type, prefer longer duration
        compatible_memberships.sort(key=lambda m: (
            self._get_quota_mode_priority(m.plan_quota_mode),
            m.plan_duration_days or 0
        ), reverse=True)
        
        # Return the best match
        return compatible_memberships[0] if compatible_memberships else False
    
    def _is_membership_compatible(self, membership):
        """Check if membership is compatible with this event"""
        if not membership or not self.club_type:
            return False
        
        # Check if membership is frozen during event date
        if self._is_membership_frozen_during_event(membership):
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
            if membership.points_remaining < self.points_consumed:
                return False

        return True

    def _is_membership_frozen_during_event(self, membership):
        """Check if membership is frozen during the event date"""
        if not membership or not self.event_id or not self.event_id.date_begin:
            return False
        
        # If membership is not frozen, it's not frozen during event
        if not membership.freeze_active:
            return False
        
        # Get event date
        event_date = self.event_id.date_begin.date()
        
        # Check if event date falls within freeze period
        if membership.freeze_start and membership.freeze_end:
            return membership.freeze_start <= event_date < membership.freeze_end
        
        return False
    
    def _get_quota_mode_priority(self, quota_mode):
        """Get priority for quota mode (higher number = higher priority)"""
        priority_map = {
            'unlimited': 3,
            'points': 2,
            'bucket_counts': 1
        }
        return priority_map.get(quota_mode, 0)
    
    def action_consume_membership(self):
        """Manually consume membership quota for this registration (legacy method)"""
        self.ensure_one()
        
        if not self.membership_id:
            raise UserError(_('No membership selected for consumption'))
        
        if self.consumption_state != 'pending':
            raise UserError(_('Registration is not in pending state for consumption'))
        
        # Use the automatic consumption method
        self._consume_membership_quota()
        
        return True
    
    def _can_consume_membership(self):
        """Check if membership has sufficient quota for this event"""
        self.ensure_one()

        if not self.membership_id:
            return False

        # Free-for-members events consume no quota — any active membership qualifies
        if self.club_type == 'free_for_members':
            return True

        membership = self.membership_id

        if membership.plan_quota_mode == 'unlimited':
            return True
        elif membership.plan_quota_mode == 'bucket_counts':
            return self._can_consume_bucket_quota()
        elif membership.plan_quota_mode == 'points':
            return self._can_consume_points_quota()
        
        return False
    
    def _can_consume_bucket_quota(self):
        """Check if bucket-based membership has sufficient quota"""
        self.ensure_one()
        membership = self.membership_id
        
        if self.club_type == 'regular_offline':
            return membership.remaining_offline >= 1
        elif self.club_type == 'regular_online':
            return membership.remaining_online >= 1
        elif self.club_type == 'spclub':
            return membership.remaining_sp >= 1
        elif self.club_type == 'social_experience':
            # Bucket-based memberships don't support social_experience events
            return False
        
        return False
    
    def _can_consume_points_quota(self):
        """Check if points-based membership has sufficient quota"""
        self.ensure_one()
        membership = self.membership_id
        
        return membership.points_remaining >= self.points_consumed
    

    
    def action_cancel_consumption(self):
        """Cancel membership consumption for this registration"""
        self.ensure_one()
        
        if self.consumption_state != 'consumed':
            raise UserError(_('Registration is not in consumed state'))
        
        # Mark as cancelled
        self.write({
            'consumption_state': 'cancelled'
        })
        
        return True

    def action_cancel_registration(self):
        """Cancel the registration and restore membership quota if applicable"""
        self.ensure_one()
        
        _logger.info(f"=== Portal Cancellation: Registration {self.id} for event {self.event_id.name} (ID: {self.event_id.id}) ===")
        _logger.info(f"Partner: {self.partner_id.name} (ID: {self.partner_id.id})")
        _logger.info(f"Current state: {self.state}, is_on_waitlist: {self.is_on_waitlist}")
        
        # Check if cancellation is allowed
        if not self.event_id.can_cancel_registration(self):
            raise UserError(_('Cancellation is not allowed at this time. Please check the event cancellation deadline.'))
        
        # Check if registration is in a cancellable state
        if self.state not in ['open', 'confirmed', 'draft']:
            raise UserError(_('Registration cannot be cancelled in its current state'))
        
        # Handle waitlist registrations (draft state) differently - just delete them
        if self.state == 'draft' and self.is_on_waitlist:
            event_id = self.event_id

            # Quota is consumed at waitlist-join time, so restore it on cancellation.
            # _restore_membership_quota posts a log message to the membership record.
            if self.membership_id and self.consumption_state == 'consumed':
                self._restore_membership_quota()

            # Log the cancellation before deletion
            self.message_post(
                body=_('Waitlist registration cancelled by portal user')
            )

            # Delete the waitlist registration, then renumber remaining positions
            # (positions must be renumbered after unlink so self is excluded).
            self.unlink()
            self._update_waitlist_positions_after_deletion(event_id)

            # No confirmed seat was freed — do NOT promote anyone from the waitlist.
            # Promotion only happens when an open/confirmed registration is cancelled.

            return True
        
        # Handle regular registrations (open/confirmed state)
        _logger.info(f"=== action_cancel_registration called for registration {self.id}, state={self.state}, is_on_waitlist={self.is_on_waitlist} ===")
        
        # If membership was consumed or pending, restore the quota
        if self.consumption_state in ['consumed', 'pending'] and self.membership_id:
            if self.consumption_state == 'consumed':
                if self._should_block_quota_refund_for_cancel_window():
                    self._apply_cancel_window_non_refund_penalty()
                    self.message_post(
                        body=_('Quota/points refund blocked due to repeated cancellation-window violations.')
                    )
                else:
                    self._restore_membership_quota()
            # If pending, just mark as cancelled (no quota to restore)
        
        # Handle automatic refund for single club purchases (not membership)
        _logger.info(f"Cancelling registration {self.id}: payment_transaction_id={self.payment_transaction_id.id if self.payment_transaction_id else None}, payment_amount={self.payment_amount}, membership_id={self.membership_id.id if self.membership_id else None}")
        
        if self.payment_transaction_id and self.payment_amount > 0 and not self.membership_id:
            _logger.info(f"Refund conditions met for registration {self.id}, initiating automatic refund")
            try:
                self._process_automatic_refund()
            except Exception as e:
                _logger.error(f"Failed to process automatic refund for registration {self.id}: {str(e)}")
                self.message_post(
                    body=_('Registration cancelled but automatic refund failed: %s. Please contact support for manual refund.') % str(e)
                )
        else:
            _logger.info(f"Refund not triggered for registration {self.id}: has_transaction={bool(self.payment_transaction_id)}, has_amount={self.payment_amount > 0}, has_membership={bool(self.membership_id)}")
        
        # Cancel the registration with context flag to prevent double promotion
        self.with_context(skip_waitlist_promotion=True).write({
            'state': 'cancel',
            'consumption_state': 'cancelled'
        })

        # Count cancellation incident for unlimited memberships.
        incident_type = self._get_cancellation_incident_type()
        if incident_type:
            self._apply_attendance_penalty_policy(incident_type)
        
        # Log the cancellation
        self.message_post(
            body=_('Registration cancelled by portal user')
        )
        
        # Promote next person from waitlist if event has limited seats
        if self.event_id.seats_limited:
            _logger.info(f"Event has limited seats, attempting to promote from waitlist...")
            # Use centralized promotion to handle concurrent cancellations
            self.event_id._promote_waitlist_safe()
        else:
            _logger.info(f"Event has unlimited seats, skipping waitlist promotion")
        
        return True
    
    def _promote_next_waitlist_registration(self):
        """Promote the next person from the waitlist when a spot becomes available"""
        self.ensure_one()
        
        _logger.info(f"--- Attempting waitlist promotion for event {self.event_id.name} (ID: {self.event_id.id}) ---")
        
        # Prevent concurrent promotions for the same event
        if self.env.context.get('promoting_waitlist'):
            _logger.info(f"Skipping promotion: already promoting (context flag is set)")
            return
        
        event = self.event_id
        
        # Check if there are actually available seats
        if not event.seats_limited:
            _logger.info(f"Skipping promotion: event has unlimited seats")
            return
        
        # Calculate current availability
        confirmed_registrations = event.registration_ids.filtered(
            lambda r: r.state in ['open', 'confirmed', 'done'] and not r.is_on_waitlist
        )
        available_seats = max(0, event.seats_max - len(confirmed_registrations))
        
        _logger.info(f"Current confirmed registrations: {len(confirmed_registrations)} / {event.seats_max}")
        _logger.info(f"Available seats: {available_seats}")
        
        if available_seats <= 0:
            _logger.info(f"No seats available for waitlist promotion")
            return
        
        # Find the next person on the waitlist (lowest position number)
        next_waitlist_reg = self.env['event.registration'].search([
            ('event_id', '=', event.id),
            ('is_on_waitlist', '=', True),
            ('state', '=', 'draft')
        ], order='waitlist_position asc', limit=1)
        
        if next_waitlist_reg:
            _logger.info(f"Promoting registration {next_waitlist_reg.id} - Partner: {next_waitlist_reg.partner_id.name} (waitlist position: {next_waitlist_reg.waitlist_position})")
            
            # Promote this registration with context flag to prevent re-entrancy
            next_waitlist_reg.with_context(promoting_waitlist=True).write({
                'is_on_waitlist': False,
                'waitlist_position': 0,
                'state': 'open',
                'pending_wechat_notification': True,
            })
            
            # Consume membership quota for the promoted registration
            if next_waitlist_reg.membership_id and next_waitlist_reg.consumption_state == 'pending':
                _logger.info(f"Consuming membership quota for promoted registration (membership: {next_waitlist_reg.membership_id.id})")
                next_waitlist_reg._consume_membership_quota()
            else:
                _logger.info(f"No quota consumption needed (membership_id: {next_waitlist_reg.membership_id.id if next_waitlist_reg.membership_id else None}, consumption_state: {next_waitlist_reg.consumption_state})")
            
            # Log the promotion
            next_waitlist_reg.message_post(
                body=_('Promoted from waitlist to confirmed registration')
            )
            
            # Update waitlist positions for remaining waitlist registrations
            self.with_context(promoting_waitlist=True)._update_waitlist_positions()
            _logger.info(f"Promotion completed successfully")
        else:
            _logger.info(f"No registrations found on waitlist to promote")
    
    def _update_waitlist_positions(self):
        """Update waitlist positions after a promotion"""
        self.ensure_one()
        
        # Get all remaining waitlist registrations
        remaining_waitlist = self.env['event.registration'].search([
            ('event_id', '=', self.event_id.id),
            ('is_on_waitlist', '=', True),
            ('state', '=', 'draft')
        ], order='waitlist_position asc')
        
        # Renumber positions starting from 1
        for i, reg in enumerate(remaining_waitlist, 1):
            reg.write({'waitlist_position': i})
    
    def _update_waitlist_positions_after_deletion(self, event_id):
        """Update waitlist positions after a waitlist registration is deleted"""
        # Get all remaining waitlist registrations
        remaining_waitlist = self.env['event.registration'].search([
            ('event_id', '=', event_id.id),
            ('is_on_waitlist', '=', True),
            ('state', '=', 'draft')
        ], order='waitlist_position asc')
        
        # Renumber positions starting from 1
        for i, reg in enumerate(remaining_waitlist, 1):
            reg.write({'waitlist_position': i})
    
    def _consume_membership_quota(self):
        """Automatically consume membership quota when registration is created"""
        self.ensure_one()
        
        _logger.info(f"[SOCIAL_EXPERIENCE_DEBUG] _consume_membership_quota called for registration {self.id}")
        _logger.info(f"[SOCIAL_EXPERIENCE_DEBUG] membership_id: {self.membership_id.id if self.membership_id else None}, consumption_state: {self.consumption_state}, club_type: {self.club_type}, points_consumed: {self.points_consumed}")
        
        if not self.membership_id or self.consumption_state != 'pending':
            _logger.info(f"[SOCIAL_EXPERIENCE_DEBUG] Skipping consumption - membership_id: {self.membership_id.id if self.membership_id else None}, consumption_state: {self.consumption_state}")
            return
        
        membership = self.membership_id
        _logger.info(f"[SOCIAL_EXPERIENCE_DEBUG] Membership quota_mode: {membership.plan_quota_mode}, points_remaining BEFORE: {membership.points_remaining}")
        
        # Check if membership has sufficient quota BEFORE consuming
        if not self._can_consume_membership():
            _logger.error(f"[SOCIAL_EXPERIENCE_DEBUG] Cannot consume membership - insufficient quota!")
            raise ValidationError(_('Insufficient membership quota for this event'))
        
        # Mark as consumed first
        self.write({
            'consumption_state': 'consumed'
        })
        
        _logger.info(f"[SOCIAL_EXPERIENCE_DEBUG] Consumption state set to 'consumed', points_remaining AFTER: {membership.points_remaining}")
        
        # Log the quota consumption
        membership.message_post(
            body=_('Quota consumed for event registration: %s') % self.event_id.name
        )
        
        # Note: Automatic expiration is now handled by cron job for reliability
    
    def _add_to_waitlist(self):
        """Add registration to waitlist and assign position with database-level locking"""
        self.ensure_one()
        
        if not self.event_id.seats_limited:
            return  # No waitlist if seats are unlimited
        
        # Use database-level locking to prevent race conditions when assigning positions
        # Lock the event record to prevent concurrent position assignments
        self.env.flush_all()
        
        # Lock the event record using FOR UPDATE pattern
        # This ensures only one transaction can assign waitlist positions at a time
        self.env.cr.execute(
            "SELECT id FROM event_event WHERE id = %s FOR UPDATE",
            [self.event_id.id]
        )
        
        # Refresh event to get latest data while holding lock
        self.event_id.invalidate_recordset()
        
        # Get current waitlist count while holding lock
        current_waitlist = self.env['event.registration'].search([
            ('event_id', '=', self.event_id.id),
            ('is_on_waitlist', '=', True)
        ], order='waitlist_position desc')
        
        # Assign next position
        next_position = (current_waitlist[0].waitlist_position + 1) if current_waitlist else 1
        
        self.write({
            'is_on_waitlist': True,
            'waitlist_position': next_position,
            'state': 'draft'  # Keep in draft state until promoted
        })
        
        # Log the waitlist addition
        self.message_post(
            body=_('Added to waitlist at position #%s') % next_position
        )
    
    def _restore_membership_quota(self):
        """Restore membership quota that was consumed by this registration"""
        self.ensure_one()
        
        if not self.membership_id or self.consumption_state != 'consumed':
            return
        
        membership = self.membership_id
        
        # Restore quota based on membership type
        if membership.plan_quota_mode == 'bucket_counts':
            if self.club_type == 'regular_offline':
                membership.remaining_offline += 1
            elif self.club_type == 'regular_online':
                membership.remaining_online += 1
            elif self.club_type == 'spclub':
                membership.remaining_sp += 1
        elif membership.plan_quota_mode == 'points':
            membership.points_remaining += self.points_consumed
        
        # Log the quota restoration
        membership.message_post(
            body=_('Quota restored due to cancellation of event: %s') % self.event_id.name
        )
    
    @api.model
    def create(self, vals):
        """Override create to set default values and validate membership"""
        # Set default consumption state if not provided
        if 'consumption_state' not in vals:
            vals['consumption_state'] = 'pending'
        
        # Check if this is an import/migration (no automatic consumption for imports)
        is_import = self._context.get('import_file') or self._context.get('from_import')
        
        # Mark as imported if this is an import
        if is_import:
            vals['is_imported'] = True
        
        # For limited-seat events, lock the event BEFORE creating registration to prevent deadlocks
        event = None
        should_lock = False
        if 'event_id' in vals:
            event = self.env['event.event'].browse(vals['event_id'])
            # Prevent duplicate bookings: block if an active (non-cancelled) registration already exists
            if event.exists() and not is_import and 'partner_id' in vals:
                duplicate = self.env['event.registration'].search([
                    ('event_id', '=', event.id),
                    ('partner_id', '=', vals['partner_id']),
                    ('state', '!=', 'cancel'),
                ], limit=1)
                if duplicate:
                    raise ValidationError(_(
                        'You are already registered for this event.'
                    ))
            if event.exists() and event.seats_limited and not is_import:
                should_lock = True
                # Lock the event FIRST before creating registration to prevent deadlocks
                # This ensures transactions process sequentially, not waiting on each other
                self.env.flush_all()
                self.env.cr.execute(
                    "SELECT id FROM event_event WHERE id = %s FOR UPDATE",
                    [event.id]
                )
                # Refresh event to get latest data while holding lock
                event.invalidate_recordset(['seats_max'])

                # Check availability BEFORE creating registration
                confirmed_registrations = self.env['event.registration'].search([
                    ('event_id', '=', event.id),
                    ('state', 'in', ['open', 'confirmed', 'done']),
                    ('is_on_waitlist', '=', False)
                ])
                available_seats = max(0, event.seats_max - len(confirmed_registrations))
                
                # Set initial state based on availability while holding lock
                if available_seats <= 0:
                    # No seats available - create as draft and add to waitlist
                    vals['state'] = 'draft'
                else:
                    # Seats available - create as open
                    if vals.get('state') != 'open':
                        vals['state'] = 'open'
        
        # Create the record (lock is still held if should_lock is True)
        registration = super().create(vals)
        
        # Flush the registration creation so other transactions see it when they get the lock
        if should_lock:
            self.env.flush_all()
        
        # Post-create validation and auto-selection
        if registration.partner_id and registration.event_id:
            registration._post_create_validation()
        
        # Handle waitlist and quota consumption for limited-seat events
        if not is_import and registration.event_id and should_lock:
            event = registration.event_id
            _logger.info(f"=== New Registration Created: ID {registration.id} for event {event.name} (ID: {event.id}) ===")
            _logger.info(f"Partner: {registration.partner_id.name} (ID: {registration.partner_id.id})")
            _logger.info(f"Has membership: {bool(registration.membership_id)}")
            
            # Re-check availability (we already checked, but verify while holding lock)
            confirmed_registrations = self.env['event.registration'].search([
                ('event_id', '=', event.id),
                ('state', 'in', ['open', 'confirmed', 'done']),
                ('is_on_waitlist', '=', False)
            ])
            available_seats = max(0, event.seats_max - len(confirmed_registrations))
            
            _logger.info(f"Event has limited seats: {len(confirmed_registrations)} / {event.seats_max} seats taken")
            _logger.info(f"Available seats: {available_seats}")
            
            if available_seats <= 0 and registration.state == 'draft':
                # No seats available - add to waitlist and consume quota immediately.
                # Consuming on join (rather than on promotion) means the quota is
                # actually reserved, preventing a user from stacking unlimited
                # waitlist entries against the same pool of points/sessions.
                _logger.info(f"No seats available - adding to waitlist")
                registration._add_to_waitlist()
                if registration.membership_id and registration.consumption_state == 'pending':
                    _logger.info(f"Consuming membership quota for waitlist registration")
                    registration._consume_membership_quota()
            elif registration.state == 'open':
                # Seats available - consume quota if membership exists
                if registration.membership_id and registration.consumption_state == 'pending':
                    _logger.info(f"[SOCIAL_EXPERIENCE_DEBUG] Registration state is 'open', consuming membership quota")
                    _logger.info(f"[SOCIAL_EXPERIENCE_DEBUG] Before consumption - club_type: {registration.club_type}, points_consumed: {registration.points_consumed}, membership points_remaining: {registration.membership_id.points_remaining}")
                    registration._consume_membership_quota()
                    _logger.info(f"[SOCIAL_EXPERIENCE_DEBUG] After consumption - membership points_remaining: {registration.membership_id.points_remaining}")
        elif not is_import and registration.event_id:
            # Unlimited seats - just consume quota if membership exists
            _logger.info(f"[SOCIAL_EXPERIENCE_DEBUG] Event has unlimited seats")
            if registration.membership_id and registration.consumption_state == 'pending':
                _logger.info(f"[SOCIAL_EXPERIENCE_DEBUG] Before consumption - club_type: {registration.club_type}, points_consumed: {registration.points_consumed}, membership points_remaining: {registration.membership_id.points_remaining}")
                registration._consume_membership_quota()
                _logger.info(f"[SOCIAL_EXPERIENCE_DEBUG] After consumption - membership points_remaining: {registration.membership_id.points_remaining}")
        
        # Note: Club registrations do NOT affect first-timer status
        # Only memberships affect is_first_timer (for membership pricing eligibility)
        # First-timer coupon usage for clubs is completely independent from membership pricing

        # PDB (Pitched Didn't Buy) logic: mark partner as PDB on their first offline registration
        if not is_import and registration.partner_id and not registration.partner_id.pdb:
            if registration.club_type == 'regular_offline':
                non_cancelled_count = self.env['event.registration'].search_count([
                    ('partner_id', '=', registration.partner_id.id),
                    ('state', '!=', 'cancel'),
                ])
                if non_cancelled_count == 1:
                    registration.partner_id.pdb = True
        
        # Clear UI caches to ensure fresh data
        registration.env['ir.ui.view'].clear_caches()
        
        # After creating registration, schedule overbooking correction to run after commit
        # This ensures we can see all committed registrations from concurrent transactions
        if not is_import and registration.event_id and registration.event_id.seats_limited:
            event_id = registration.event_id.id
            # Schedule correction to run after transaction commits
            # This allows us to see all committed registrations from concurrent transactions
            def correct_after_commit():
                try:
                    # Use a new cursor to see committed changes
                    with self.env.registry.cursor() as new_cr:
                        new_env = self.env(cr=new_cr)
                        event = new_env['event.event'].browse(event_id)
                        if event.exists():
                            event._correct_overbooking_single()
                            new_cr.commit()
                except Exception as e:
                    _logger.error(f"Error correcting overbooking for event {event_id} after commit: {e}")
            
            # Schedule to run after current transaction commits
            self.env.cr.postcommit.add(correct_after_commit)
        
        return registration
    
    def _post_create_validation(self):
        """Post-create validation and auto-selection"""
        self.ensure_one()
        
        # Auto-select membership if none selected
        if not self.membership_id and self.partner_id and self.event_id:
            best_membership = self._find_best_membership()
            if best_membership:
                self.membership_id = best_membership
        
        # Validate the registration
        self._validate_registration()
    
    def _validate_registration(self):
        """Validate the registration based on membership rules"""
        self.ensure_one()
        
        if not self.club_type:
            return  # No validation needed
        
        # If using membership, validate it
        if self.membership_id:
            # Check if membership is frozen during event
            if self._is_membership_frozen_during_event(self.membership_id):
                event_date = self.event_id.date_begin.date()
                raise ValidationError(_('Cannot book this event: Your membership is frozen from %s to %s. Event date: %s') % (
                    self.membership_id.freeze_start,
                    self.membership_id.freeze_end,
                    event_date
                ))
            
            if not self._is_membership_compatible(self.membership_id):
                raise ValidationError(_('Selected membership is not compatible with this event'))
            
            if not self._can_consume_membership():
                raise ValidationError(_('Insufficient membership quota for this event'))
    
    def write(self, vals):
        """Override write to handle state changes and validation"""
        # If changing consumption state to consumed, validate membership
        if vals.get('consumption_state') == 'consumed':
            for registration in self:
                if not registration._can_consume_membership():
                    raise UserError(_('Cannot consume membership: insufficient quota'))
        
        # If changing membership, validate compatibility
        if 'membership_id' in vals:
            for registration in self:
                if vals['membership_id']:
                    membership = self.env['popcorn.membership'].browse(vals['membership_id'])
                    if not registration._is_membership_compatible(membership):
                        raise ValidationError(_('Selected membership is not compatible with this event'))
        
        # Store original states and consumption states to check for cancellations
        original_states = {reg.id: reg.state for reg in self}
        original_consumption_states = {reg.id: reg.consumption_state for reg in self}
        # If cancelling from backend, also update consumption_state
        if 'state' in vals and vals['state'] == 'cancel' and not self._context.get('skip_waitlist_promotion'):
            vals['consumption_state'] = 'cancelled'
        
        result = super().write(vals)
        
        # Consume membership quota when draft registrations are confirmed
        if 'state' in vals:
            new_state = vals['state']
            for registration in self:
                original_state = original_states.get(registration.id)
                if (
                    original_state == 'draft'
                    and new_state in ['open', 'confirmed', 'done']
                    and registration.membership_id
                    and registration.consumption_state == 'pending'
                ):
                    registration._consume_membership_quota()

        # Post-write validation
        for registration in self:
            if registration.partner_id and registration.event_id:
                registration._validate_registration()

        # Count cancellation incidents for unlimited memberships regardless
        # of waitlist-promotion context.
        if 'state' in vals and vals['state'] == 'cancel':
            for registration in self:
                original_state = original_states.get(registration.id)
                if original_state in ['open', 'confirmed']:
                    incident_type = registration._get_cancellation_incident_type()
                    if incident_type:
                        registration._apply_attendance_penalty_policy(incident_type)
        
        # Handle state changes for waitlist promotion and quota restoration
        # Only promote from waitlist if state is being changed directly (not from action_cancel_registration)
        # action_cancel_registration sets a context flag to prevent double promotion
        if 'state' in vals and not self._context.get('skip_waitlist_promotion'):
            new_state = vals['state']
            for registration in self:
                original_state = original_states.get(registration.id)
                original_consumption_state = original_consumption_states.get(registration.id)
                
                # If registration is being cancelled, restore quota and promote waitlist
                if new_state == 'cancel' and original_state in ['open', 'confirmed']:
                    _logger.info(f"=== Backend Cancellation: Registration {registration.id} for event {registration.event_id.name} (ID: {registration.event_id.id}) ===")
                    _logger.info(f"Partner: {registration.partner_id.name} (ID: {registration.partner_id.id})")
                    _logger.info(f"Original state: {original_state} -> New state: {new_state}")
                    _logger.info(f"Original consumption_state: {original_consumption_state}")
                    
                    # Restore membership quota if it was consumed
                    if registration.membership_id and original_consumption_state == 'consumed':
                        if registration._should_block_quota_refund_for_cancel_window():
                            _logger.info(
                                f"Quota refund blocked by cancel-window policy for membership {registration.membership_id.id}"
                            )
                            registration._apply_cancel_window_non_refund_penalty()
                            registration.message_post(
                                body=_('Quota/points refund blocked due to repeated cancellation-window violations.')
                            )
                        else:
                            _logger.info(f"Restoring membership quota for membership {registration.membership_id.id}")
                            registration._restore_membership_quota()
                    else:
                        _logger.info(f"No quota to restore (membership_id: {registration.membership_id.id if registration.membership_id else None}, consumption_state: {original_consumption_state})")

                    # Violation record is handled by unified attendance penalty policy.
                    
                    # Promote next person from waitlist
                    if registration.event_id.seats_limited:
                        _logger.info(f"Event has limited seats (max: {registration.event_id.seats_max}), attempting to promote from waitlist...")
                        # Use centralized promotion to handle concurrent cancellations
                        registration.event_id._promote_waitlist_safe()
                    else:
                        _logger.info(f"Event has unlimited seats, skipping waitlist promotion")

                    # Cancellation incident counting is handled above.
                
                # Handle waitlist registration cancellations from backend
                elif new_state == 'cancel' and original_state == 'draft' and registration.is_on_waitlist:
                    _logger.info(f"=== Backend Waitlist Cancellation: Registration {registration.id} for event {registration.event_id.name} (ID: {registration.event_id.id}) ===")
                    _logger.info(f"Partner: {registration.partner_id.name} (ID: {registration.partner_id.id})")
                    _logger.info(f"Original state: {original_state} -> New state: {new_state}")
                    _logger.info(f"Waitlist position: {registration.waitlist_position}")
                    
                    # Store event info before deletion for waitlist promotion
                    event_id = registration.event_id
                    seats_limited = event_id.seats_limited
                    
                    # Log the cancellation before deletion
                    registration.message_post(
                        body=_('Waitlist registration cancelled from backend')
                    )
                    
                    # Delete the waitlist registration
                    registration.unlink()
                    
                    # Promote next person from waitlist if event has limited seats
                    if seats_limited:
                        # Find the next person on the waitlist (lowest position number)
                        next_waitlist_reg = self.env['event.registration'].search([
                            ('event_id', '=', event_id.id),
                            ('is_on_waitlist', '=', True),
                            ('state', '=', 'draft')
                        ], order='waitlist_position asc', limit=1)
                        
                        if next_waitlist_reg:
                            # Promote this registration
                            next_waitlist_reg.write({
                                'is_on_waitlist': False,
                                'waitlist_position': 0,
                                'state': 'open',
                                'pending_wechat_notification': True,
                            })
                            
                            # Consume membership quota for the promoted registration
                            if next_waitlist_reg.membership_id and next_waitlist_reg.consumption_state == 'pending':
                                next_waitlist_reg._consume_membership_quota()
                            
                            # Log the promotion
                            next_waitlist_reg.message_post(
                                body=_('Promoted from waitlist to confirmed registration')
                            )
                            
                            # Update waitlist positions for remaining waitlist registrations
                            self._update_waitlist_positions_after_deletion(event_id)
        
        # Note: Club attendance (state='done') does NOT affect first-timer status
        # Only memberships affect is_first_timer (for membership pricing eligibility)
        # First-timer coupon usage for clubs is completely independent from membership pricing
        
        # Clear UI caches to ensure fresh data
        self.env['ir.ui.view'].clear_caches()
        
        return result
    
    def action_promote_from_waitlist(self):
        """Manually promote a registration from waitlist to confirmed"""
        for registration in self:
            if not registration.is_on_waitlist:
                raise UserError(_('This registration is not on the waitlist'))
            
            if not registration.event_id.seats_limited:
                raise UserError(_('This event does not have limited seats'))
            
            # Use the safe promotion method to handle concurrent scenarios
            # This will check availability and promote appropriately
            try:
                registration.event_id._promote_waitlist_safe()
                
                # Refresh the registration to get updated state
                registration.invalidate_recordset()
                
                if not registration.is_on_waitlist:
                    # Log the manual promotion
                    registration.message_post(
                        body=_('Manually promoted from waitlist to confirmed registration')
                    )
                else:
                    raise UserError(_('No seats available for promotion'))
                    
            except Exception as e:
                _logger.error(f"Error promoting registration {registration.id}: {e}")
                raise UserError(_('Failed to promote from waitlist: %s') % str(e))
    
    def action_add_to_waitlist(self):
        """Manually add a registration to the waitlist"""
        for registration in self:
            if registration.is_on_waitlist:
                raise UserError(_('This registration is already on the waitlist'))
            
            if not registration.event_id.seats_limited:
                raise UserError(_('This event does not have limited seats'))
            
            # Add to waitlist
            registration._add_to_waitlist()
            
            # Log the addition
            registration.message_post(
                body=_('Manually added to waitlist')
            )

    def action_mark_late_attendance(self):
        """Toggle late attendance flag from registration desk."""
        for registration in self:
            if registration.state in ['cancel', 'draft'] or registration.is_on_waitlist:
                raise UserError(_('Only confirmed/open attendees can be marked as late attendance.'))

            mark_as_late = not registration.is_late_attendance
            vals = {'is_late_attendance': mark_as_late}
            if mark_as_late and registration.state != 'done':
                vals['state'] = 'done'
            if mark_as_late:
                vals['is_no_show_attendance'] = False
            registration.write(vals)

            if mark_as_late:
                message = _('Marked as late attendance from registration desk')
            else:
                message = _('Removed late attendance mark from registration desk')
            registration.message_post(body=message)

            if mark_as_late:
                registration._apply_attendance_penalty_policy('late')
        return True

    def action_mark_no_show_attendance(self):
        """Toggle no-show flag from registration desk."""
        for registration in self:
            if registration.state in ['cancel', 'draft'] or registration.is_on_waitlist:
                raise UserError(_('Only confirmed/open attendees can be marked as no-show.'))

            mark_as_no_show = not registration.is_no_show_attendance
            vals = {'is_no_show_attendance': mark_as_no_show}
            if mark_as_no_show:
                vals['is_late_attendance'] = False
            registration.write(vals)

            if mark_as_no_show:
                message = _('Marked as no-show from registration desk')
            else:
                message = _('Removed no-show mark from registration desk')
            registration.message_post(body=message)

            if mark_as_no_show:
                registration._apply_attendance_penalty_policy('no_show')
        return True

    def _mark_late_no_show_incident(self, incident_type):
        """Backward-compatible wrapper; delegates to unified attendance policy."""
        return self._apply_attendance_penalty_policy(incident_type)

    def _is_quota_penalty_incident_type(self, incident_type):
        return incident_type in ['late', 'no_show', 'cancel_window']

    def _apply_attendance_penalty_policy(self, incident_type):
        """
        Unified attendance penalty engine.
        - unlimited: every 3 incidents => 3-day penalty freeze
        - bucket/points: 2 incidents in the current calendar month => cancel-window refund blocked
        """
        self.ensure_one()
        membership = self.membership_id
        if not membership:
            return False

        if incident_type == 'late':
            body = _('Attendance policy incident recorded: late attendance')
        elif incident_type == 'cancel_window':
            body = _('Attendance policy incident recorded: cancellation within cancellation window')
        else:
            body = _('Attendance policy incident recorded: no-show')

        # Unlimited memberships use freeze policy incidents.
        if membership.plan_quota_mode == 'unlimited':
            if self.late_no_show_incident:
                return False
            self.write({
                'late_no_show_incident': True,
                'late_no_show_incident_date': fields.Datetime.now(),
            })
            self.message_post(body=body)
            membership._evaluate_unlimited_late_no_show_policy()
            return True

        # Bucket/points memberships use calendar-month violation policy.
        if membership.plan_quota_mode in ['bucket_counts', 'points'] and self._is_quota_penalty_incident_type(incident_type):
            if self.quota_penalty_violation:
                return False
            self.write({
                'quota_penalty_violation': True,
                'quota_penalty_violation_date': fields.Datetime.now(),
                'quota_penalty_incident_type': incident_type,
            })
            violation_count_30d = self._get_recent_quota_policy_violation_count(include_current=True)
            membership.message_post(
                body=_(
                    'Attendance policy violation recorded for event "%s" (%s). '
                    'Current count this month: %s.'
                ) % (self.event_id.name, incident_type, violation_count_30d)
            )
            if violation_count_30d == 2:
                self._apply_cancel_window_non_refund_penalty()
            return True

        return False

    def _get_cancellation_incident_type(self):
        """
        Return cancellation incident type:
        - cancel_window: cancellation happens during event cancellation window
                         (from cancellation deadline up to event start)
        - False: cancellation happens outside that window (no incident)
        """
        self.ensure_one()
        if not self.event_id or not self.event_id.date_begin:
            return False

        now = fields.Datetime.now()
        event_start = self.event_id.date_begin
        cancellation_deadline = event_start - timedelta(hours=self.event_id.cancellation_deadline_hours or 24)
        if cancellation_deadline <= now < event_start:
            return 'cancel_window'
        return False

    def _is_cancel_window_violation_for_quota_policy(self):
        """Whether this cancellation counts for bucket/points non-refund policy."""
        self.ensure_one()
        membership = self.membership_id
        if not membership:
            return False
        if membership.plan_quota_mode not in ['bucket_counts', 'points']:
            return False
        return self._get_cancellation_incident_type() == 'cancel_window'

    def _should_block_quota_refund_for_cancel_window(self):
        """
        Bucket/points rule:
        - 1st violation this calendar month: normal refund
        - 2nd violation this calendar month: refund blocked
        """
        self.ensure_one()
        if not self._is_cancel_window_violation_for_quota_policy():
            return False
        recent_violations = self._get_recent_quota_policy_violation_count(include_current=False)
        projected_count = recent_violations + 1
        return projected_count == 2

    def _register_cancel_window_violation(self):
        """Backward-compatible wrapper for unified attendance policy."""
        return self._apply_attendance_penalty_policy('cancel_window')

    def _apply_cancel_window_non_refund_penalty(self):
        """
        Apply persistent adjustment so computed remaining quota/points
        does not return the last club/points on blocked refund.
        """
        self.ensure_one()
        membership = self.membership_id
        if not membership:
            return False
        if self.quota_penalty_applied:
            return False
        if self.consumption_state != 'consumed':
            return False

        if membership.plan_quota_mode == 'points':
            points_penalty = self.points_consumed or 0
            if points_penalty:
                membership.write({'adj_points': membership.adj_points - points_penalty})
                self.write({'quota_penalty_applied': True})
                membership.message_post(
                    body=_(
                        'Attendance policy penalty applied for event "%s": '
                        '%s points were not refunded.'
                    ) % (self.event_id.name, points_penalty)
                )
            return True

        if membership.plan_quota_mode == 'bucket_counts':
            if self.club_type == 'regular_offline':
                membership.write({'adj_offline': membership.adj_offline - 1})
                self.write({'quota_penalty_applied': True})
                membership.message_post(
                    body=_(
                        'Attendance policy penalty applied for event "%s": '
                        '1 offline session was not refunded.'
                    ) % self.event_id.name
                )
            elif self.club_type == 'regular_online':
                membership.write({'adj_online': membership.adj_online - 1})
                self.write({'quota_penalty_applied': True})
                membership.message_post(
                    body=_(
                        'Attendance policy penalty applied for event "%s": '
                        '1 online session was not refunded.'
                    ) % self.event_id.name
                )
            elif self.club_type == 'spclub':
                membership.write({'adj_sp': membership.adj_sp - 1})
                self.write({'quota_penalty_applied': True})
                membership.message_post(
                    body=_(
                        'Attendance policy penalty applied for event "%s": '
                        '1 special session was not refunded.'
                    ) % self.event_id.name
                )
            return True

        return False

    def _get_recent_quota_policy_violation_count(self, include_current=False):
        """Count quota policy violations for this membership in the current calendar month."""
        self.ensure_one()
        if not self.membership_id:
            return 0
        now = fields.Datetime.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        domain = [
            ('membership_id', '=', self.membership_id.id),
            ('quota_penalty_violation', '=', True),
            ('quota_penalty_violation_date', '>=', month_start),
        ]
        if not include_current:
            domain.append(('id', '!=', self.id))
        return self.search_count(domain)

    def _process_automatic_refund(self):
        """Process automatic refund for single club purchases"""
        self.ensure_one()
        
        if not self.payment_transaction_id:
            return
            
        transaction = self.payment_transaction_id
        
        # Only process WeChat and Alipay payments that are completed
        if transaction.provider_code not in ['wechat', 'alipay'] or transaction.state != 'done':
            _logger.info(f"Skipping automatic refund for registration {self.id}: provider={transaction.provider_code}, state={transaction.state}")
            return
            
        # Check if already refunded
        # For WeChat: check wechat_transaction_id for REF- prefix
        # For Alipay: check if there are any refund child transactions
        already_refunded = False
        if transaction.provider_code == 'wechat':
            if transaction.wechat_transaction_id and 'REF-' in str(transaction.wechat_transaction_id):
                already_refunded = True
        elif transaction.provider_code == 'alipay':
            # Check if there are any refund child transactions
            refund_txs = transaction.child_transaction_ids.filtered(lambda tx: tx.state == 'done')
            if refund_txs:
                already_refunded = True
        
        if already_refunded:
            _logger.info(f"Registration {self.id} already refunded: provider={transaction.provider_code}")
            return
            
        _logger.info(f"Processing automatic refund for registration {self.id}, provider={transaction.provider_code}, transaction amount: {transaction.amount}")
        
        try:
            # Call the refund method (will refund the transaction amount automatically)
            transaction.action_refund()
            
            # Post success message with provider name
            provider_name = 'WeChat Pay' if transaction.provider_code == 'wechat' else 'Alipay'
            self.message_post(
                body=_('Automatic refund processed: ¥%s refunded to %s. Transaction: %s') % (
                    transaction.amount,
                    provider_name,
                    transaction.reference
                )
            )
            
            _logger.info(f"Automatic refund successful for registration {self.id}, provider={transaction.provider_code}, amount: {transaction.amount}")
            
        except Exception as e:
            _logger.error(f"Refund failed for registration {self.id}, provider={transaction.provider_code}: {str(e)}")
            raise UserError(_('Failed to process automatic refund: %s') % str(e))

    def unlink(self):
        """Override unlink to handle membership cleanup"""
        # If registration was consumed, we might want to restore quota
        # This could be implemented based on business rules
        result = super().unlink()
        
        # Clear UI caches to ensure fresh data
        self.env['ir.ui.view'].clear_caches()
        
        return result
