# -*- coding: utf-8 -*-

import base64
from datetime import timedelta
from io import BytesIO

from PIL import Image

from odoo import fields
from odoo.tests.common import TransactionCase


class TestEventHostImage(TransactionCase):

    @staticmethod
    def _make_image(color):
        output = BytesIO()
        Image.new('RGB', (800, 1200), color).save(output, format='PNG')
        return base64.b64encode(output.getvalue())

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.host = cls.env['res.partner'].create({
            'name': 'High Resolution Host',
            'image_1920': cls._make_image((220, 20, 60)),
        })
        start = fields.Datetime.now() + timedelta(days=7)
        cls.event = cls.env['event.event'].create({
            'name': 'Host Image Quality Test',
            'date_begin': start,
            'date_end': start + timedelta(hours=1),
            'host_id': cls.host.id,
        })

    def test_event_uses_high_resolution_host_variant(self):
        image = Image.open(BytesIO(base64.b64decode(self.event.host_image)))

        self.assertGreater(min(image.size), 128)
        self.assertEqual(max(image.size), 512)

    def test_event_image_refreshes_when_host_photo_changes(self):
        original = self.event.host_image

        self.host.image_1920 = self._make_image((20, 80, 220))

        self.assertNotEqual(self.event.host_image, original)
