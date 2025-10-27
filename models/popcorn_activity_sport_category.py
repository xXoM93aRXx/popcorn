# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class ActivitySportCategory(models.Model):
    _name = 'popcorn.activity_sport.category'
    _description = 'Activity/Sport Category'
    _order = 'sequence, name'

    name = fields.Char('Category Name', required=True, translate=True)
    sequence = fields.Integer('Sequence', default=10)
    description = fields.Text('Description', translate=True)
    active = fields.Boolean('Active', default=True)
    
    activity_sport_ids = fields.One2many('popcorn.activity_sport', 'category_id', string='Activities & Sports')
    activity_sport_count = fields.Integer('Count', compute='_compute_activity_sport_count')
    
    @api.depends('activity_sport_ids')
    def _compute_activity_sport_count(self):
        for record in self:
            record.activity_sport_count = len(record.activity_sport_ids)
    
    def toggle_active(self):
        """Toggle the active field"""
        for record in self:
            record.active = not record.active
        return True

