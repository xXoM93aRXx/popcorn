{
    'name': 'Popcorn Club',
    'version': '18.0.1.0.2',
    'category': 'Customizations',
    'summary': 'A generic Odoo 18 module for Popcorn Club',
    'description': """
        This module provides a generic setup for Popcorn Club functionality.
        Features include:
        - Basic module structure
        - Sample models and views
        - Security configurations
        - Data files
        - Event host field customization
        - Contact host boolean field with automatic setting
        - First timer logic migrated to contact model
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'depends': ['base', 'event', 'website', 'website_event', 'website_sale', 'delivery', 'mail','web'],
    'data': [
        'security/ir.model.access.csv',
        'views/popcorn_menus.xml',
        'data/popcorn_membership_plans_data.xml',
        'views/popcorn_event_tag_category_views.xml',
        'views/popcorn_event_views.xml',
        'views/popcorn_membership_views.xml',
        'views/popcorn_membership_plan_views.xml',
        'views/popcorn_partner_views.xml',
        'views/popcorn_registration_button_override.xml',
        'views/popcorn_website_event_templates.xml',
        'views/popcorn_event_description_templates.xml',
        'views/popcorn_membership_website_templates.xml',
        'views/popcorn_event_registration_templates.xml',
        'views/popcorn_portal_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'popcorn/static/src/css/popcorn_event_styles.css',
            'popcorn/static/src/css/popcorn_membership_styles.css',
            'popcorn/static/src/css/popcorn_event_registration_styles.css',
            'popcorn/static/src/css/popcorn_membership_freeze.css',
            'popcorn/static/src/css/popcorn_event_freeze_styles.css',
            'popcorn/static/src/js/popcorn_membership_popup.js',
            'popcorn/static/src/js/popcorn_event_registration.js',
            'popcorn/static/src/js/popcorn_membership_freeze.js',
            'popcorn/static/src/js/popcorn_registration_cancellation.js',
        ],
    
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
