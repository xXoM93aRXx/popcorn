# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import re
import logging

_logger = logging.getLogger(__name__)


class PopcornNotification(models.Model):
    _name = 'popcorn.notification'
    _description = 'Popcorn Notification'
    _order = 'sequence, name'

    name = fields.Char('Notification Name', required=True, translate=True)
    sequence = fields.Integer('Sequence', default=10, help='Order of display priority')
    active = fields.Boolean('Active', default=True)
    
    # Display settings
    notification_type = fields.Selection([
        ('banner', 'Banner (Toast)'),
        ('popup', 'Popup')
    ], string='Notification Type', default='banner', required=True)
    
    # Content
    title = fields.Char('Title', required=True, translate=True, help='Notification title')
    message = fields.Html('Message', required=True, translate=True, 
                          help='Notification message. Use {field_name} for dynamic content from partner fields')
    
    # Styling
    banner_position = fields.Selection([
        ('top', 'Top'),
        ('bottom', 'Bottom')
    ], string='Banner Position', default='top')
    
    banner_style = fields.Selection([
        ('info', 'Info (Blue)'),
        ('success', 'Success (Green)'),
        ('warning', 'Warning (Orange)'),
        ('danger', 'Danger (Red)')
    ], string='Banner Style', default='info')
    
    popup_size = fields.Selection([
        ('small', 'Small'),
        ('medium', 'Medium'),
        ('large', 'Large')
    ], string='Popup Size', default='medium')
    
    # Display timing
    auto_dismiss = fields.Boolean('Auto Dismiss', default=True, 
                                  help='Automatically dismiss notification after duration')
    dismiss_duration = fields.Integer('Dismiss Duration (seconds)', default=5,
                                     help='Seconds before auto-dismiss (only for banners)')
    
    # Action button (optional)
    show_action_button = fields.Boolean('Show Action Button', default=False)
    action_button_text = fields.Char('Action Button Text', translate=True)
    action_button_url = fields.Char('Action Button URL')
    
    # Rules
    notification_rule_ids = fields.One2many('popcorn.notification.rule', 'notification_id', 
                                           string='Notification Rules')
    
    # Display frequency
    show_once_per_session = fields.Boolean('Show Once Per Session', default=False,
                                          help='Show notification only once per user session')
    show_once_per_user = fields.Boolean('Show Once Per User', default=False,
                                       help='Show notification only once per user (stored in browser)')

    def _evaluate_notification_for_partner(self, partner):
        """Evaluate if a partner should see this notification based on all rules"""
        self.ensure_one()
        
        if not self.active:
            return False
            
        if not self.notification_rule_ids.filtered('active'):
            # If no active rules, show to everyone
            return True
            
        # All rules must pass (AND logic)
        for rule in self.notification_rule_ids.filtered('active'):
            if not rule._evaluate_rule_for_partner(partner):
                return False
        return True
    
    def _bulk_filter_partners_for_notification(self):
        """
        Bulk filter partners that match this notification's rules using Odoo ORM.
        This is much more efficient than evaluating each partner individually.
        
        Returns: recordset of res.partner records that match all rules
        """
        self.ensure_one()
        
        _logger.debug(f'[Bulk Filter] Starting bulk filter for notification "{self.name}" (ID: {self.id})')
        
        if not self.active:
            _logger.debug(f'[Bulk Filter] Notification {self.id} is not active, returning empty')
            return self.env['res.partner'].browse()
        
        active_rules = self.notification_rule_ids.filtered('active')
        _logger.debug(f'[Bulk Filter] Found {len(active_rules)} active rule(s)')
        
        if not active_rules:
            # No rules - but we still shouldn't search all partners
            # Return empty - notifications should have rules
            _logger.warning('[Bulk Filter] No active rules, returning empty (notifications should have rules)')
            return self.env['res.partner'].browse()
        
        # Group rules by model to build efficient domain queries
        rules_by_model = {}
        for rule in active_rules:
            model_name = rule.model_id.model if rule.model_id else None
            if model_name not in rules_by_model:
                rules_by_model[model_name] = []
            rules_by_model[model_name].append(rule)
        
        _logger.debug(f'[Bulk Filter] Rules grouped by model: {list(rules_by_model.keys())}')
        
        # Determine primary model to start from (most selective)
        # Priority: membership > discount > event.registration > res.partner
        # We MUST start from a related model, never from all partners
        primary_model = None
        if 'popcorn.membership' in rules_by_model:
            primary_model = 'popcorn.membership'
        elif 'popcorn.discount' in rules_by_model:
            primary_model = 'popcorn.discount'
        elif 'event.registration' in rules_by_model:
            primary_model = 'event.registration'
        elif 'res.partner' in rules_by_model:
            # Only use partner as primary if it's the ONLY model
            if len(rules_by_model) == 1:
                primary_model = 'res.partner'
            else:
                # If there are other models, use them instead
                primary_model = None
        
        _logger.debug(f'[Bulk Filter] Primary model: {primary_model}')
        
        # If no related model found, we can't optimize - return empty
        if not primary_model or primary_model == 'res.partner':
            _logger.warning(
                f'[Bulk Filter] No related model rules found (membership/discount/event). '
                f'Cannot optimize - returning empty. Rules are only on: {list(rules_by_model.keys())}'
            )
            return self.env['res.partner'].browse()
        
        # Partner domain for partner-level filters (only for additional partner rules)
        partner_domain = []
        matching_partner_ids = set()
        initial_partners = None
        
        # Process rules by model - start with primary model if it's a related model
        for model_name, rules in sorted(rules_by_model.items(), 
                                       key=lambda x: (x[0] != primary_model, x[0])):
            if model_name == 'res.partner':
                # Direct partner field rules - add to domain
                for rule in rules:
                    field_name = rule.field_id.name if rule.field_id else None
                    if not field_name:
                        continue
                    
                    # Convert value to appropriate type
                    value = rule.value
                    if rule.operator in ['=', '!=']:
                        # Try to convert boolean
                        if value.lower() == 'true':
                            value = True
                        elif value.lower() == 'false':
                            value = False
                        # Try to convert integer
                        elif value.isdigit():
                            value = int(value)
                    
                    # Build domain condition
                    if rule.operator == '=':
                        partner_domain.append((field_name, '=', value))
                    elif rule.operator == '!=':
                        partner_domain.append((field_name, '!=', value))
                    elif rule.operator == '<=':
                        partner_domain.append((field_name, '<=', int(value) if value.isdigit() else value))
                    elif rule.operator == '>=':
                        partner_domain.append((field_name, '>=', int(value) if value.isdigit() else value))
            
            elif model_name == 'popcorn.membership':
                # Membership rules - START FROM ACTIVE MEMBERSHIPS (optimization)
                membership_domain = []
                has_computed_field = False
                
                # ALWAYS start with active/frozen memberships filter (most selective)
                membership_domain.append(('state', 'in', ['active', 'frozen']))
                
                for rule in rules:
                    field_name = rule.field_id.name if rule.field_id else None
                    if not field_name:
                        continue
                    
                    # Skip state field if already added
                    if field_name == 'state':
                        continue
                    
                    # Check if field is computed (not stored)
                    field_info = self.env['popcorn.membership']._fields.get(field_name)
                    if field_info and not field_info.store:
                        # Computed field - will filter in Python later
                        has_computed_field = True
                        continue
                    
                    # Stored field - add to domain
                    value = rule.value
                    if value.lower() == 'true':
                        value = True
                    elif value.lower() == 'false':
                        value = False
                    elif value.isdigit():
                        value = int(value)
                    
                    if rule.operator == '=':
                        membership_domain.append((field_name, '=', value))
                    elif rule.operator == '<=':
                        membership_domain.append((field_name, '<=', int(value) if value.isdigit() else value))
                    elif rule.operator == '>=':
                        membership_domain.append((field_name, '>=', int(value) if value.isdigit() else value))
                    elif rule.operator == '!=':
                        membership_domain.append((field_name, '!=', value))
                
                # Find matching memberships (starting from active ones)
                _logger.debug(f'[Bulk Filter] Searching memberships with domain: {membership_domain}')
                memberships = self.env['popcorn.membership'].search(membership_domain)
                _logger.debug(f'[Bulk Filter] Found {len(memberships)} matching membership(s)')
                
                if has_computed_field:
                    # Filter by computed fields in Python
                    for membership in memberships:
                        # Evaluate computed field rules
                        all_rules_pass = True
                        for rule in rules:
                            field_name = rule.field_id.name
                            field_info = self.env['popcorn.membership']._fields.get(field_name)
                            if field_info and not field_info.store:
                                # Computed field - evaluate
                                field_value = getattr(membership, field_name, None)
                                # Convert value for comparison
                                comparison_value = rule._convert_value_to_type(field_value, rule.value)
                                if not rule._evaluate_condition(field_value, rule.operator, comparison_value):
                                    all_rules_pass = False
                                    break
                        
                        if all_rules_pass and membership.partner_id.id:
                            matching_partner_ids.add(membership.partner_id.id)
                else:
                    # All fields are stored - use membership partner IDs directly
                    membership_partner_ids = memberships.mapped('partner_id.id')
                    if initial_partners is None:
                        initial_partners = set(membership_partner_ids)
                    else:
                        initial_partners &= set(membership_partner_ids)
            
            elif model_name == 'event.registration':
                # Registration rules - START FROM UPCOMING EVENTS (optimization)
                registration_domain = []
                
                # ALWAYS start with upcoming events filter (most selective)
                registration_domain.append(('event_start_time', '>', fields.Datetime.now()))
                registration_domain.append(('state', 'in', ['open', 'done']))
                
                for rule in rules:
                    field_name = rule.field_id.name if rule.field_id else None
                    if not field_name:
                        continue
                    
                    # Skip fields already added
                    if field_name in ['event_start_time', 'state']:
                        continue
                    
                    value = rule.value
                    if value.lower() == 'true':
                        value = True
                    elif value.lower() == 'false':
                        value = False
                    elif value.isdigit():
                        value = int(value)
                    
                    if rule.operator == '=':
                        registration_domain.append((field_name, '=', value))
                    elif rule.operator == '!=':
                        registration_domain.append((field_name, '!=', value))
                
                # Find matching registrations (starting from upcoming ones)
                _logger.debug(f'[Bulk Filter] Searching registrations with domain: {registration_domain}')
                registrations = self.env['event.registration'].search(registration_domain)
                _logger.debug(f'[Bulk Filter] Found {len(registrations)} matching registration(s)')
                registration_partner_ids = registrations.mapped('partner_id.id')
                
                if initial_partners is None:
                    initial_partners = set(registration_partner_ids)
                else:
                    initial_partners &= set(registration_partner_ids)
            
            elif model_name == 'popcorn.discount':
                # Discount/coupon rules - START FROM ACTIVE DISCOUNTS (optimization)
                discount_domain = []
                
                # ALWAYS start with active discounts filter (most selective)
                discount_domain.append(('active', '=', True))
                
                for rule in rules:
                    field_name = rule.field_id.name if rule.field_id else None
                    if not field_name:
                        continue
                    
                    # Skip active field if already added
                    if field_name == 'active':
                        continue
                    
                    value = rule.value
                    if value.lower() == 'true':
                        value = True
                    elif value.lower() == 'false':
                        value = False
                    elif value.isdigit():
                        value = int(value)
                    
                    if rule.operator == '=':
                        discount_domain.append((field_name, '=', value))
                    elif rule.operator == '!=':
                        discount_domain.append((field_name, '!=', value))
                    elif rule.operator == '<=':
                        discount_domain.append((field_name, '<=', int(value) if value.isdigit() else value))
                    elif rule.operator == '>=':
                        discount_domain.append((field_name, '>=', int(value) if value.isdigit() else value))
                
                # Find matching discounts (starting from active ones)
                _logger.debug(f'[Bulk Filter] Searching discounts with domain: {discount_domain}')
                discounts = self.env['popcorn.discount'].search(discount_domain)
                _logger.debug(f'[Bulk Filter] Found {len(discounts)} matching discount(s)')
                
                # For discounts, we need to find partners who can use them
                # This depends on discount configuration (customer_type, partner_id, etc.)
                # For now, get partners from memberships that used these discounts
                discount_partner_ids = set()
                if discounts:
                    # Find memberships that used these discounts
                    memberships_with_discounts = self.env['popcorn.membership'].search([
                        ('applied_discount_id', 'in', discounts.ids),
                        ('state', 'in', ['active', 'frozen'])
                    ])
                    discount_partner_ids = set(memberships_with_discounts.mapped('partner_id.id'))
                
                if initial_partners is None:
                    initial_partners = discount_partner_ids
                else:
                    initial_partners &= discount_partner_ids
        
        # Combine results from different models (AND logic - all must match)
        final_partner_ids = None
        
        if matching_partner_ids:
            # Had computed fields - start with those IDs
            final_partner_ids = matching_partner_ids
            if initial_partners is not None:
                final_partner_ids &= initial_partners
        elif initial_partners is not None:
            # Only stored fields from related models
            final_partner_ids = initial_partners
        
        # Apply partner domain filters if any (AND with existing results)
        # Only apply to already-filtered partners, never search all partners
        if partner_domain and final_partner_ids:
            # Apply partner filters only to the partners we already found from related models
            partners = self.env['res.partner'].browse(list(final_partner_ids))
            # Filter in Python for partner-level rules (safer than searching all partners)
            filtered_partner_ids = set()
            for partner in partners:
                # Check if partner matches all partner domain rules
                matches = True
                for domain_item in partner_domain:
                    field_name = domain_item[0]
                    operator = domain_item[1]
                    value = domain_item[2]
                    
                    field_value = getattr(partner, field_name, None)
                    if operator == '=' and field_value != value:
                        matches = False
                        break
                    elif operator == '!=' and field_value == value:
                        matches = False
                        break
                    elif operator == '<=' and (field_value is None or field_value > value):
                        matches = False
                        break
                    elif operator == '>=' and (field_value is None or field_value < value):
                        matches = False
                        break
                
                if matches:
                    filtered_partner_ids.add(partner.id)
            
            final_partner_ids = filtered_partner_ids
            _logger.debug(f'[Bulk Filter] After partner domain filters: {len(final_partner_ids)} partner(s)')
        
        # If no related model rules matched, return empty (should not happen)
        if final_partner_ids is None:
            _logger.warning(
                f'[Bulk Filter] No partners found from related models. '
                f'This should not happen if rules are correct.'
            )
            return self.env['res.partner'].browse()
        
        # FINAL STEP: Filter by WeChat OpenID (always required for WeChat notifications)
        if final_partner_ids:
            partners_with_wechat = self.env['res.partner'].search([
                ('id', 'in', list(final_partner_ids)),
                ('wechat_openid', '!=', False),
                ('wechat_openid', '!=', ''),
            ])
            final_partner_ids = set(partners_with_wechat.ids)
            _logger.debug(f'[Bulk Filter] After WeChat OpenID filter: {len(final_partner_ids)} partner(s)')
        
        # Return as recordset
        result = self.env['res.partner'].browse(list(final_partner_ids)) if final_partner_ids else self.env['res.partner'].browse()
        _logger.info(f'[Bulk Filter] Notification "{self.name}": Returning {len(result)} matching partner(s) (from {len(final_partner_ids) if final_partner_ids else 0} IDs)')
        return result
    
    def _get_dynamic_content(self, partner, content, registration=None):
        """
        Replace dynamic placeholders in content with actual partner, membership, and event registration data
        
        :param partner: res.partner record
        :param content: String content with {placeholder} placeholders
        :param registration: Optional event.registration record to use for event-specific fields
        :return: Content with placeholders replaced
        """
        if not content:
            return content
            
        # Find all {field_name} placeholders
        placeholders = re.findall(r'\{(\w+)\}', content)
        
        # Get active membership for this partner
        active_membership = self.env['popcorn.membership'].search([
            ('partner_id', '=', partner.id),
            ('state', 'in', ['active', 'frozen'])
        ], limit=1)
        
        # Use provided registration, or search for upcoming event registration
        event_registration = registration
        if not event_registration:
            # Fall back to searching for upcoming registration (backward compatibility)
            event_registration = self.env['event.registration'].search([
                ('partner_id', '=', partner.id),
                ('state', 'in', ['open', 'done']),
                ('event_start_time', '>', fields.Datetime.now())
            ], order='event_start_time asc', limit=1)
        
        # Pass partner's timezone in context so computed fields use correct timezone
        eval_context = self.env.context.copy() if self.env.context else {}
        partner_tz = partner.tz or False
        if partner_tz:
            eval_context['tz'] = partner_tz
        
        for placeholder in placeholders:
            value = None
            
            # Try to get from partner first
            if hasattr(partner, placeholder):
                value = getattr(partner, placeholder, '')
            # Then try from active membership
            elif active_membership and hasattr(active_membership, placeholder):
                value = getattr(active_membership, placeholder, '')
            # Then try from event registration (either provided or found)
            elif event_registration and hasattr(event_registration, placeholder):
                # Evaluate with correct timezone context
                value = getattr(event_registration.with_context(eval_context), placeholder, '')
            
            # Handle different field types
            if value:
                if isinstance(value, models.BaseModel):
                    value = value.display_name if hasattr(value, 'display_name') else value.name
                elif isinstance(value, (int, float)):
                    value = str(value)
                elif hasattr(value, 'strftime'):  # Date/datetime
                    value = value.strftime('%Y-%m-%d')
                content = content.replace(f'{{{placeholder}}}', str(value))
            else:
                content = content.replace(f'{{{placeholder}}}', '')
        
        return content
    
    def get_notification_data_for_partner(self, partner, registration=None):
        """
        Get formatted notification data for display
        
        :param partner: res.partner record
        :param registration: Optional event.registration record to use for event-specific placeholders
        :return: Dict with notification data or None if rules don't match
        """
        self.ensure_one()
        
        if not self._evaluate_notification_for_partner(partner):
            return None
        
        # Process dynamic content (pass registration if provided)
        dynamic_title = self._get_dynamic_content(partner, self.title, registration=registration)
        dynamic_message = self._get_dynamic_content(partner, self.message, registration=registration)
        
        return {
            'id': self.id,
            'name': self.name,
            'type': self.notification_type,
            'title': dynamic_title,
            'message': dynamic_message,
            'banner_position': self.banner_position,
            'banner_style': self.banner_style,
            'popup_size': self.popup_size,
            'auto_dismiss': self.auto_dismiss,
            'dismiss_duration': self.dismiss_duration,
            'show_action_button': self.show_action_button,
            'action_button_text': self.action_button_text,
            'action_button_url': self.action_button_url,
            'show_once_per_session': self.show_once_per_session,
            'show_once_per_user': self.show_once_per_user,
            'sequence': self.sequence,
        }


class PopcornNotificationRule(models.Model):
    _name = 'popcorn.notification.rule'
    _description = 'Popcorn Notification Rule'
    _order = 'notification_id, sequence'

    name = fields.Char('Rule Name', required=True, translate=True)
    notification_id = fields.Many2one('popcorn.notification', string='Notification', 
                                     required=True, ondelete='cascade')
    sequence = fields.Integer('Sequence', default=10)
    
    model_id = fields.Many2one('ir.model', string='Model', required=True, ondelete='cascade',
                               domain=[('model', 'in', ['res.partner', 'popcorn.membership', 
                                                        'event.event', 'event.registration', 'popcorn.discount'])])
    field_id = fields.Many2one('ir.model.fields', string='Field', required=True, ondelete='cascade')
    operator = fields.Selection([
        ('=', 'Equal to'),
        ('>', 'Greater than'),
        ('<', 'Less than'),
        ('>=', 'Greater than or equal to'),
        ('<=', 'Less than or equal to'),
        ('!=', 'Not equal to'),
        ('in', 'In'),
        ('not in', 'Not in'),
        ('like', 'Contains'),
        ('ilike', 'Contains (case insensitive)'),
    ], string='Operator', default='=', required=True)
    value = fields.Char('Value', required=True, help="Threshold value for comparison")
    
    active = fields.Boolean('Active', default=True)
    description = fields.Text('Description', translate=True)
    
    @api.onchange('model_id')
    def _onchange_model_id(self):
        """Reset field_id when model changes"""
        if self.model_id:
            return {'domain': {'field_id': [('model_id', '=', self.model_id.id)]}}
        else:
            return {'domain': {'field_id': []}}
    
    def _evaluate_rule_for_partner(self, partner):
        """Evaluate if a partner meets this rule criteria"""
        if not self.active or not self.model_id or not self.field_id:
            return False
            
        try:
            # Get the model and field
            model_name = self.model_id.model
            field_name = self.field_id.name
            
            # Find records related to this partner
            records = self._find_records_for_partner(model_name, partner)
            
            # If no records found for non-partner models, rule fails
            if not records and model_name != 'res.partner':
                return False
            
            # Get field value based on the field type and operator
            field_value = self._get_field_value(records, field_name, model_name)
            
            # Convert value to appropriate type for comparison
            comparison_value = self._convert_value_to_type(field_value, self.value)
            
            # Evaluate the condition
            return self._evaluate_condition(field_value, self.operator, comparison_value)
            
        except Exception as e:
            # Log error and return False
            _logger.warning(f"Error evaluating notification rule {self.name}: {str(e)}")
            return False
    
    def _find_records_for_partner(self, model_name, partner):
        """Find records related to the partner in any model"""
        model = self.env[model_name]
        
        # If the model is res.partner, return the partner itself
        if model_name == 'res.partner':
            return partner
        
        # Try common partner relationship fields
        partner_fields = ['partner_id', 'user_id', 'contact_id', 'customer_id']
        
        for field in partner_fields:
            if hasattr(model, field):
                # Check if the field is a Many2one to res.partner
                field_info = model._fields.get(field)
                if field_info and field_info.comodel_name == 'res.partner':
                    # For membership model, only get active/frozen memberships
                    if model_name == 'popcorn.membership':
                        return model.search([
                            (field, '=', partner.id),
                            ('state', 'in', ['active', 'frozen'])
                        ], limit=1)  # Get only one active membership
                    # For event registration, get upcoming registrations
                    elif model_name == 'event.registration':
                        return model.search([
                            (field, '=', partner.id),
                            ('state', 'in', ['open', 'done']),
                            ('event_start_time', '>', fields.Datetime.now())
                        ], order='event_start_time asc', limit=1)  # Get next upcoming event
                    else:
                        return model.search([(field, '=', partner.id)])
        
        # If no relationship found, return empty recordset
        return model.browse()
    
    def _get_field_value(self, records, field_name, model_name):
        """Get field value from records based on field type and operator"""
        if not records:
            return False
        
        # If we have multiple records and operator is numeric, count them
        if len(records) > 1 and self.operator in ['=', '>', '<', '>=', '<=']:
            return len(records)
        
        # If we have one record, get the field value
        if len(records) == 1:
            record = records[0]
            if hasattr(record, field_name):
                return getattr(record, field_name, False)
            else:
                return False
        
        # If we have multiple records and operator is not numeric, return the recordset
        if len(records) > 1:
            return records
        
        return False
    
    def _convert_value_to_type(self, field_value, string_value):
        """Convert string value to appropriate type based on field value"""
        # Check for boolean FIRST (before int/float, since bool is subclass of int in Python!)
        if isinstance(field_value, bool) and type(field_value) == bool:
            # Convert string to boolean
            if isinstance(string_value, bool):
                return string_value
            return str(string_value).lower() in ('true', '1', 'yes', 'on')
        elif isinstance(field_value, (int, float)):
            try:
                return float(string_value)
            except ValueError:
                return string_value
        else:
            return string_value
    
    def _evaluate_condition(self, field_value, operator, comparison_value):
        """Evaluate the condition based on operator"""
        try:
            if operator == '=':
                return field_value == comparison_value
            elif operator == '!=':
                return field_value != comparison_value
            elif operator == '>':
                return field_value > comparison_value
            elif operator == '<':
                return field_value < comparison_value
            elif operator == '>=':
                return field_value >= comparison_value
            elif operator == '<=':
                return field_value <= comparison_value
            elif operator == 'in':
                return field_value in comparison_value
            elif operator == 'not in':
                return field_value not in comparison_value
            elif operator == 'like':
                return comparison_value in str(field_value)
            elif operator == 'ilike':
                return comparison_value.lower() in str(field_value).lower()
            else:
                return False
        except Exception:
            return False

    def _coerce_record_to_model(self, record, target_model_name):
        """Return a record of target_model_name related to the given record, or None.
        Handles common relationships needed by notifications (e.g., discount -> partner).
        """
        try:
            # Exact match
            if getattr(record, '_name', None) == target_model_name:
                return record
            # Discount -> Partner
            if target_model_name == 'res.partner' and hasattr(record, 'partner_id') and record.partner_id:
                return record.partner_id
            # Registration -> Partner
            if target_model_name == 'res.partner' and hasattr(record, 'partner_id') and record.partner_id:
                return record.partner_id
            # Membership -> Partner
            if target_model_name == 'res.partner' and hasattr(record, 'partner_id') and record.partner_id:
                return record.partner_id
        except Exception:
            return None
        return None

    def _evaluate_rule_for_record(self, record):
        """Evaluate a rule for an arbitrary record (of any model)."""
        if not self.active or not self.model_id or not self.field_id:
            return False
        try:
            model_name = self.model_id.model
            # Attempt to coerce to required model
            coerced = self._coerce_record_to_model(record, model_name)
            if not coerced:
                return False
            field_name = self.field_id.name
            if hasattr(coerced, field_name):
                field_value = getattr(coerced, field_name, False)
            else:
                field_value = False
            comparison_value = self._convert_value_to_type(field_value, self.value)
            return self._evaluate_condition(field_value, self.operator, comparison_value)
        except Exception:
            return False

    def _evaluate_rule_for_record_verbose(self, record):
        """Like _evaluate_rule_for_record, but returns (bool, debug_string) for tracing."""
        if not self.active or not self.model_id or not self.field_id:
            return False, f"Rule {self.id} inactive or missing model/field."
        try:
            model_name = self.model_id.model
            # Attempt to coerce to required model
            coerced = self._coerce_record_to_model(record, model_name)
            if not coerced:
                return False, f"Model mismatch and no related record found: rule model={model_name}, record={getattr(record, '_name', None)}."
            field_name = self.field_id.name
            operator = self.operator
            val_required = self.value
            if hasattr(coerced, field_name):
                field_value = getattr(coerced, field_name, False)
            else:
                field_value = None
            comparison_value = self._convert_value_to_type(field_value, val_required)
            comparison_passed = self._evaluate_condition(field_value, operator, comparison_value)
            msg = (
                f"model={model_name}, field={field_name}, op={operator}, "
                f"record_value={field_value!r}, compare_to={comparison_value!r}, passed={comparison_passed}"
            )
            return comparison_passed, msg
        except Exception as e:
            return False, f"EXC: {str(e)} in rule eval."

