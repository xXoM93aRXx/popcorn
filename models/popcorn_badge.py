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
        """Evaluate if a partner has earned this badge based on all rules"""
        if not self.badge_rule_ids.filtered('active'):
            return False
            
        for rule in self.badge_rule_ids.filtered('active'):
            if not rule._evaluate_rule_for_partner(partner):
                return False
        return True


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
            
            # Universal approach: Find records related to this partner
            records = self._find_records_for_partner(model_name, partner)
            
            # Get field value based on the field type and operator
            field_value = self._get_field_value(records, field_name, model_name)
            
            # Convert value to appropriate type for comparison
            comparison_value = self._convert_value_to_type(field_value, self.value)
            
            # Evaluate the condition
            return self._evaluate_condition(field_value, self.operator, comparison_value)
            
        except Exception as e:
            # Log error and return False
            import logging
            _logger = logging.getLogger(__name__)
            _logger.warning(f"Error evaluating badge rule {self.name}: {str(e)}")
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
                    return model.search([(field, '=', partner.id)])
        
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
    
    def _get_field_value(self, records, field_name, model_name):
        """Get field value from records based on field type and operator"""
        if not records:
            return False
        
        # Special case: If we're looking for a relationship field (like partner_id) 
        # and the operator is numeric, we want to count the records, not get the field value
        if self.operator in ['=', '>', '<', '>=', '<=']:
            # Check if the field is a relationship field
            if hasattr(records[0], field_name):
                field_info = records[0]._fields.get(field_name)
                if field_info and field_info.type in ['many2one', 'one2many', 'many2many']:
                    # For relationship fields with numeric operators, return count
                    return len(records)
        
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
        if isinstance(field_value, (int, float)):
            try:
                return float(string_value)
            except ValueError:
                return string_value
        elif isinstance(field_value, bool):
            return string_value.lower() in ('true', '1', 'yes', 'on')
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


class ResPartner(models.Model):
    _inherit = 'res.partner'
    
    badge_ids = fields.Many2many('popcorn.badge', 'partner_badge_rel', 'partner_id', 'badge_id', 
                                 string='Available Badges', compute='_compute_badge_ids', store=False)
    earned_badge_ids = fields.Many2many('popcorn.badge', 'partner_earned_badge_rel', 'partner_id', 'badge_id',
                                       string='Earned Badges', compute='_compute_earned_badge_ids', store=False)
    
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
