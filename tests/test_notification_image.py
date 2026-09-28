# -*- coding: utf-8 -*-

import base64

from odoo.tests.common import TransactionCase


class TestNotificationImage(TransactionCase):

    def test_popup_image_is_exposed_to_frontend(self):
        notification = self.env['popcorn.notification'].create({
            'name': 'Image Popup',
            'notification_type': 'popup',
            'title': 'New announcement',
            'message': '<p>See what is new.</p>',
            'image': base64.b64encode(b'popup-image'),
            'image_filename': 'announcement.jpg',
            'show_action_button': True,
            'action_button_text': 'View now',
            'action_button_url': '/events',
        })

        data = notification.get_notification_data_for_partner(self.env.user.partner_id)

        self.assertEqual(
            data['image_url'],
            '/web/image/popcorn.notification/%s/image' % notification.id,
        )
        self.assertTrue(data['show_action_button'])
        self.assertEqual(data['action_button_text'], 'View now')
        self.assertEqual(data['action_button_url'], '/events')

    def test_text_only_popup_has_no_image_url(self):
        notification = self.env['popcorn.notification'].create({
            'name': 'Text Popup',
            'notification_type': 'popup',
            'title': 'Reminder',
            'message': '<p>Existing popup content.</p>',
        })

        data = notification.get_notification_data_for_partner(self.env.user.partner_id)

        self.assertFalse(data['image_url'])
