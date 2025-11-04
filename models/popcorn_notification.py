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
    
    # --- BEGIN: WeChat Notification Fields ---
    send_wechat_notification = fields.Boolean(
        string='Send WeChat Notification',
        default=False,
        help='Enable to send this notification via WeChat Official Account'
    )
    wechat_notification_message = fields.Html(
        string='WeChat Notification Message',
        translate=True,
        help='Optional message body to send via WeChat (overrides default message if provided)'
    )
    wechat_template_id = fields.Char(
        string='WeChat Template ID',
        help='Template message ID from WeChat Official Account platform'
    )
    wechat_first_field = fields.Char(
        string='First Field',
        help='Field to use for "first" placeholder. Use {field_name} syntax, e.g., {name}, {event_name}'
    )
    wechat_keyword1_field = fields.Char(
        string='Keyword1 Field',
        help='Field to use for "keyword1" placeholder. Use {field_name} syntax'
    )
    wechat_keyword2_field = fields.Char(
        string='Keyword2 Field',
        help='Field to use for "keyword2" placeholder. Use {field_name} syntax'
    )
    wechat_keyword3_field = fields.Char(
        string='Keyword3 Field',
        help='Field to use for "keyword3" placeholder. Use {field_name} syntax'
    )
    wechat_keyword4_field = fields.Char(
        string='Keyword4 Field',
        help='Field to use for "keyword4" placeholder. Use {field_name} syntax'
    )
    wechat_remark_field = fields.Char(
        string='Remark Field',
        help='Field to use for "remark" placeholder. Use {field_name} syntax'
    )
    last_wechat_cron_run = fields.Datetime(
        string='Last Cron Run',
        help='Timestamp of the last cron evaluation for this notification'
    )
    wechat_sent_partner_ids = fields.Many2many(
        'res.partner',
        'popcorn_notification_wechat_sent_rel',
        'notification_id',
        'partner_id',
        string='WeChat Sent To',
        help='Partners who have already received this WeChat notification'
    )
    # --- END: WeChat Notification Fields ---

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
            # Then try from upcoming event registration
            elif upcoming_registration and hasattr(upcoming_registration, placeholder):
                # Evaluate with correct timezone context
                value = getattr(upcoming_registration.with_context(eval_context), placeholder, '')
            
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

    def _evaluate_notification_for_discount(self, discount):
        """Evaluate if a discount record matches all active rules for this notification."""
        self.ensure_one()
        if not self.active:
            _logger.info(f"[WeChatCron] Notification {self.id}: inactive (discount {discount.id}).")
            return False
        if not self.notification_rule_ids.filtered('active'):
            _logger.info(f"[WeChatCron] Notification {self.id}: no active rules (discount {discount.id}), auto-pass.")
            return True
        for rule in self.notification_rule_ids.filtered('active'):
            rule_result, rule_msg = rule._evaluate_rule_for_record_verbose(discount)
            _logger.info(f"[WeChatCron] Notification ID={self.id} Discount ID={discount.id} Rule ID={rule.id}: {rule_msg}")
            if not rule_result:
                return False
        return True

    @api.model
    def cron_send_wechat_notifications(self, limit_partners=200):
        """Cron entrypoint: send expiring-discount notifications directly to affected partners."""
        notifications = self.sudo().search([
            ('active', '=', True),
            ('send_wechat_notification', '=', True),
            ('wechat_template_id', '!=', False),
        ])
        if not notifications:
            _logger.info("[WeChatCron] No eligible notifications found (active & enabled & template set)")
            return True
        Discount = self.env['popcorn.discount'].sudo()
        for notification in notifications:
            processed = 0
            discounts = Discount.search([
                ('partner_id', '!=', False),
            ])
            _logger.info(
                "[WeChatCron] Notification id=%s name=%s: checking discounts=%s",
                notification.id, notification.name, len(discounts)
            )
            partners_done = set()
            for disc in discounts:
                partner = disc.partner_id
                if not partner:
                    _logger.info(f"[WeChatCron] SKIP: Notification {notification.id}, discount {disc.id} has no partner.")
                    continue
                if not partner.wechat_openid:
                    _logger.info(f"[WeChatCron] SKIP: Notification {notification.id}, partner {partner.id} (discount {disc.id}) has no WeChat OpenID.")
                    continue
                if notification.show_once_per_user and partner in notification.wechat_sent_partner_ids:
                    _logger.info(f"[WeChatCron] SKIP: Notification {notification.id}, partner {partner.id} (discount {disc.id}) already notified (show_once_per_user).")
                    continue
                if partner.id in partners_done:
                    _logger.info(f"[WeChatCron] SKIP: Notification {notification.id}, partner {partner.id} (discount {disc.id}) already processed in this run.")
                    continue
                if not notification._evaluate_notification_for_discount(disc):
                    _logger.info(f"[WeChatCron] SKIP: Notification {notification.id}, discount {disc.id}, partner {partner.id}: _evaluate_notification_for_discount returned False.")
                    continue
                sent = notification.send_wechat_template_message(partner)
                if sent:
                    processed += 1
                    partners_done.add(partner.id)
                    if notification.show_once_per_user:
                        notification.wechat_sent_partner_ids = [(4, partner.id)]
                    _logger.info("[WeChatCron] Sent WeChat notification (discount %s) to partner %s (processed %s)", disc.id, partner.id, processed)
                    if processed >= limit_partners:
                        break
            notification.last_wechat_cron_run = fields.Datetime.now()
            _logger.info("[WeChatCron] Finished notification id=%s name=%s processed=%s", notification.id, notification.name, processed)
        return True

    def send_wechat_template_message(self, partner):
        """Send WeChat template message to partner"""
        self.ensure_one()
        if not hasattr(self, 'send_wechat_notification') or not self.send_wechat_notification:
            return False
        if not partner.wechat_openid:
            _logger.info(f"Partner {partner.id} does not have WeChat OpenID")
            return False
        if not self.wechat_template_id:
            _logger.info(f"Notification {self.id} does not have WeChat Template ID configured")
            return False
        try:
            access_token = self._get_wechat_access_token()
            if not access_token:
                _logger.error("Could not obtain WeChat access token")
                return False
            template_data = self._prepare_wechat_template_data(partner)
            success = self._send_wechat_message(
                access_token,
                partner.wechat_openid,
                self.wechat_template_id,
                template_data
            )
            if success:
                _logger.info(f"WeChat template message sent to partner {partner.id}")
            return success
        except Exception as e:
            _logger.error(f"Error sending WeChat template message: {str(e)}", exc_info=True)
            return False
    # Supporting methods _get_wechat_access_token, _prepare_wechat_template_data, _send_wechat_message go here
    def _get_wechat_access_token(self):
        wechat_config = self.env['wechat.config'].sudo().search([('active', '=', True)], limit=1)
        if not wechat_config or not wechat_config.app_id or not wechat_config.app_secret:
            _logger.error("WeChat configuration not found or incomplete")
            return None
        cache_key = f'wechat_access_token_{wechat_config.app_id}'
        cached_token = self.env['ir.config_parameter'].sudo().get_param(f'popcorn.wechat.{cache_key}')
        cached_token_time = self.env['ir.config_parameter'].sudo().get_param(f'popcorn.wechat.{cache_key}_time')
        from datetime import datetime, timedelta
        if cached_token and cached_token_time:
            try:
                token_time = datetime.fromisoformat(cached_token_time)
                if (datetime.now() - token_time) < timedelta(hours=1.9):
                    return cached_token
            except:
                pass
        import requests
        url = f'https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={wechat_config.app_id}&secret={wechat_config.app_secret}'
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            if 'access_token' in data:
                access_token = data['access_token']
                self.env['ir.config_parameter'].sudo().set_param(f'popcorn.wechat.{cache_key}', access_token)
                self.env['ir.config_parameter'].sudo().set_param(f'popcorn.wechat.{cache_key}_time', datetime.now().isoformat())
                _logger.info("WeChat access token retrieved successfully")
                return access_token
            else:
                error_msg = data.get('errmsg', 'Unknown error')
                _logger.error(f"WeChat token error: {error_msg}")
                return None
        except Exception as e:
            _logger.error(f"WeChat token request failed: {str(e)}")
            return None
    def _prepare_wechat_template_data(self, partner):
        template_data = {}
        def get_field_value(field_config):
            if not field_config:
                return ''
            if field_config.startswith('{') and field_config.endswith('}'):
                field_name = field_config.strip('{}')
                return self._get_dynamic_content(partner, f'{{{field_name}}}')
            else:
                return field_config
        if hasattr(self, 'wechat_first_field') and self.wechat_first_field:
            first_value = get_field_value(self.wechat_first_field)
            if first_value:
                template_data['first'] = {'value': first_value[:50], 'color': '#173177'}
        else:
            title = self._get_dynamic_content(partner, self.title)
            if title:
                template_data['first'] = {'value': title[:50], 'color': '#173177'}
        keyword_fields = [
            ('keyword1', self.wechat_keyword1_field),
            ('keyword2', self.wechat_keyword2_field),
            ('keyword3', self.wechat_keyword3_field),
            ('keyword4', self.wechat_keyword4_field)
        ]
        for keyword_name, field_config in keyword_fields:
            if field_config:
                keyword_value = get_field_value(field_config)
                if keyword_value:
                    template_data[keyword_name] = {'value': keyword_value[:20], 'color': '#173177'}
        if hasattr(self, 'wechat_remark_field') and self.wechat_remark_field:
            remark_value = get_field_value(self.wechat_remark_field)
            if remark_value:
                template_data['remark'] = {'value': remark_value[:100], 'color': '#173177'}
        return template_data
    def _send_wechat_message(self, access_token, openid, template_id, data):
        import requests
        url = f'https://api.weixin.qq.com/cgi-bin/message/template/send?access_token={access_token}'
        payload = {
            'touser': openid,
            'template_id': template_id,
            'data': data
        }
        if self.show_action_button and self.action_button_url:
            payload['url'] = self.action_button_url
        try:
            _logger.info("[WeChatSend] POST %s payload=%s", url, payload)
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            result = response.json()
            _logger.info("[WeChatSend] response=%s", result)
            if result.get('errcode') == 0:
                return True
            else:
                error_msg = result.get('errmsg', 'Unknown error')
                _logger.error("[WeChatSend] failed errcode=%s errmsg=%s", result.get('errcode'), error_msg)
                return False
        except Exception as e:
            _logger.error("[WeChatSend] HTTP error: %s", str(e))
            return False


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

