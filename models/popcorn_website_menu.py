# -*- coding: utf-8 -*-

from odoo import models, fields, api


class WebsiteMenu(models.Model):
    _inherit = 'website.menu'
    
    def _auto_init(self):
        """Override to handle field removal"""
        super()._auto_init()
        # Drop removed fields if they exist
        if self._table:
            try:
                # Check and drop show_in_sticky_footer field
                self.env.cr.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = %s AND column_name = 'show_in_sticky_footer'
                """, (self._table,))
                if self.env.cr.fetchone():
                    self.env.cr.execute(f'ALTER TABLE {self._table} DROP COLUMN show_in_sticky_footer')
                
                # Check and drop sticky_footer_sequence field
                self.env.cr.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = %s AND column_name = 'sticky_footer_sequence'
                """, (self._table,))
                if self.env.cr.fetchone():
                    self.env.cr.execute(f'ALTER TABLE {self._table} DROP COLUMN sticky_footer_sequence')
            except Exception:
                # Ignore errors during field removal
                pass

    # Field for storing FontAwesome icon class
    fa_icon = fields.Char(
        string='FontAwesome Icon',
        help='FontAwesome icon class (e.g., fa-home, fa-calendar-check, fa-user). '
             'Available icons: https://fontawesome.com/v4/icons/',
        default='fa-circle'
    )
    
    

    @api.model
    def get_sticky_footer_menus(self):
        """Get child menus that should be displayed in sticky footer"""
        try:
            website_id = self.env.context.get('website_id') or self.env['website'].get_current_website().id
        except:
            website_id = False
        
        # Get all child menus (sub-menus) for the website, filter is_visible in Python
        # (is_visible is a computed non-stored field and cannot be used in search domains)
        all_child_menus = self.search([
            ('website_id', 'in', [website_id, False]),
            ('parent_id', '!=', False),  # Only child menus (sub-menus)
        ], order='sequence').filtered(lambda m: m.is_visible)

        # Remove duplicates by URL - keep the first occurrence of each unique URL
        seen_urls = set()
        unique_menus = []
        for menu in all_child_menus:
            if menu.url not in seen_urls:
                seen_urls.add(menu.url)
                unique_menus.append(menu)

        return self.browse([menu.id for menu in unique_menus])
    
    @api.model
    def _safe_get_sticky_footer_menus(self):
        """Safely get sticky footer menus, returns empty recordset if method doesn't exist"""
        try:
            return self.get_sticky_footer_menus()
        except AttributeError:
            return self.browse([])
    
    @api.model
    def get_sticky_footer_menus_for_website(self, website_id=None):
        """Get child menus for sticky footer for a specific website"""
        if not website_id:
            website_id = self.env['website'].get_current_website().id
            
        # Get all child menus for the website, filter is_visible in Python
        # (is_visible is a computed non-stored field and cannot be used in search domains)
        all_child_menus = self.search([
            ('website_id', 'in', [website_id, False]),
            ('parent_id', '!=', False),  # Only child menus (sub-menus)
        ], order='sequence').filtered(lambda m: m.is_visible)

        # Remove duplicates by URL - keep the first occurrence of each unique URL
        seen_urls = set()
        unique_menus = []
        for menu in all_child_menus:
            if menu.url not in seen_urls:
                seen_urls.add(menu.url)
                unique_menus.append(menu)

        return self.browse([menu.id for menu in unique_menus])
