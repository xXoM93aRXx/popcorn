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
    
    waitlist_promotion_notification_id = fields.Many2one(
        'popcorn.notification',
        string='Waitlist Promotion Notification',
        domain=[('active', '=', True)],
        config_parameter='popcorn.waitlist_promotion_notification_id',
        help='Notification to send when a user is promoted from waitlist to confirmed registration. Configure WeChat template and field mappings in the notification record. Note: Enable "Send WeChat Notification" on the notification record if WeChat integration is installed.'
    )

    badges_evaluation_enabled = fields.Boolean(
        string='Enable Badge Evaluation',
        config_parameter='popcorn.badges_evaluation_enabled',
        default=False,
        help='When enabled, the system will evaluate and award badges to members on every portal page visit. '
             'Disable this before a module update so you can configure badge prizes before evaluation begins.'
    )






