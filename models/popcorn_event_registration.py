# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta

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
    
    # Computed field to check if cancellation is allowed
    can_cancel = fields.Boolean(string='Can Cancel', compute='_compute_can_cancel', store=False)
    
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
        """Consume membership quota for this registration"""
        self.ensure_one()
        
        if not self.membership_id:
            raise UserError(_('No membership selected for consumption'))
        
        if self.consumption_state != 'pending':
            raise UserError(_('Registration is not in pending state for consumption'))
        
        membership = self.membership_id
        
        # Check if membership has sufficient quota BEFORE marking as consumed
        if not self._can_consume_membership():
            raise UserError(_('Insufficient membership quota for this event'))
        
        # Mark as consumed first - this will trigger recomputation of remaining fields
        self.write({
            'consumption_state': 'consumed'
        })
        
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
        
        # Check if cancellation is allowed
        if not self.event_id.can_cancel_registration(self):
            raise UserError(_('Cancellation is not allowed at this time. Please check the event cancellation deadline.'))
        
        # Check if registration is in a cancellable state
        if self.state not in ['open', 'confirmed']:
            raise UserError(_('Registration cannot be cancelled in its current state'))
        
        # If membership was consumed, restore the quota
        if self.consumption_state == 'consumed' and self.membership_id:
            self._restore_membership_quota()
        
        # Cancel the registration
        self.write({
            'state': 'cancel',
            'consumption_state': 'cancelled'
        })
        
        # Log the cancellation
        self.message_post(
            body=_('Registration cancelled by portal user')
        )
        
        return True
    
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
        
        # Create the record first
        registration = super().create(vals)
        
        # Post-create validation and auto-selection
        if registration.partner_id and registration.event_id:
            registration._post_create_validation()
        
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
        
        result = super().write(vals)
        
        # Post-write validation
        for registration in self:
            if registration.partner_id and registration.event_id:
                registration._validate_registration()
        
        # Clear UI caches to ensure fresh data
        self.env['ir.ui.view'].clear_caches()
        
        return result
    
    def unlink(self):
        """Override unlink to handle membership cleanup"""
        # If registration was consumed, we might want to restore quota
        # This could be implemented based on business rules
        result = super().unlink()
        
        # Clear UI caches to ensure fresh data
        self.env['ir.ui.view'].clear_caches()
        
        return result
