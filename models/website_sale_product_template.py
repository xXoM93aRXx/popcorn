# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ProductTemplate(models.Model):
    """Extend website sale product template to apply membership discounts."""

    _inherit = 'product.template'

    def _get_sales_prices(self, website):
        """Override to apply membership discount for customers with active memberships."""
        # Get partner from request context (works for both logged-in users and portal users)
        partner = False
        try:
            from odoo.http import request
            if hasattr(request, 'website') and hasattr(request, 'env'):
                # Check if user is logged in (not public user)
                user = request.env.user
                public_user = request.env.ref('base.public_user', raise_if_not_found=False)
                if user and user != public_user and hasattr(user, 'partner_id'):
                    partner = user.partner_id
        except:
            # Fallback to env user if request not available
            user = self.env.user
            public_user = self.env.ref('base.public_user', raise_if_not_found=False)
            if user and user != public_user and hasattr(user, 'partner_id'):
                partner = user.partner_id
        
        # Check for active membership before calling super
        has_active_membership = False
        if partner:
            active_memberships = self.env['popcorn.membership'].sudo().search([
                ('partner_id', '=', partner.id),
                ('state', 'in', ['active', 'frozen'])
            ], limit=1)
            has_active_membership = bool(active_memberships)
        
        # Call super to get base prices
        prices = super()._get_sales_prices(website)
        
        # Apply membership discount if customer has active membership
        if has_active_membership:
            pricelist = website.pricelist_id
            currency = website.currency_id
            fiscal_position = website.fiscal_position_id.sudo()
            date = fields.Date.context_today(self)
            
            for template in self:
                if not template.membership_discount or template.membership_discount <= 0:
                    continue
                
                if template.id not in prices:
                    continue
                
                price_vals = prices[template.id]
                original_price_with_tax = price_vals.get('price_reduce')

                # Get the pricelist price (before taxes)
                pricelist_prices = pricelist._compute_price_rule(template, 1.0)
                pricelist_price, _ = pricelist_prices.get(template.id, (0.0, False))
                
                if pricelist_price <= 0:
                    continue
                
                # Apply membership discount to pricelist price
                discount_amount = pricelist_price * (template.membership_discount / 100.0)
                discounted_price = max(0.0, pricelist_price - discount_amount)
                
                # Apply taxes to the discounted price
                product_taxes = template.sudo().taxes_id._filter_taxes_by_company(self.env.company)
                taxes = fiscal_position.map_tax(product_taxes)
                
                discounted_price_with_tax = self._apply_taxes_to_price(
                    discounted_price, currency, product_taxes, taxes, template, website=website,
                )
                
                # Update the price_reduce with discounted price
                price_vals['price_reduce'] = discounted_price_with_tax

                # Ensure base_price keeps the original price for comparison display
                if original_price_with_tax:
                    if 'base_price' not in price_vals or price_vals['base_price'] <= discounted_price_with_tax:
                        price_vals['base_price'] = original_price_with_tax

                # Expose membership discount for templates
                price_vals['popcorn_membership_discount_percent'] = template.membership_discount
        
        return prices

