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
        ('spclub', 'Special Club')
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
    
    # Computed fields for notifications
    hours_until_event = fields.Float(string='Hours Until Event', compute='_compute_hours_until_event', store=False)
    event_name = fields.Char(string='Event Name', related='event_id.name', readonly=True)
    event_venue_name = fields.Char(string='Venue Name', related='event_id.address_id.name', readonly=True)
    event_time_formatted = fields.Char(string='Event Time', compute='_compute_event_time_formatted', store=False)
    
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
                # Convert from UTC to user's timezone
                user_tz = self.env.user.tz or 'UTC'
                import pytz
                from datetime import datetime
                
                # Convert the datetime to user's timezone
                utc_time = registration.event_id.date_begin
                if isinstance(utc_time, datetime):
                    utc_time = pytz.UTC.localize(utc_time) if utc_time.tzinfo is None else utc_time
                    local_tz = pytz.timezone(user_tz)
                    local_time = utc_time.astimezone(local_tz)
                    # Format as "HH:MM AM/PM"
                    registration.event_time_formatted = local_time.strftime('%I:%M %p')
                else:
                    registration.event_time_formatted = ''
            else:
                registration.event_time_formatted = ''
    
    @api.depends('event_id.tag_ids')
    def _compute_club_type(self):
        """Compute club type from the event's Type tag"""
        for registration in self:
            if registration.event_id and registration.event_id.tag_ids:
                # Look for the tag with category "Type" to determine club type
                type_tag = registration.event_id.tag_ids.filtered(
                    lambda tag: tag.category_id.name == 'Type'
                )[:1]  # Safely grab the first record
                if type_tag:
                    tag_name = type_tag.name.lower()
                    if 'offline' in tag_name:
                        registration.club_type = 'regular_offline'
                    elif 'online' in tag_name:
                        registration.club_type = 'regular_online'
                    elif 'sp' in tag_name or 'special' in tag_name:
                        registration.club_type = 'spclub'
                    else:
                        registration.club_type = False
                else:
                    # Fallback: determine from event properties
                    if hasattr(registration.event_id, 'is_online_event') and registration.event_id.is_online_event:
                        registration.club_type = 'regular_online'
                    else:
                        registration.club_type = 'regular_offline'
            else:
                # Default to offline if no tags
                registration.club_type = 'regular_offline'
    
    @api.depends(
        'club_type',
        'membership_id',
        'membership_id.membership_plan_id',
        'membership_id.membership_plan_id.points_per_offline',
        'membership_id.membership_plan_id.points_per_online',
        'membership_id.membership_plan_id.points_per_sp',
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
                if registration.club_type == 'regular_offline':
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
            # Store event info before deletion for waitlist promotion
            event_id = self.event_id
            seats_limited = event_id.seats_limited
            
            # Log the cancellation before deletion
            self.message_post(
                body=_('Waitlist registration cancelled by portal user')
            )
            
            # Delete the waitlist registration
            self.unlink()
            
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
                        'state': 'open'
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
            
            return True
        
        # Handle regular registrations (open/confirmed state)
        _logger.info(f"=== action_cancel_registration called for registration {self.id}, state={self.state}, is_on_waitlist={self.is_on_waitlist} ===")
        
        # If membership was consumed or pending, restore the quota
        if self.consumption_state in ['consumed', 'pending'] and self.membership_id:
            if self.consumption_state == 'consumed':
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
        
        # Log the cancellation
        self.message_post(
            body=_('Registration cancelled by portal user')
        )
        
        # Promote next person from waitlist if event has limited seats
        if self.event_id.seats_limited:
            _logger.info(f"Event has limited seats, attempting to promote from waitlist...")
            self._promote_next_waitlist_registration()
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
                'state': 'open'
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
        
        if not self.membership_id or self.consumption_state != 'pending':
            return
        
        membership = self.membership_id
        
        # Check if membership has sufficient quota BEFORE consuming
        if not self._can_consume_membership():
            raise ValidationError(_('Insufficient membership quota for this event'))
        
        # Mark as consumed first
        self.write({
            'consumption_state': 'consumed'
        })
        
        # Log the quota consumption
        membership.message_post(
            body=_('Quota consumed for event registration: %s') % self.event_id.name
        )
    
    def _add_to_waitlist(self):
        """Add registration to waitlist and assign position"""
        self.ensure_one()
        
        if not self.event_id.seats_limited:
            return  # No waitlist if seats are unlimited
        
        # Get current waitlist count
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
        
        # Create the record first
        registration = super().create(vals)
        
        # Post-create validation and auto-selection
        if registration.partner_id and registration.event_id:
            registration._post_create_validation()
        
        # Check seat availability for all new registrations (not imports)
        if not is_import and registration.event_id:
            event = registration.event_id
            _logger.info(f"=== New Registration Created: ID {registration.id} for event {event.name} (ID: {event.id}) ===")
            _logger.info(f"Partner: {registration.partner_id.name} (ID: {registration.partner_id.id})")
            _logger.info(f"Has membership: {bool(registration.membership_id)}")
            
            if event.seats_limited:
                # Force fresh data from database
                event.flush_recordset()
                event.invalidate_recordset()
                
                # Calculate current availability directly (excluding the newly created registration)
                confirmed_registrations = event.registration_ids.filtered(
                    lambda r: r.id != registration.id and r.state in ['open', 'confirmed', 'done'] and not r.is_on_waitlist
                )
                available_seats = max(0, event.seats_max - len(confirmed_registrations))
                
                _logger.info(f"Event has limited seats: {len(confirmed_registrations)} / {event.seats_max} seats taken (excluding current registration)")
                _logger.info(f"Available seats: {available_seats}")
                
                if available_seats <= 0:
                    # Add to waitlist instead of consuming quota
                    _logger.info(f"No seats available - adding to waitlist")
                    registration._add_to_waitlist()
                elif registration.membership_id and registration.consumption_state == 'pending':
                    # Normal registration with membership - consume quota
                    _logger.info(f"Seats available - confirming registration and consuming quota")
                    registration._consume_membership_quota()
                else:
                    _logger.info(f"Seats available - registration confirmed (no membership quota to consume)")
            else:
                # Unlimited seats - just consume quota if membership exists
                _logger.info(f"Event has unlimited seats")
                if registration.membership_id and registration.consumption_state == 'pending':
                    _logger.info(f"Consuming membership quota")
                    registration._consume_membership_quota()
        
        # Update partner's first timer status after creating registration
        if registration.partner_id:
            self.env['res.partner']._update_first_timer_status(registration.partner_id.id)
        
        # Clear UI caches to ensure fresh data
        registration.env['ir.ui.view'].clear_caches()
        
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
        
        # Post-write validation
        for registration in self:
            if registration.partner_id and registration.event_id:
                registration._validate_registration()
        
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
                        _logger.info(f"Restoring membership quota for membership {registration.membership_id.id}")
                        registration._restore_membership_quota()
                    else:
                        _logger.info(f"No quota to restore (membership_id: {registration.membership_id.id if registration.membership_id else None}, consumption_state: {original_consumption_state})")
                    
                    # Promote next person from waitlist
                    if registration.event_id.seats_limited:
                        _logger.info(f"Event has limited seats (max: {registration.event_id.seats_max}), attempting to promote from waitlist...")
                        registration._promote_next_waitlist_registration()
                    else:
                        _logger.info(f"Event has unlimited seats, skipping waitlist promotion")
        
        # Update first timer status if registration state changed to 'done' (attended)
        if vals.get('state') == 'done':
            for registration in self:
                if registration.partner_id:
                    self.env['res.partner']._update_first_timer_status(registration.partner_id.id)
        
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
            
            # Check if there are available seats
            confirmed_registrations = registration.event_id.registration_ids.filtered(
                lambda r: r.state in ['open', 'confirmed', 'done'] and not r.is_on_waitlist
            )
            if len(confirmed_registrations) >= registration.event_id.seats_max:
                raise UserError(_('No seats available for promotion'))
            
            # Promote the registration
            registration.write({
                'is_on_waitlist': False,
                'waitlist_position': 0,
                'state': 'open'
            })
            
            # Consume membership quota
            if registration.membership_id and registration.consumption_state == 'pending':
                registration._consume_membership_quota()
            
            # Log the promotion
            registration.message_post(
                body=_('Manually promoted from waitlist to confirmed registration')
            )
            
            # Update remaining waitlist positions
            registration._update_waitlist_positions()
    
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
    
    def _process_automatic_refund(self):
        """Process automatic refund for single club purchases"""
        self.ensure_one()
        
        if not self.payment_transaction_id:
            return
            
        transaction = self.payment_transaction_id
        
        # Only process WeChat payments that are completed
        if transaction.provider_code != 'wechat' or transaction.state != 'done':
            _logger.info(f"Skipping automatic refund for registration {self.id}: provider={transaction.provider_code}, state={transaction.state}")
            return
            
        # Check if already refunded
        if transaction.wechat_transaction_id and 'REF-' in str(transaction.wechat_transaction_id):
            _logger.info(f"Registration {self.id} already refunded: {transaction.wechat_transaction_id}")
            return
            
        _logger.info(f"Processing automatic refund for registration {self.id}, transaction amount: {transaction.amount}")
        
        try:
            # Call the refund method (will refund the transaction amount automatically)
            transaction.action_refund()
            
            # Post success message
            self.message_post(
                body=_('Automatic refund processed: ¥%s refunded to WeChat Pay. Transaction: %s') % (
                    transaction.amount,
                    transaction.reference
                )
            )
            
            _logger.info(f"Automatic refund successful for registration {self.id}, amount: {transaction.amount}")
            
        except Exception as e:
            _logger.error(f"WeChat Pay refund failed for registration {self.id}: {str(e)}")
            raise UserError(_('Failed to process automatic refund: %s') % str(e))

    def unlink(self):
        """Override unlink to handle membership cleanup"""
        # If registration was consumed, we might want to restore quota
        # This could be implemented based on business rules
        result = super().unlink()
        
        # Clear UI caches to ensure fresh data
        self.env['ir.ui.view'].clear_caches()
        
        return result
