# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class ActivitySport(models.Model):
    _name = 'popcorn.activity_sport'
    _description = 'Activities & Sports'
    _order = 'category_id, name'

    name = fields.Char('Activity/Sport Name', required=True, translate=True)
    category_id = fields.Many2one('popcorn.activity_sport.category', string='Category', required=True, ondelete='restrict')
    description = fields.Text('Description', translate=True)
    active = fields.Boolean('Active', default=True)
    
    def name_get(self):
        """Override name_get to show category with name"""
        result = []
        for record in self:
            if record.category_id:
                result.append((record.id, f"[{record.category_id.name}] {record.name}"))
            else:
                result.append((record.id, record.name))
        return result
    
    def toggle_active(self):
        """Toggle the active field"""
        for record in self:
            record.active = not record.active
        return True

