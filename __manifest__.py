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
        - Dynamic Badge System:
          * Create badges with custom images and descriptions
          * Define flexible badge rules based on any model and field
          * Automatic badge evaluation for users
          * Portal integration showing earned/unearned badges
          * Visual distinction between earned and unearned badges
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'depends': ['base', 'event', 'website', 'website_event', 'website_sale', 'payment', 'delivery', 'mail','web'],
    'data': [
        'security/ir.model.access.csv',
        'views/popcorn_menus.xml',
        'data/popcorn_membership_plans_data.xml',
        'data/popcorn_sticky_footer_data.xml',
        'data/popcorn_badge_data.xml',
        'data/popcorn_event_auto_end_data.xml',
        'views/popcorn_event_tag_category_views.xml',
        'views/popcorn_event_views.xml',
        'views/popcorn_event_registration_views.xml',
        'views/popcorn_membership_views.xml',
        'views/popcorn_membership_plan_views.xml',
        'views/popcorn_discount_views.xml',
        'views/popcorn_partner_views.xml',
        'views/popcorn_badge_views.xml',
        'views/popcorn_referral_views.xml',
        'views/popcorn_registration_button_override.xml',
        'views/popcorn_website_event_templates.xml',
        'views/popcorn_event_search_templates.xml',
        'views/popcorn_event_description_templates.xml',
        'views/popcorn_membership_website_templates.xml',
        'views/popcorn_event_registration_templates.xml',
        'views/popcorn_portal_templates.xml',
        'views/popcorn_badge_portal_templates.xml',
        'views/popcorn_badge_detail_templates.xml',
        'views/popcorn_language_switcher_templates.xml',
        'views/popcorn_website_menu_views.xml',
        'views/popcorn_sticky_footer_templates.xml',
        'views/popcorn_host_profile_templates.xml',
        'views/popcorn_contract_website_templates.xml',
        'views/popcorn_contact_templates.xml',
        'views/popcorn_contract_template.xml',
        'report/popcorn_contract_report_template.xml',
        'report/popcorn_contract_report_action.xml',
        'views/popcorn_contract_views.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'popcorn/static/src/css/popcorn_event_styles.css',
            'popcorn/static/src/css/popcorn_membership_styles.css',
            'popcorn/static/src/css/popcorn_event_registration_styles.css',
            'popcorn/static/src/css/popcorn_membership_freeze.css',
            'popcorn/static/src/css/popcorn_event_freeze_styles.css',
            'popcorn/static/src/css/popcorn_language_switcher.css',
            'popcorn/static/src/css/popcorn_sticky_footer.css',
            'popcorn/static/src/css/popcorn_badge_styles.css',
            'popcorn/static/src/css/popcorn_host_profile_styles.css',
            'popcorn/static/src/css/popcorn_contact_styles.css',
            'popcorn/static/src/css/popcorn_portal_styles.css',
            'popcorn/static/src/js/popcorn_membership_popup.js',
            'popcorn/static/src/js/popcorn_event_registration.js',
            'popcorn/static/src/js/popcorn_membership_freeze.js',
            'popcorn/static/src/js/popcorn_registration_cancellation.js',
            'popcorn/static/src/js/popcorn_language_switcher.js',
            'popcorn/static/src/js/popcorn_sticky_footer.js',
            'popcorn/static/src/js/popcorn_host_dropdown.js',
            'popcorn/static/src/js/popcorn_day_filter.js',
            'popcorn/static/src/js/popcorn_referral.js',
            'popcorn/static/src/js/popcorn_membership_anchor_scroll.js',
        ],
        'web.report_assets_common': [
            'popcorn/static/src/css/popcorn_contract_report.css',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
