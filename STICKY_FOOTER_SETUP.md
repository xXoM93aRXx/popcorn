# Popcorn Sticky Footer Navigation Setup

This document explains how to set up and use the sticky footer navigation system in the Popcorn Club Odoo addon.

## Overview

The sticky footer navigation system allows you to create a mobile-friendly bottom navigation bar that automatically highlights the active page. It integrates with Odoo's website menu system and uses FontAwesome icons.

## Features

- **Dynamic Menu Management**: Configure navigation items through Odoo's website menu system
- **FontAwesome Icons**: Uses Odoo 18's built-in FontAwesome 4 library
- **Active Tab Highlighting**: Automatically highlights the current page
- **Responsive Design**: Adapts to different screen sizes
- **Brand Colors**: Uses Popcorn's brand red (#e60000) for active states
- **Accessibility**: Includes proper ARIA labels and keyboard navigation
- **Multi-language Support**: Fully translatable menu items and interface

## Setup Instructions

### 1. Install the Module

After adding the new files, upgrade your Popcorn module:

```bash
# In Odoo shell or through the UI
odoo-bin -u popcorn -d your_database
```

### 2. Configure Menu Items

The sticky footer navigation automatically shows ALL visible child menu items (sub-menus) by default. You can customize which ones appear.

1. Go to **Website > Configuration > Website Menus**
2. Create parent menus and their child menus (sub-menus)
3. For each child menu item:
   - **FontAwesome Icon**: Set icon (e.g., `fa-home`, `fa-calendar-check`, `fa-user`)
   - **Footer Order**: Set order (lower numbers appear first)
   - **Hide from Sticky Footer**: Check this to exclude from sticky footer
4. **Important**: All visible child menus appear by default - use "Hide from Sticky Footer" to exclude

### 3. Available FontAwesome Icons

Here are some commonly used icons for navigation:

- `fa-home` - Home/Dashboard
- `fa-calendar-check` - Events/Appointments
- `fa-user` - Profile/Account
- `fa-shopping-cart` - Shopping/Cart
- `fa-bell` - Notifications
- `fa-search` - Search
- `fa-heart` - Favorites/Likes
- `fa-star` - Featured/Important
- `fa-cog` - Settings
- `fa-info-circle` - Information/Help

For a complete list, visit: https://fontawesome.com/v4/icons/

## File Structure

The sticky footer system consists of several files:

```
popcorn/
├── models/
│   └── popcorn_website_menu.py          # Extends website.menu model
├── views/
│   ├── popcorn_website_menu_views.xml    # Custom form view for menus
│   └── popcorn_sticky_footer_templates.xml # Footer templates
├── static/src/
│   ├── css/
│   │   └── popcorn_sticky_footer.css     # Footer styles
│   └── js/
│       └── popcorn_sticky_footer.js      # Active tab logic
├── data/
│   └── popcorn_sticky_footer_data.xml    # Empty - menus configured dynamically
└── security/
    └── ir.model.access.csv               # Access permissions
```

## Customization

### Changing Colors

Edit `static/src/css/popcorn_sticky_footer.css`:

```css
:root { 
    --brand-red: #your-color;     /* Active/hover color */
    --brand-black: #your-color;   /* Default text color */
}
```

### Multi-language Support

The sticky footer navigation supports multiple languages:

1. **Default Language**: Menu items are created in English by default
2. **Translation Files**: Located in `i18n/` directory
   - `popcorn.pot`: Translation template
   - `zh_CN.po`: Chinese (Simplified) translations
3. **Adding New Languages**: 
   - Copy `popcorn.pot` to `i18n/[language_code].po`
   - Translate the strings
   - Add language to `__manifest__.py`
4. **Menu Item Translation**: 
   - Menu names are automatically translated based on user's language
   - Use Odoo's translation system: **Settings > Translations > Import/Export**

### Adding More Menu Items

1. Go to **Website > Configuration > Website Menus**
2. Create parent menus and their child menus (sub-menus)
3. Set appropriate FontAwesome icon and footer order for child menus
4. **Note**: New child menus automatically appear in sticky footer unless you check "Hide from Sticky Footer"
5. **Automatic filtering**: The system shows only:
   - Child menus (sub-menus with a parent)
   - Visible menus
   - Menus for the current website
   - Menus not explicitly hidden from sticky footer

### Modifying Layout

The footer automatically adjusts to the number of menu items. For custom layouts, modify the CSS:

```css
.sticky-footer {
    justify-content: space-evenly; /* Change to space-between, flex-start, etc. */
}
```

## Technical Details

### Model Extensions

The `website.menu` model is extended with:

- `fa_icon`: FontAwesome icon class
- `sticky_footer_sequence`: Integer for ordering in footer
- `sticky_footer_sequence`: Order in footer

### JavaScript Features

- Automatic active tab detection
- URL normalization for proper matching
- Responsive behavior
- Smooth transitions

### CSS Features

- Fixed positioning with safe area support
- Backdrop blur effect
- Responsive breakpoints
- Dark mode support
- Accessibility improvements

## Troubleshooting

### Footer Not Appearing

1. Check that menu items have **"Show in Sticky Footer"** enabled
2. Verify the template is properly inherited in `website.layout`
3. Check browser console for JavaScript errors

### Icons Not Showing

1. Ensure FontAwesome is loaded (included in Odoo 18)
2. Check icon class names (should start with `fa-`)
3. Verify icon exists in FontAwesome 4

### Active Tab Not Highlighting

1. Check JavaScript console for errors
2. Verify URL paths match between menu items and current page
3. Ensure `data-paths` attribute is set correctly

### Styling Issues

1. Check CSS file is loaded in assets
2. Verify CSS specificity isn't overridden
3. Test responsive breakpoints

## Browser Support

- Modern browsers (Chrome, Firefox, Safari, Edge)
- Mobile browsers (iOS Safari, Chrome Mobile)
- Supports safe area insets for notched devices

## Performance

- Minimal JavaScript overhead
- CSS uses efficient selectors
- Icons are font-based (lightweight)
- Responsive images not required

## Security

- No external dependencies
- Uses Odoo's built-in security model
- Proper access controls for menu editing
- XSS protection through Odoo's template system
