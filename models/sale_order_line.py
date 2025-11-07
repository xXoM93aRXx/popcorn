# -*- coding: utf-8 -*-

from odoo import api, fields, models


class SaleOrderLine(models.Model):
    """Extend sale order lines to apply membership discounts automatically."""

    _inherit = 'sale.order.line'

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _popcorn_get_membership_discount_percent(self):
        """Return the membership discount percentage for the current line."""
        self.ensure_one()

        template = self.product_id.product_tmpl_id
        if not template or not template.membership_discount:
            return 0.0

        partner = self.order_partner_id or self.order_id.partner_id
        if not partner:
            return 0.0

        membership = self.env['popcorn.membership'].sudo().search([
            ('partner_id', '=', partner.id),
            ('state', 'in', ['active', 'frozen'])
        ], limit=1)

        return template.membership_discount if membership else 0.0

    # -------------------------------------------------------------------------
    # Pricing overrides
    # -------------------------------------------------------------------------

    def _get_display_price_ignore_combo(self):
        """Apply membership discount after pricelist pricing and before taxes."""
        self.ensure_one()

        price = super()._get_display_price_ignore_combo()

        discount_percent = self._popcorn_get_membership_discount_percent()
        if discount_percent > 0:
            price = max(0.0, price * (1 - discount_percent / 100.0))

        return price

    # -------------------------------------------------------------------------
    # Public helpers for templates
    # -------------------------------------------------------------------------

    def get_popcorn_membership_cart_pricing(self):
        """Return pricing details for membership discounts in the cart UI."""
        self.ensure_one()

        discount_percent = self._popcorn_get_membership_discount_percent()
        if discount_percent <= 0 or discount_percent >= 100:
            return {}

        final_price = self._get_cart_display_price()
        if final_price <= 0:
            return {}

        base_price = final_price / (1 - discount_percent / 100.0)

        return {
            'percent': discount_percent,
            'base_price': base_price,
            'final_price': final_price,
        }

