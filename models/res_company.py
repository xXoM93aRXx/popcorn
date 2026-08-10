# -*- coding: utf-8 -*-

from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    # Kept here rather than in ir.config_parameter: config parameters hold a
    # single global string, and this one is shown to members on the website,
    # which runs in several languages.
    forum_thank_you_message = fields.Char(
        string='Forum Thank You Message',
        translate=True,
        default='Thanks for sharing with the club! Your post has been received.',
        help='Shown to the member after they submit a forum post. Deliberately identical whether the '
             'post is published or rejected, so the moderation outcome is not revealed.'
    )
