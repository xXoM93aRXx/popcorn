# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class Badge(models.Model):
    _name = 'popcorn.badge'
    _description = 'Badge'
    _order = 'name'

    name = fields.Char('Badge Name', required=True, translate=True)
    description = fields.Text('Description', translate=True)
    image = fields.Binary('Badge Image', attachment=True)
    image_filename = fields.Char("Image Filename")
    badge_rule_ids = fields.One2many('popcorn.badge.rule', 'badge_id', string='Badge Rules')
    active = fields.Boolean('Active', default=True)
    prize_popcorn_money = fields.Float(
        'Prize (Popcorn Money)',
        default=0.0,
        digits=(16, 2),
        help='Amount of Popcorn Money awarded to the partner when this badge is first earned'
    )
    prize_expiry_days = fields.Integer(
        'Prize Expiry (Days)',
        default=0,
        help='Number of days before the prize Popcorn Money expires. 0 = never expires.'
    )
    is_diversity_badge = fields.Boolean(
        'Diversity Badge',
        default=False,
        help='If enabled, clicking this badge in the portal shows the Mortal Kombat style host unlock screen'
    )
    is_variety_badge = fields.Boolean(
        'Variety Badge',
        default=False,
        help='If enabled, clicking this badge in the portal shows the constellation sky topic unlock screen'
    )
    variety_locked_teaser = fields.Char(
        'Locked Teaser',
        translate=True,
        default="Learn cool facts about me when I'm unlocked!",
        help='Text shown in the info card instead of the description when a constellation is locked'
    )

    # Computed field to show if user has earned this badge
    earned = fields.Boolean('Earned', compute='_compute_earned', store=False)
    
    @api.depends_context('uid')
    def _compute_earned(self):
        """Compute if the current user has earned this badge"""
        for badge in self:
            if self.env.context.get('uid'):
                partner = self.env.user.partner_id
                badge.earned = badge._evaluate_badge_for_partner(partner)
            else:
                badge.earned = False
    
    def _evaluate_badge_for_partner(self, partner):
        """Evaluate if a partner has earned this badge based on all rules.
        Once a badge is in permanently_earned_badge_ids it is always considered earned."""
        if self in partner.permanently_earned_badge_ids:
            return True

        if not self.badge_rule_ids.filtered('active'):
            return False

        for rule in self.badge_rule_ids.filtered('active'):
            if not rule._evaluate_rule_for_partner(partner):
                return False
        return True

    def get_remaining_text_for_partner(self, partner):
        """Return rendered remaining text based on rule templates for a partner."""
        self.ensure_one()
        if not partner or self._evaluate_badge_for_partner(partner):
            return ''

        texts = []
        for rule in self.badge_rule_ids.filtered('active'):
            records = rule._find_records_for_partner(rule.model_id.model, partner)
            if rule.use_time_filter and rule.time_filter_months > 0 and records:
                records = rule._apply_time_filter(records)
            field_value = rule._get_field_value(records, rule.field_id.name, rule.model_id.model)
            comparison_value = rule._convert_value_to_type(field_value, rule.value)
            remaining = rule._get_remaining_amount(field_value, comparison_value)
            if remaining and remaining > 0 and rule.remaining_text_template:
                texts.append(rule._render_remaining_text(remaining))

        return ' / '.join(texts)
    
    @api.model
    def evaluate_for_partner_xmlrpc(self, badge_id, partner_id):
        """Public method to evaluate if a badge is earned by a partner (for XML-RPC)"""
        badge = self.browse(badge_id)
        partner = self.env['res.partner'].browse(partner_id)
        return badge._evaluate_badge_for_partner(partner)


class BadgeRule(models.Model):
    _name = 'popcorn.badge.rule'
    _description = 'Badge Rule'
    _order = 'badge_id, sequence'

    name = fields.Char('Rule Name', required=True, translate=True)
    badge_id = fields.Many2one('popcorn.badge', string='Badge', required=True, ondelete='cascade')
    sequence = fields.Integer('Sequence', default=10)
    
    model_id = fields.Many2one('ir.model', string='Model', required=True, ondelete='cascade',
                               domain=[('model', 'in', ['res.partner', 'event.event', 'event.registration'])]
                               )
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
    remaining_text_template = fields.Char(
        string='Remaining Text',
        help="Use {remaining} as a placeholder, e.g. '{remaining} more to earn this badge'"
    )
    
    # Time-based filtering
    use_time_filter = fields.Boolean('Filter by Time Period', default=False,
                                      help="If enabled, only count records within the specified time period")
    time_filter_months = fields.Integer('Time Period (Months)', default=0,
                                       help="Number of months for the time period")
    time_filter_field = fields.Char('Date Field Name', default='create_date',
                                    help="Name of the date field to filter on (e.g., 'create_date', 'date_begin')")
    time_filter_anchor_date = fields.Date('Start Date (Anchor)', 
                                          help="Fixed start date for the time window. If not set, counts backwards from today.")
    
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
        """Evaluate if a partner meets this rule criteria - Universal approach"""
        if not self.active or not self.model_id or not self.field_id:
            return False
            
        try:
            # Get the model and field
            model_name = self.model_id.model
            field_name = self.field_id.name
            
            # Special case: distinct hosts count evaluation
            if field_name == 'distinct_hosts_count_in_period':
                return self._evaluate_distinct_hosts_rule(partner)

            # Special case: distinct topics count (event tags in the "Topic" category)
            if field_name == 'distinct_topics_count_in_period':
                return self._evaluate_distinct_topics_rule(partner)
            
            # Universal approach: Find records related to this partner
            records = self._find_records_for_partner(model_name, partner)
            
            import logging
            _logger = logging.getLogger(__name__)
            _logger.info(f"Badge Rule {self.name} for partner {partner.id}: Found {len(records)} total records")
            
            # Apply time filtering if enabled
            if self.use_time_filter and self.time_filter_months > 0 and records:
                records = self._apply_time_filter(records)
            
            # Get field value based on the field type and operator
            field_value = self._get_field_value(records, field_name, model_name)
            
            # Convert value to appropriate type for comparison
            comparison_value = self._convert_value_to_type(field_value, self.value)
            
            # Evaluate the condition
            result = self._evaluate_condition(field_value, self.operator, comparison_value)
            
            _logger.info(f"Badge Rule {self.name} for partner {partner.id}: {len(records)} records, value={field_value}, operator={self.operator}, comparison={comparison_value}, result={result}")
            
            return result
            
        except Exception as e:
            # Log error and return False
            import logging
            _logger = logging.getLogger(__name__)
            _logger.warning(f"Error evaluating badge rule {self.name}: {str(e)}")
            return False

    def _get_remaining_amount(self, field_value, comparison_value):
        """Return remaining amount for numeric comparisons, or None."""
        if not isinstance(field_value, (int, float)) or not isinstance(comparison_value, (int, float)):
            return None

        if self.operator == '>=':
            return max(0, comparison_value - field_value)
        if self.operator == '>':
            return max(0, (comparison_value + 1) - field_value)
        if self.operator == '=':
            return abs(comparison_value - field_value)
        if self.operator == '<=':
            return max(0, field_value - comparison_value)
        if self.operator == '<':
            return max(0, field_value - (comparison_value - 1))
        return None

    def _render_remaining_text(self, remaining):
        """Render the remaining text template with the remaining value."""
        template = self.remaining_text_template or ''
        if isinstance(remaining, float) and remaining.is_integer():
            remaining_value = str(int(remaining))
        else:
            remaining_value = str(remaining)
        return template.replace('{remaining}', remaining_value)
    
    def _evaluate_distinct_hosts_rule(self, partner):
        """Evaluate distinct hosts count rule within time period"""
        try:
            from datetime import datetime, timedelta
            import logging
            _logger = logging.getLogger(__name__)
            
            # Rolling window ending today, optionally capped by anchor date as earliest start
            cutoff_end = datetime.now()
            cutoff_start = cutoff_end - timedelta(days=self.time_filter_months * 30)
            if self.time_filter_anchor_date:
                anchor = datetime.combine(self.time_filter_anchor_date, datetime.min.time())
                cutoff_start = max(cutoff_start, anchor)
            _logger.info(f"Badge Rule {self.name} for partner {partner.id}: Using rolling window {cutoff_start} to {cutoff_end}")
            
            # Get all non-cancelled registrations for this partner within time period
            attended_registrations = self.env['event.registration'].search([
                ('partner_id', '=', partner.id),
                ('state', '!=', 'cancel'),
                ('create_date', '>=', cutoff_start.strftime('%Y-%m-%d %H:%M:%S')),
                ('create_date', '<=', cutoff_end.strftime('%Y-%m-%d %H:%M:%S'))
            ])
            
            # Get all unique host IDs from these registrations
            unique_host_ids = attended_registrations.mapped('event_id.host_id').filtered('id')
            unique_host_ids_list = list(set(unique_host_ids.mapped('id')))
            
            distinct_hosts_count = len(unique_host_ids_list)
            
            # Convert comparison value to integer
            comparison_value = int(self.value) if self.value.isdigit() else 0
            
            # Evaluate the condition
            result = self._evaluate_condition(distinct_hosts_count, self.operator, comparison_value)
            
            _logger.info(f"Badge Rule {self.name} for partner {partner.id}: Found {distinct_hosts_count} distinct hosts (needed: {comparison_value}), result={result}")
            
            return result
            
        except Exception as e:
            import logging
            _logger = logging.getLogger(__name__)
            _logger.warning(f"Error evaluating distinct hosts rule {self.name}: {str(e)}")
            return False
    
    def _evaluate_distinct_topics_rule(self, partner):
        """Count distinct event tags in the 'Topic' category across non-cancelled registrations."""
        try:
            from datetime import datetime, timedelta
            import logging
            _logger = logging.getLogger(__name__)

            domain = [
                ('partner_id', '=', partner.id),
                ('state', '!=', 'cancel'),
            ]
            if self.time_filter_anchor_date:
                anchor = datetime.combine(self.time_filter_anchor_date, datetime.min.time())
                domain.append(('create_date', '>=', anchor.strftime('%Y-%m-%d %H:%M:%S')))

            registrations = self.env['event.registration'].search(domain)

            topic_ids = set()
            for reg in registrations:
                for tag in reg.event_id.tag_ids:
                    if tag.category_id.name == 'Topics':
                        topic_ids.add(tag.id)

            distinct_count = len(topic_ids)
            comparison_value = int(self.value) if self.value.isdigit() else 0
            result = self._evaluate_condition(distinct_count, self.operator, comparison_value)

            _logger.info(
                'Badge Rule %s for partner %s: distinct_topics=%s, needed %s %s, result=%s',
                self.name, partner.id, distinct_count, self.operator, comparison_value, result,
            )
            return result

        except Exception as e:
            import logging
            logging.getLogger(__name__).warning('Error evaluating distinct_topics_count_in_period: %s', e)
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
                    domain = [(field, '=', partner.id)]
                    # Never count cancelled registrations toward any badge
                    if model_name == 'event.registration':
                        domain.append(('state', '!=', 'cancel'))
                    return model.search(domain)
        
        # Try reverse relationships (One2many/Many2many from partner)
        partner_field_name = model_name.replace('.', '_')
        if hasattr(partner, partner_field_name):
            return getattr(partner, partner_field_name)
        
        # Try to find records where partner appears in any field
        # This is a fallback for complex relationships
        try:
            # Search for records where partner appears in any field
            domain = []
            for field_name, field_info in model._fields.items():
                if field_info.comodel_name == 'res.partner':
                    domain.append((field_name, '=', partner.id))
            
            if domain:
                return model.search(domain)
        except:
            pass
        
        # If no relationship found, return empty recordset
        return model.browse()
    
    def _apply_time_filter(self, records):
        """Apply time-based filter to records"""
        if not records or not self.use_time_filter or not self.time_filter_months:
            return records
        
        try:
            from datetime import datetime, timedelta
            import logging
            _logger = logging.getLogger(__name__)
            
            # Rolling window ending today, optionally capped by anchor date as earliest start
            cutoff_end = datetime.now()
            cutoff_start = cutoff_end - timedelta(days=self.time_filter_months * 30)
            if self.time_filter_anchor_date:
                anchor = datetime.combine(self.time_filter_anchor_date, datetime.min.time())
                cutoff_start = max(cutoff_start, anchor)
            _logger.info(f"Badge Rule {self.name}: Using rolling window {cutoff_start} to {cutoff_end}")
            
            # Get the date field to filter on
            date_field = self.time_filter_field or 'create_date'
            
            # Get the model from the recordset
            model = records._name
            
            # Get field info safely (without triggering singleton error)
            field_info = records._fields.get(date_field)
            if not field_info:
                import logging
                _logger = logging.getLogger(__name__)
                _logger.warning(f"Field {date_field} not found in model {model}")
                return records.browse()
            
            # Check if it's a date/datetime field
            if field_info.type not in ('datetime', 'date'):
                import logging
                _logger = logging.getLogger(__name__)
                _logger.warning(f"Field {date_field} is not a date/datetime field (type: {field_info.type})")
                return records.browse()
            
            # Format dates based on field type
            if field_info.type == 'datetime':
                cutoff_start_str = cutoff_start.strftime('%Y-%m-%d %H:%M:%S')
                cutoff_end_str = cutoff_end.strftime('%Y-%m-%d %H:%M:%S')
            else:
                cutoff_start_str = cutoff_start.strftime('%Y-%m-%d')
                cutoff_end_str = cutoff_end.strftime('%Y-%m-%d')
            
            # Search with the filtered domain (within date range)
            domain = [
                ('id', 'in', records.ids),
                (date_field, '>=', cutoff_start_str),
                (date_field, '<=', cutoff_end_str)
            ]
            
            filtered_records = records.browse().search(domain)
            _logger.info(f"Badge Rule {self.name}: Filtered {len(records)} down to {len(filtered_records)} records in time window")
            return filtered_records
            
        except Exception as e:
            import logging
            _logger = logging.getLogger(__name__)
            _logger.warning(f"Error applying time filter: {str(e)}")
            return records
    
    def _get_field_value(self, records, field_name, model_name):
        """Get field value from records based on field type and operator"""
        if not records:
            return 0  # Return 0 instead of False for counting
        
        # For numeric operators (>, <, >=, <=), we're counting records, not reading field values
        if self.operator in ['>', '<', '>=', '<=']:
            # When evaluating "count >= value", we return the count of records
            return len(records)
        
        # Special case: If we're looking for a relationship field (like partner_id) 
        # and the operator is numeric, we want to count the records
        if self.operator in ['=']:
            # Check if the field is a relationship field
            if hasattr(records[0], field_name):
                field_info = records[0]._fields.get(field_name)
                if field_info and field_info.type in ['many2one', 'one2many', 'many2many']:
                    # For relationship fields, return count when using numeric comparison
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
        
        return 0  # Return 0 instead of False
    
    def _convert_value_to_type(self, field_value, string_value):
        """Convert string value to appropriate type based on field value"""
        # If comparing with empty string for "not empty" check, return empty string as-is
        if string_value == '':
            return ''
            
        # If the field value is a boolean (selection field), try to convert the string value accordingly
        if isinstance(field_value, bool):
            # If string value is 'False', convert to False boolean
            if string_value.lower() in ('false', 'False', '0', 'no', 'off'):
                return False
            # For other values, treat as boolean
            return string_value.lower() in ('true', '1', 'yes', 'on')
            
        if isinstance(field_value, (int, float)):
            try:
                return float(string_value)
            except ValueError:
                return string_value
        else:
            return string_value
    
    def _evaluate_condition(self, field_value, operator, comparison_value):
        """Evaluate the condition based on operator"""
        try:
            # Check for empty values when comparing with != and empty string or 'False'
            # This handles the case where we want to check if a field is not empty
            if operator == '!=' and (comparison_value == '' or comparison_value == 'False'):
                # For "not equal to empty", we want to check if the field has a value
                # Empty values in Odoo can be: None, False, '', 0, 0.0, []
                
                # Check if value is explicitly None
                if field_value is None:
                    return False
                
                # Check if value is False (empty selection field or False boolean)
                if field_value is False:
                    return False
                
                # Check if value is empty string
                if field_value == '':
                    return False
                
                # Check if value is empty list or empty recordset
                if isinstance(field_value, (list, tuple)) and len(field_value) == 0:
                    return False
                
                # Check if it's an empty recordset (Odoo's browse record)
                if hasattr(field_value, '__len__') and len(field_value) == 0:
                    return False
                
                # If we get here, the field has a non-empty value
                return True
            
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


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Placeholder fields used as badge rule field references for special-case evaluators
    distinct_topics_count_in_period = fields.Integer(
        string='Distinct Topics Count (Period)',
        compute='_compute_distinct_topics_count_in_period',
        store=False,
        help='Number of distinct event topics (tags in the Topic category) attended (used by badge rules)'
    )

    def _compute_distinct_topics_count_in_period(self):
        for partner in self:
            partner.distinct_topics_count_in_period = 0

    badge_ids = fields.Many2many('popcorn.badge', 'partner_badge_rel', 'partner_id', 'badge_id',
                                 string='Available Badges', compute='_compute_badge_ids', store=False)
    earned_badge_ids = fields.Many2many('popcorn.badge', 'partner_earned_badge_rel', 'partner_id', 'badge_id',
                                       string='Earned Badges', compute='_compute_earned_badge_ids', store=False)
    notified_badge_ids = fields.Many2many('popcorn.badge', 'partner_notified_badge_rel', 'partner_id', 'badge_id',
                                         string='Notified Badges',
                                         help='Badges whose earn animation has already been shown to this partner')
    permanently_earned_badge_ids = fields.Many2many('popcorn.badge', 'partner_permanent_badge_rel', 'partner_id', 'badge_id',
                                                    string='Permanently Earned Badges',
                                                    help='Badges permanently awarded to this partner — once earned, never lost')
    
    def _compute_badge_ids(self):
        """Compute all available badges for this partner"""
        for partner in self:
            partner.badge_ids = self.env['popcorn.badge'].search([('active', '=', True)])
    
    def _compute_earned_badge_ids(self):
        """Compute badges that this partner has earned"""
        for partner in self:
            earned_badges = self.env['popcorn.badge']
            for badge in self.env['popcorn.badge'].search([('active', '=', True)]):
                if badge._evaluate_badge_for_partner(partner):
                    earned_badges |= badge
            partner.earned_badge_ids = earned_badges
    
    def evaluate_for_partner(self, partner_id):
        """Public method to evaluate if this badge is earned by a partner
        This can be called from XML-RPC or other external interfaces
        """
        partner = self.env['res.partner'].browse(partner_id)
        return self._evaluate_badge_for_partner(partner)
