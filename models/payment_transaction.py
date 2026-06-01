# -*- coding: utf-8 -*-

import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'
    
    # Transaction type discriminator
    popcorn_transaction_type = fields.Selection([
        ('membership', 'Membership Purchase'),
        ('event', 'Event Registration'),
        ('product', 'Product Purchase'),
    ], string='Popcorn Transaction Type', help='Type of popcorn transaction for automatic processing')
    
    # Membership fields
    membership_plan_id = fields.Many2one(
        'popcorn.membership.plan',
        string='Membership Plan',
        help='Membership plan associated with this transaction'
    )
    is_upgrade = fields.Boolean(
        string='Is Upgrade',
        help='Whether this is a membership upgrade transaction'
    )
    is_renewal = fields.Boolean(
        string='Is Renewal',
        help='Whether this is a membership renewal transaction'
    )
    upgrade_details = fields.Json(
        string='Upgrade Details',
        help='Details of membership upgrade (old membership, new tier, etc.)'
    )
    customer_signature = fields.Binary(
        string='Customer Signature',
        attachment=True,
        help='Customer signature (base64 image) for membership contracts'
    )
    student_card_attachment_id = fields.Many2one(
        'ir.attachment',
        string='Student Card',
        ondelete='set null',
        help='Student ID card uploaded during checkout, transferred to membership on creation'
    )
    
    # Event fields
    event_id = fields.Many2one(
        'event.event',
        string='Event',
        help='Event associated with this transaction'
    )
    
    # Shared fields
    applied_discount_id = fields.Many2one(
        'popcorn.discount',
        string='Applied Discount',
        help='Discount applied to this transaction'
    )
    use_popcorn_money = fields.Boolean(
        string='Use Popcorn Money',
        help='Whether popcorn money was used in this transaction'
    )
    popcorn_money_to_use = fields.Float(
        string='Popcorn Money Used',
        help='Amount of popcorn money used in this transaction'
    )
    remaining_amount = fields.Float(
        string='Remaining Amount',
        help='Remaining amount after popcorn money deduction'
    )
    
    # Flag to prevent duplicate processing
    popcorn_processed = fields.Boolean(
        string='Popcorn Processed',
        default=False,
        help='Whether this transaction has been processed for popcorn (membership/event creation)'
    )
    
    def write(self, vals):
        """Override write to detect state changes and process popcorn transactions
        
        This handles cases where wechat_payment_gateway bypasses _set_done() 
        and writes state directly due to TypeError compatibility issues.
        """
        # Check if state is being changed to 'done' (before write)
        state_changing_to_done = (
            vals.get('state') == 'done' and 
            any(t.state != 'done' for t in self)
        )
        
        # Store current popcorn_processed flags before write
        pre_write_processed = {t.id: t.popcorn_processed for t in self}
        
        # Call parent write first
        res = super().write(vals)
        
        # Process popcorn transactions if state just changed to 'done'
        # Only process if not already processed (prevents duplicates)
        if state_changing_to_done:
            for transaction in self:
                # Only process if:
                # 1. It's a popcorn transaction
                # 2. It wasn't processed before the write
                # 3. State is now 'done'
                # 4. Still not processed (safety check)
                if (transaction.popcorn_transaction_type and 
                    not pre_write_processed.get(transaction.id, False) and
                    not transaction.popcorn_processed and 
                    transaction.state == 'done'):
                    try:
                        _logger.info(f"State changed to 'done' via write() for transaction {transaction.reference}, "
                                   f"processing popcorn transaction")
                        transaction._process_popcorn_transaction()
                    except Exception as e:
                        _logger.error(
                            f"Error processing popcorn transaction {transaction.reference}: {str(e)}",
                            exc_info=True
                        )
                        # Don't fail the transaction, just log the error
        
        return res
    
    def _set_done(self, state_message=None, write_state=True):
        """Override to automatically create membership/event when payment is confirmed"""
        res = super()._set_done(state_message=state_message, write_state=write_state)
        
        # Only process popcorn transactions that haven't been processed yet
        # This handles cases where _set_done() is called normally
        for transaction in self:
            if (transaction.popcorn_transaction_type and 
                not transaction.popcorn_processed and 
                transaction.state == 'done'):
                try:
                    _logger.info(f"_set_done() called for transaction {transaction.reference}, "
                               f"processing popcorn transaction")
                    transaction._process_popcorn_transaction()
                except Exception as e:
                    _logger.error(
                        f"Error processing popcorn transaction {transaction.reference}: {str(e)}",
                        exc_info=True
                    )
                    # Don't fail the transaction, just log the error
        
        return res
    
    def _process_popcorn_transaction(self):
        """Process popcorn transaction and create membership/event registration"""
        self.ensure_one()
        
        if self.popcorn_processed:
            _logger.info(f"Transaction {self.reference} already processed, skipping")
            return
        
        if not self.popcorn_transaction_type:
            _logger.debug(f"Transaction {self.reference} is not a popcorn transaction, skipping")
            return
        
        if self.state != 'done':
            _logger.debug(f"Transaction {self.reference} not in done state ({self.state}), skipping")
            return
        
        _logger.info(f"Processing popcorn transaction {self.reference}, type: {self.popcorn_transaction_type}")
        
        if self.popcorn_transaction_type == 'membership':
            self._process_membership_transaction()
        elif self.popcorn_transaction_type == 'event':
            self._process_event_transaction()
        elif self.popcorn_transaction_type == 'product':
            # Product transactions are handled by sale orders automatically
            _logger.debug(f"Product transaction {self.reference} handled by sale order system")
            pass
        else:
            _logger.warning(f"Unknown popcorn transaction type: {self.popcorn_transaction_type}")
        
        # Mark as processed to prevent duplicate processing
        self.write({'popcorn_processed': True})
    
    def _process_membership_transaction(self):
        """Process membership purchase transaction"""
        self.ensure_one()
        
        if not self.membership_plan_id:
            _logger.error(f"Membership transaction {self.reference} missing membership_plan_id")
            raise UserError(_("Membership plan information is missing for this transaction"))
        
        if not self.partner_id:
            _logger.error(f"Membership transaction {self.reference} missing partner_id")
            raise UserError(_("Partner information is missing for this transaction"))
        
        plan = self.membership_plan_id
        partner = self.partner_id
        
        _logger.info(
            f"Processing membership transaction {self.reference}: "
            f"Plan: {plan.name}, Partner: {partner.name}, "
            f"is_upgrade: {self.is_upgrade}, is_renewal: {self.is_renewal}, "
            f"upgrade_details: {self.upgrade_details}"
        )
        
        # Get applied discount if any
        applied_discount = self.applied_discount_id if self.applied_discount_id else None
        
        # Deduct popcorn money if used (for all transaction types)
        if self.use_popcorn_money and self.popcorn_money_to_use > 0:
            _logger.info(f"Deducting popcorn money: {self.popcorn_money_to_use} for partner {partner.name}")
            partner.deduct_popcorn_money(
                self.popcorn_money_to_use,
                f'Membership purchase: {plan.display_name}'
            )
        
        # Priority: Upgrade first, then renewal, then new membership
        # Check for upgrade FIRST before checking if membership exists
        # IMPORTANT: If is_upgrade is True, we MUST handle it as an upgrade, not renewal
        # Even if upgrade_details is missing, we should log an error but still treat it as upgrade
        if self.is_upgrade:
            # Ensure upgrade_details is a dict (JSON field may return as dict or string)
            upgrade_details_dict = {}
            if self.upgrade_details:
                if isinstance(self.upgrade_details, str):
                    import json
                    try:
                        upgrade_details_dict = json.loads(self.upgrade_details)
                    except (json.JSONDecodeError, TypeError):
                        _logger.error(f"Invalid upgrade_details JSON for transaction {self.reference}: {self.upgrade_details}")
                        upgrade_details_dict = {}
                else:
                    upgrade_details_dict = self.upgrade_details or {}
            
            # Upgrade existing membership
            membership_id = upgrade_details_dict.get('membership_id')
            upgrade_price = upgrade_details_dict.get('upgrade_price', 0)
            
            # IMPORTANT: Use actual payment amount (remaining_amount) for purchase_price calculation
            # remaining_amount = upgrade_price - popcorn_money_to_use
            # purchase_price_paid should only reflect real money paid, not popcorn money
            actual_payment_amount = self.remaining_amount if self.remaining_amount else (self.amount if self.amount else 0)
            
            _logger.info(
                f"Upgrade processing - membership_id: {membership_id}, "
                f"upgrade_price: {upgrade_price}, "
                f"popcorn_money_to_use: {self.popcorn_money_to_use or 0}, "
                f"remaining_amount: {self.remaining_amount or 0}, "
                f"actual_payment_amount (for purchase_price): {actual_payment_amount}, "
                f"upgrade_details: {upgrade_details_dict}"
            )
            
            if not membership_id:
                _logger.error(f"Upgrade transaction {self.reference} missing membership_id in upgrade_details. upgrade_details: {upgrade_details_dict}")
                raise UserError(_("Membership ID is missing for upgrade transaction"))
            
            # Get the original membership
            original_membership = self.env['popcorn.membership'].browse(int(membership_id))
            
            if not original_membership.exists():
                _logger.error(f"Membership {membership_id} not found for upgrade transaction {self.reference}")
                raise UserError(_("Original membership not found for upgrade"))
            
            # Validate ownership
            if original_membership.partner_id.id != partner.id:
                _logger.error(f"Membership {membership_id} does not belong to partner {partner.id} for upgrade transaction {self.reference}")
                raise UserError(_("Membership does not belong to this partner"))
            
            # Upgrade the membership using model method
            # Pass actual_payment_amount (not upgrade_price) so purchase_price_paid only reflects real money paid
            membership = original_membership.action_upgrade_to_plan(
                plan,
                actual_payment_amount,  # Use actual payment amount, not full upgrade_price
                payment_transaction_id=self.id,
                payment_reference=self.reference,
                applied_discount=applied_discount
            )
            
            _logger.info(f"Membership {membership.id} upgraded successfully for transaction {self.reference}")
            
            # Add payment message
            payment_message = _(
                'Payment successful via %s. Transaction: %s. Membership upgraded and activated.'
            ) % (self.provider_id.name if self.provider_id else 'Unknown', self.reference)
            
            membership.message_post(body=payment_message)
            
            if self.use_popcorn_money and self.popcorn_money_to_use > 0:
                currency_symbol = plan.currency_id.symbol if plan.currency_id else ''
                payment_message += _(
                    ' Popcorn money used: %s%s. Remaining: %s%s'
                ) % (
                    currency_symbol, self.popcorn_money_to_use,
                    currency_symbol, self.remaining_amount or 0
                )
            
            _logger.info(f"Membership {membership.id} upgraded successfully for transaction {self.reference}")
            return membership
        
        # IMPORTANT: Only process renewal if NOT an upgrade
        # If is_upgrade is True, we already handled it above
        elif self.is_renewal and not self.is_upgrade:
            # Renewal creates a NEW membership
            # Check if renewal membership already exists for this transaction
            renewal_membership = self.env['popcorn.membership'].search([
                ('payment_transaction_id', '=', self.id),
                ('partner_id', '=', partner.id)
            ], limit=1)
            
            if renewal_membership:
                _logger.info(f"Renewal membership {renewal_membership.id} already exists for transaction {self.reference}, skipping creation")
                membership = renewal_membership
            else:
                # Create new membership for renewal
                membership = self._create_membership_from_transaction(
                    plan, partner, applied_discount
                )
                _logger.info(f"Renewal membership {membership.id} created successfully for transaction {self.reference}")
            
            # Add payment message
            payment_message = _(
                'Payment successful via %s. Transaction: %s. Membership renewed and activated.'
            ) % (self.provider_id.name if self.provider_id else 'Unknown', self.reference)
            
            membership.message_post(body=payment_message)
            
            if self.use_popcorn_money and self.popcorn_money_to_use > 0:
                currency_symbol = plan.currency_id.symbol if plan.currency_id else ''
                payment_message += _(
                    ' Popcorn money used: %s%s. Remaining: %s%s'
                ) % (
                    currency_symbol, self.popcorn_money_to_use,
                    currency_symbol, self.remaining_amount or 0
                )
            
            _logger.info(f"Renewal membership {membership.id} created successfully for transaction {self.reference}")
            return membership
            
        else:
            # Create standard new membership
            # Check if membership already exists for this transaction (for new purchases only)
            existing_membership = self.env['popcorn.membership'].search([
                ('payment_transaction_id', '=', self.id)
            ], limit=1)
            
            if existing_membership:
                _logger.info(
                    f"Membership {existing_membership.id} already exists for transaction {self.reference}, "
                    f"skipping creation"
                )
                return existing_membership
            
            membership = self._create_membership_from_transaction(
                plan, partner, applied_discount
            )
            
            _logger.info(f"Membership {membership.id} created successfully for transaction {self.reference}")
            
            # Add payment message
            payment_message = _(
                'Payment successful via %s. Transaction: %s. Membership created and activated.'
            ) % (self.provider_id.name if self.provider_id else 'Unknown', self.reference)
            
            if self.use_popcorn_money and self.popcorn_money_to_use > 0:
                currency_symbol = plan.currency_id.symbol if plan.currency_id else ''
                payment_message += _(
                    ' Popcorn money used: %s%s. Remaining: %s%s'
                ) % (
                    currency_symbol, self.popcorn_money_to_use,
                    currency_symbol, self.remaining_amount or 0
                )
            
            membership.message_post(body=payment_message)
            
            return membership
    
    def _create_membership_from_transaction(self, plan, partner, applied_discount=None):
        """Create membership from transaction data"""
        from odoo import fields as fields_module
        
        # Determine price tier
        price_tier = 'first_timer'
        existing_memberships = self.env['popcorn.membership'].search([
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
        
        # Get best discount
        if applied_discount:
            best_price = applied_discount.get_discounted_price(plan, purchase_price, partner)
            best_discount = applied_discount
            extra_days = applied_discount.get_extra_days(plan, partner)
        else:
            # Get best discount for this plan and customer
            best_price, best_discount, extra_days = plan.get_best_discount_with_extra_days(
                partner, original_price=purchase_price
            )
        
        # Create membership values
        membership_vals = {
            'partner_id': partner.id,
            'membership_plan_id': plan.id,
            'state': 'pending',
            'purchase_price_paid': self.amount,
            'price_tier': 'discount' if best_discount else price_tier,
            'purchase_channel': 'online',
            'upgrade_discount_allowed': False,
            'first_timer_customer': price_tier == 'first_timer',
            'applied_discount_id': best_discount.id if best_discount else False,
            'extra_days_extension': extra_days,
            'payment_transaction_id': self.id,
            'payment_reference': self.reference,
        }
        
        # Set activation date based on plan policy
        if plan.activation_policy == 'immediate':
            membership_vals['activation_date'] = fields_module.Date.today()
            membership_vals['state'] = 'active'
        elif plan.activation_policy == 'first_attendance':
            membership_vals['state'] = 'pending'
        elif plan.activation_policy == 'manual':
            membership_vals['state'] = 'pending'

        # Student plans always stay pending verification regardless of activation policy
        if plan.is_student_plan:
            membership_vals.pop('activation_date', None)
            membership_vals['state'] = 'pending_student_verification'

        # Create the membership
        membership = self.env['popcorn.membership'].create(membership_vals)
        
        # Create discount usage record if discount was applied
        if best_discount:
            self.env['popcorn.discount.usage'].create_usage_record(
                discount_id=best_discount.id,
                partner_id=partner.id,
                original_price=purchase_price,
                discounted_price=best_price,
                currency_id=plan.currency_id.id,
                membership_plan_id=plan.id,
                membership_id=membership.id,
                extra_days=extra_days
            )
            
            # Increment discount usage
            try:
                best_discount.action_increment_usage()
            except Exception as e:
                _logger.error(f"Failed to increment discount usage: {e}", exc_info=True)
        
        # Create contract with signature if provided
        if self.customer_signature:
            contract_vals = {
                'membership_id': membership.id,
                'contract_type': 'standard',
                'state': 'draft',
                'customer_signature': self.customer_signature,
                'customer_signature_date': fields_module.Datetime.now(),
                'signed_by_customer': True,
            }
            contract = self.env['popcorn.contract'].create(contract_vals)
            membership.write({'contract_id': contract.id})
            membership.message_post(body=_('Contract created and signed by customer during checkout'))

        # Link student card attachment if present
        if plan.is_student_plan and self.student_card_attachment_id:
            self.student_card_attachment_id.write({'res_id': membership.id})
            membership.write({'student_card_attachment_id': self.student_card_attachment_id.id})
            membership.message_post(body=_('Student card uploaded. Awaiting staff verification before activation.'))

        # Log the creation
        membership.message_post(
            body=_('Membership created directly from plan %s') % plan.name
        )

        if plan.is_student_plan:
            membership.message_post(
                body=_('Student membership requires staff verification. Please review the uploaded student card and activate manually.')
            )
        elif plan.activation_policy == 'immediate':
            membership.message_post(
                body=_('Membership automatically activated upon purchase')
            )
        elif plan.activation_policy == 'first_attendance':
            membership.message_post(
                body=_('Membership will be activated upon first event attendance')
            )

        return membership
    
    def _process_event_transaction(self):
        """Process event registration transaction"""
        self.ensure_one()
        
        if not self.event_id:
            _logger.error(f"Event transaction {self.reference} missing event_id")
            raise UserError(_("Event information is missing for this transaction"))
        
        if not self.partner_id:
            _logger.error(f"Event transaction {self.reference} missing partner_id")
            raise UserError(_("Partner information is missing for this transaction"))
        
        event = self.event_id
        partner = self.partner_id
        
        _logger.info(
            f"Creating event registration for transaction {self.reference}: "
            f"Event: {event.name}, Partner: {partner.name}"
        )
        
        # Check if registration already exists for this transaction
        existing_registration = self.env['event.registration'].search([
            ('payment_transaction_id', '=', self.id)
        ], limit=1)
        
        if existing_registration:
            _logger.info(
                f"Event registration {existing_registration.id} already exists for transaction {self.reference}, "
                f"skipping creation"
            )
            return existing_registration
        
        # Deduct popcorn money if used
        if self.use_popcorn_money and self.popcorn_money_to_use > 0:
            _logger.info(f"Deducting popcorn money: {self.popcorn_money_to_use} for partner {partner.name}")
            partner.deduct_popcorn_money(
                self.popcorn_money_to_use,
                f'Event registration: {event.name}'
            )
        
        # Apply discount if used
        applied_discount = None
        if self.applied_discount_id:
            applied_discount = self.applied_discount_id
            _logger.info(f"Applying discount: {applied_discount.code}")
            _logger.info(f"Discount usage count before: {applied_discount.usage_count}")
            applied_discount.action_increment_usage()
            _logger.info(f"Discount usage count after: {applied_discount.usage_count}")
            
            # Calculate discounted price for event (same logic as event controller)
            original_price = event.event_price
            if applied_discount.discount_type == 'percentage':
                discount_amount = original_price * (applied_discount.discount_value / 100)
                discounted_price = max(0, original_price - discount_amount)
            elif applied_discount.discount_type == 'fixed_amount':
                discounted_price = max(0, original_price - applied_discount.discount_value)
            else:
                # Fallback: no discount applied
                discounted_price = original_price
            
            # Create usage record
            self.env['popcorn.discount.usage'].create({
                'discount_id': applied_discount.id,
                'partner_id': partner.id,
                'original_price': event.event_price,
                'discounted_price': discounted_price,
                'currency_id': event.currency_id.id if event.currency_id else self.env.company.currency_id.id,
                'event_id': event.id,
                'extra_days': applied_discount.get_extra_days(None, partner)
            })
            _logger.info(f"Discount usage record created for transaction {self.reference}")
        
        # Create event registration
        registration_vals = {
            'event_id': event.id,
            'partner_id': partner.id,
            'name': partner.name,
            'email': partner.email,
            'phone': partner.phone,
            'state': 'open',
            'payment_amount': self.remaining_amount or self.amount,
            'payment_transaction_id': self.id,
        }
        
        registration = self.env['event.registration'].create(registration_vals)
        
        registration.message_post(
            body=_(
                'Direct purchase registration for event: %s. Price: %s. Payment successful via %s. '
                'Transaction: %s. Event registration created and activated.'
            ) % (
                event.name,
                self.remaining_amount or self.amount,
                self.provider_id.name if self.provider_id else 'Unknown',
                self.reference
            )
        )
        
        _logger.info(
            f"Event registration {registration.id} created successfully for transaction {self.reference}"
        )
        return registration

