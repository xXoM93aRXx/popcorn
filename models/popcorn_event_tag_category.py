from odoo import models, fields, api

class EventTagCategory(models.Model):
    _inherit = 'event.tag.category'

    controls_card_color = fields.Boolean(
        string='Controls Card Color',
        help='If checked, this category will control the background color of event cards in the website view'
    )
