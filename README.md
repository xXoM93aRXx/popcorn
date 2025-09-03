# Popcorn Club Module

## Overview
This module provides comprehensive membership management functionality for Popcorn Club, including both backend administration and frontend website pages.

## Features

### Membership Plans Website Page
The membership plans page is now available as a proper website page that can be edited using the Odoo website editor.

#### How to Access
1. **Direct URL**: Navigate to `/memberships/website`
2. **Website Menu**: Access via "Membership Plans" in the website main menu
3. **Website Editor**: Edit the page content using the website editor

#### Key Features
- **Editable Content**: The page header and description can be customized using the website editor
- **Dynamic Data Loading**: Membership plans are loaded dynamically from the backend via AJAX
- **Responsive Design**: Fully responsive design that works on all devices
- **Real-time Updates**: Changes to membership plans in the backend are reflected on the website

#### Technical Implementation
- Uses `website.layout` template for proper website integration
- AJAX endpoint `/memberships/data` provides membership plan data
- CSS styles are automatically loaded via frontend assets
- JavaScript handles dynamic content loading and error states

#### Backend Integration
- Membership plans are managed in the backend under "Popcorn > Membership Plans"
- Active plans are automatically displayed on the website
- Plan details include pricing, benefits, and access permissions

## Installation
1. Install the module
2. Create membership plans in the backend
3. Access the website page at `/memberships/website`
4. Customize the page content using the website editor

## Dependencies
- `website` - For website functionality
- `website_event` - For event integration
- `website_sale` - For sales functionality
- `delivery` - For delivery management

## Files Modified
- `views/popcorn_membership_website_templates.xml` - Added website page template
- `controllers/popcorn_membership_controller.py` - Added JSON endpoint and website route
- `views/popcorn_menus.xml` - Added website menu item
- `__manifest__.py` - Added website dependency
