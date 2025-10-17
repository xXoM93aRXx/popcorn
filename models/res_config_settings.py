# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    popcorn_first_timer_discount_amount = fields.Float(
        string='First Timer Discount Amount (RMB)',
        default=118.00,
        config_parameter='popcorn.first_timer_discount_amount',
        help='The discount amount in RMB for first-timer customers'
    )
    
    company_currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        readonly=True
    )






