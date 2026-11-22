from odoo import models, fields, api

class EventTagCategory(models.Model):
    _inherit = 'event.tag.category'

    controls_card_color = fields.Boolean(
        string='Controls Card Color',
        help='If checked, this category will control the background color of event cards in the website view'
    )
    show_on_event_card = fields.Boolean(
        string='Show on Event Card',
        default=True,
        help=(
            'If checked, tags from this category are displayed on website event cards. '
            'This only controls their visibility; tags continue to work normally in all business rules.'
        ),
    )


class EventTag(models.Model):
    _inherit = 'event.tag'

    card_display_name = fields.Char(
        string='Display Name',
        translate=True,
        help=(
            'Optional public label shown on website event cards. '
            'Leave empty to display the functional tag name.'
        ),
    )

    @api.model
    def _ensure_focus_club_type_tag(self):
        """Ensure each Type category offers all Focus Club event types."""
        categories = self.env['event.tag.category'].sudo().search([
            ('name', '=', 'Type'),
        ])
        if not categories:
            categories = self.env['event.tag.category'].sudo().create({
                'name': 'Type',
            })

        focus_tags = (
            ('Focus Club', 1),
            ('Focus Club 90', 2),
            ('Focus Club 120', 3),
        )
        for category in categories:
            for tag_name, color in focus_tags:
                existing = self.sudo().search([
                    ('name', '=', tag_name),
                    ('category_id', '=', category.id),
                ], limit=1)
                if not existing:
                    self.sudo().create({
                        'name': tag_name,
                        'category_id': category.id,
                        'color': color,
                    })
        return True

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
