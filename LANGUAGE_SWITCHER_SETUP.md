# Language Switcher Setup Guide

This guide explains how to set up the language switcher that integrates with Odoo's native language system.

## Prerequisites

1. **Install Languages in Odoo:**
   - Go to `Website` → `Configuration` → `Settings`
   - In the "Website info" section, click "Install languages"
   - Select English and Chinese (or your preferred languages)
   - Click "Add" to install the languages

2. **Enable Languages for Website:**
   - Make sure the languages are assigned to your website
   - Verify that both languages are active

## Features

- **Fixed Position:** The language switcher appears as a fixed button in the top-right corner
- **Native Integration:** Uses Odoo's built-in language switching system
- **Beautiful Design:** Custom styled with gradient background and smooth animations
- **Responsive:** Adapts to different screen sizes
- **Accessibility:** Supports reduced motion preferences and high contrast mode

## How It Works

The language switcher integrates with Odoo's native language system by:

1. **Extending website.layout:** Adds the language selector to all pages
2. **Using Odoo's Language API:** Leverages `website.get_available_languages()` to get available languages
3. **Native Language Switching:** Uses `/web/session/set_lang?lang={code}` for language changes
4. **Custom Styling:** Applies beautiful CSS styling while maintaining functionality

## File Structure

- `views/popcorn_language_switcher_templates.xml` - Template definitions
- `static/src/css/popcorn_language_switcher.css` - Styling
- `static/src/js/popcorn_language_switcher.js` - JavaScript enhancements

## Customization

### Changing Position
To change the position of the language switcher, modify the CSS:

```css
.popcorn-language-switcher {
    position: fixed;
    top: 20px;        /* Change top position */
    right: 20px;      /* Change right position */
    z-index: 9999;
}
```

### Changing Colors
To change the button colors, modify the gradient in the CSS:

```css
.popcorn-lang-btn {
    background: linear-gradient(135deg, #your-color-1 0%, #your-color-2 100%);
}
```

### Adding More Languages
Simply install additional languages in Odoo's website settings, and they will automatically appear in the language switcher.

## Troubleshooting

1. **Language switcher not appearing:**
   - Ensure languages are installed in Website → Configuration → Settings
   - Check that the module is properly installed and updated

2. **Languages not switching:**
   - Verify that languages are assigned to the website
   - Check browser console for JavaScript errors

3. **Styling issues:**
   - Clear browser cache
   - Ensure CSS files are properly loaded
   - Check for CSS conflicts with other modules

## Browser Support

- Chrome/Edge: Full support
- Firefox: Full support  
- Safari: Full support
- Mobile browsers: Responsive design included
