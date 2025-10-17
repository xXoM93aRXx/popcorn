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
    
    def _get_dynamic_content(self, partner, content):
        """Replace dynamic placeholders in content with actual partner, membership, and event registration data"""
        if not content:
            return content
            
        # Find all {field_name} placeholders
        placeholders = re.findall(r'\{(\w+)\}', content)
        
        # Get active membership for this partner
        active_membership = self.env['popcorn.membership'].search([
            ('partner_id', '=', partner.id),
            ('state', 'in', ['active', 'frozen'])
        ], limit=1)
        
        # Get upcoming event registration for this partner
        upcoming_registration = self.env['event.registration'].search([
            ('partner_id', '=', partner.id),
            ('state', 'in', ['open', 'done']),
            ('event_start_time', '>', fields.Datetime.now())
        ], order='event_start_time asc', limit=1)
        
        for placeholder in placeholders:
            value = None
            
            # Try to get from partner first
            if hasattr(partner, placeholder):
                value = getattr(partner, placeholder, '')
            # Then try from active membership
            elif active_membership and hasattr(active_membership, placeholder):
                value = getattr(active_membership, placeholder, '')
            # Then try from upcoming event registration
            elif upcoming_registration and hasattr(upcoming_registration, placeholder):
                value = getattr(upcoming_registration, placeholder, '')
            
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
    
    def get_notification_data_for_partner(self, partner):
        """Get formatted notification data for display"""
        self.ensure_one()
        
        if not self._evaluate_notification_for_partner(partner):
            return None
        
        # Process dynamic content
        dynamic_title = self._get_dynamic_content(partner, self.title)
        dynamic_message = self._get_dynamic_content(partner, self.message)
        
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
                                                        'event.event', 'event.registration'])])
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

