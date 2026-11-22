# -*- coding: utf-8 -*-

from odoo.tests.common import TransactionCase


class TestEventTagDisplayName(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['res.lang']._activate_lang('zh_CN')
        cls.category = cls.env['event.tag.category'].create({
            'name': 'Display Name Test Category',
        })

    def test_display_name_uses_odoo_translation_context_without_changing_name(self):
        tag = self.env['event.tag'].with_context(lang='en_US').create({
            'name': 'functional_tag_key',
            'card_display_name': 'Public Card Label',
            'category_id': self.category.id,
        })

        tag.with_context(lang='zh_CN').card_display_name = '公开卡片标签'

        self.assertEqual(tag.with_context(lang='en_US').card_display_name, 'Public Card Label')
        self.assertEqual(tag.with_context(lang='zh_CN').card_display_name, '公开卡片标签')
        self.assertEqual(tag.with_context(lang='en_US').name, 'functional_tag_key')
        self.assertEqual(tag.with_context(lang='zh_CN').name, 'functional_tag_key')

    def test_empty_display_name_can_fall_back_to_functional_name(self):
        tag = self.env['event.tag'].create({
            'name': 'Fallback Label',
            'category_id': self.category.id,
        })

        self.assertFalse(tag.card_display_name)
        self.assertEqual(tag.card_display_name or tag.name, 'Fallback Label')
