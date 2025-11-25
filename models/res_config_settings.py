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
        domain=[('active', '=', True), ('send_wechat_notification', '=', True)],
        config_parameter='popcorn.waitlist_promotion_notification_id',
        help='Notification to send when a user is promoted from waitlist to confirmed registration. Configure WeChat template and field mappings in the notification record.'
    )






