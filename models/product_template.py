from odoo import api, fields, models


class ProductTemplate(models.Model):
    """Extend product templates with host linkage and membership discounts."""

    _inherit = 'product.template'

    popcorn_host_id = fields.Many2one(
        'res.partner',
        string='Host',
        domain="[('is_host', '=', True)]",
        help='Select the host whose profile and events should be highlighted on the product page.'
    )

    popcorn_host_latest_event_ids = fields.Many2many(
        'event.event',
        string='Latest Host Events',
        compute='_compute_popcorn_host_latest_event_ids',
        store=False,
        help='Last three published events associated with the selected host.',
        compute_sudo=True,
    )

    popcorn_host_name = fields.Char(
        string='Host Name',
        compute='_compute_popcorn_host_info',
        store=False,
        help='Cached host name for website display.',
    )

    popcorn_host_function = fields.Char(
        string='Host Function',
        compute='_compute_popcorn_host_info',
        store=False,
        help='Cached host job title for website display.',
    )

    popcorn_host_bio = fields.Text(
        string='Host Bio',
        compute='_compute_popcorn_host_info',
        store=False,
        help='Cached host biography for website display.',
    )

    popcorn_host_image = fields.Binary(
        string='Host Image',
        compute='_compute_popcorn_host_info',
        store=True,
        help='Cached host image for website display.',
    )

    membership_discount = fields.Float(
        string='Membership Discount (%)',
        digits='Discount',
        default=0.0,
        help='Discount percentage to apply automatically for customers with active memberships. Applied after pricelist pricing.'
    )

    @api.depends('popcorn_host_id')
    def _compute_popcorn_host_latest_event_ids(self):
        """Fetch the three most recent published events for the selected host."""
        Event = self.env['event.event'].sudo()
        for template in self:
            if template.popcorn_host_id:
                template.popcorn_host_latest_event_ids = Event.search([
                    ('host_id', '=', template.popcorn_host_id.id),
                    ('website_published', '=', True),
                ], order='date_begin desc', limit=3)
            else:
                template.popcorn_host_latest_event_ids = Event.browse()

    @api.depends('popcorn_host_id')
    def _compute_popcorn_host_info(self):
        """Populate host information fields without exposing res.partner records."""
        for template in self:
            host = template.popcorn_host_id.sudo()
            if host:
                template.popcorn_host_name = host.name or ''
                template.popcorn_host_function = host.function or ''
                template.popcorn_host_bio = host.host_bio or ''
                template.popcorn_host_image = host.image_128 or False
            else:
                template.popcorn_host_name = ''
                template.popcorn_host_function = ''
                template.popcorn_host_bio = ''
                template.popcorn_host_image = False

    def write(self, vals):
        """Ensure linked partners keep their host status when assigned to a product."""
        result = super().write(vals)
        if 'popcorn_host_id' in vals and vals['popcorn_host_id']:
            host_partner = self.env['res.partner'].browse(vals['popcorn_host_id'])
            host_partner.sudo().is_host = True
        return result

    @api.model
    def create(self, vals):
        """Preserve host flag when a host is set during product creation."""
        template = super().create(vals)
        if template.popcorn_host_id:
            template.popcorn_host_id.sudo().is_host = True
        return template

