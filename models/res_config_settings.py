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

    forum_moderation_enabled = fields.Boolean(
        string='Enable Forum Moderation',
        config_parameter='popcorn.forum_moderation_enabled',
        default=False,
        help='When enabled, every forum post is checked against the content regulations by DeepSeek before '
             'it becomes visible. When disabled, posts are published immediately without any review.'
    )

    forum_deepseek_api_key = fields.Char(
        string='DeepSeek API Key',
        config_parameter='popcorn.forum_deepseek_api_key',
        help='API key from platform.deepseek.com used to moderate forum posts.'
    )

    forum_deepseek_model = fields.Char(
        string='DeepSeek Model',
        config_parameter='popcorn.forum_deepseek_model',
        default='deepseek-v4-flash',
        help='DeepSeek model used for moderation. Leave as deepseek-v4-flash unless you need the stronger '
             'deepseek-v4-pro, which is slower and costs more per post.'
    )

    # res.config.settings only accepts boolean/integer/float/char/selection/
    # many2one/datetime for config_parameter fields, so this one is read and
    # written by hand below to keep a multi-line editor for the rules.
    forum_content_regulations = fields.Text(
        string='Content Regulations',
        help='The rules a post must follow, in plain text. These are sent to DeepSeek verbatim as the only '
             'basis for its decision, so write them as a numbered list of clear, checkable statements. '
             'Editing them affects future posts only; use "Re-run Moderation" to re-check existing ones.'
    )

    # Related to a translatable field on res.company so the message can be
    # maintained per language, which a config_parameter cannot do.
    forum_thank_you_message = fields.Char(
        related='company_id.forum_thank_you_message',
        readonly=False,
        help='Shown to the member after they submit a post. Deliberately identical whether the post is '
             'published or rejected, so the moderation outcome is not revealed.'
    )

    @api.model
    def get_values(self):
        res = super().get_values()
        res['forum_content_regulations'] = self.env['ir.config_parameter'].sudo().get_param(
            'popcorn.forum_content_regulations', ''
        )
        return res

    def set_values(self):
        super().set_values()
        self.env['ir.config_parameter'].sudo().set_param(
            'popcorn.forum_content_regulations', self.forum_content_regulations or ''
        )






