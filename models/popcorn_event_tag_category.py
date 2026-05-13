from odoo import models, fields, api

class EventTagCategory(models.Model):
    _inherit = 'event.tag.category'

    controls_card_color = fields.Boolean(
        string='Controls Card Color',
        help='If checked, this category will control the background color of event cards in the website view'
    )


class EventTag(models.Model):
    _inherit = 'event.tag'

    constellation_image = fields.Binary(
        string='Constellation Image',
        attachment=True,
        help='PNG with transparent background displayed as a constellation on the Variety Badge sky screen'
    )
    constellation_image_filename = fields.Char(string='Constellation Image Filename')
    constellation_name = fields.Char(
        string='Constellation Name',
        translate=True,
        help='Astronomical name shown in the info card (e.g. "Cygnus")'
    )
    constellation_description = fields.Text(
        string='Constellation Description',
        translate=True,
        help='Flavour text shown in the info card when a member clicks this constellation'
    )
