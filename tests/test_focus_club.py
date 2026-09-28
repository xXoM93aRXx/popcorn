# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import fields
from odoo.tests.common import TransactionCase


class TestFocusClub(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['event.tag']._ensure_focus_club_type_tag()
        cls.focus_tag = cls.env['event.tag'].search([
            ('name', '=', 'Focus Club'),
            ('category_id.name', '=', 'Type'),
        ], limit=1)
        cls.partner = cls.env['res.partner'].create({
            'name': 'Focus Club Test Member',
            'email': 'focus-club-test@example.com',
            'is_first_timer': True,
        })
        cls.today = fields.Date.today()

    def _create_event(self, name):
        start = fields.Datetime.now() + timedelta(days=7)
        return self.env['event.event'].create({
            'name': name,
            'date_begin': start,
            'date_end': start + timedelta(hours=2),
            'tag_ids': [(6, 0, self.focus_tag.ids)],
        })

    def _create_membership(self, plan):
        return self.env['popcorn.membership'].create({
            'partner_id': self.partner.id,
            'membership_plan_id': plan.id,
            'purchase_price_paid': 100.0,
            'purchase_channel': 'online',
            'price_tier': 'normal',
            'state': 'active',
            'activation_date': self.today,
        })

    def test_focus_tag_classifies_event_and_registration(self):
        event = self._create_event('Focus Club Classification')
        plan = self.env['popcorn.membership.plan'].create({
            'name': 'Focus Bucket Plan',
            'quota_mode': 'bucket_counts',
            'duration_days': 90,
            'activation_policy': 'immediate',
            'allowed_regular_offline': False,
            'allowed_regular_online': False,
            'allowed_spclub': False,
            'allowed_focus_club': True,
            'quota_focus': 2,
            'price_normal': 100.0,
        })
        membership = self._create_membership(plan)

        registration = self.env['event.registration'].create({
            'event_id': event.id,
            'partner_id': self.partner.id,
            'membership_id': membership.id,
            'name': self.partner.name,
            'email': self.partner.email,
            'state': 'open',
        })

        self.assertEqual(event.club_type, 'focus_club')
        self.assertEqual(registration.club_type, 'focus_club')
        self.assertEqual(registration.consumption_state, 'consumed')
        self.assertEqual(membership.remaining_focus, 1)

    def test_focus_club_uses_configured_points(self):
        event = self._create_event('Focus Club Points')
        plan = self.env['popcorn.membership.plan'].create({
            'name': 'Focus Points Plan',
            'quota_mode': 'points',
            'duration_days': 90,
            'activation_policy': 'immediate',
            'allowed_focus_club': True,
            'points_start': 20,
            'points_per_focus': 5,
            'price_normal': 100.0,
        })
        membership = self._create_membership(plan)

        registration = self.env['event.registration'].create({
            'event_id': event.id,
            'partner_id': self.partner.id,
            'membership_id': membership.id,
            'name': self.partner.name,
            'email': self.partner.email,
            'state': 'open',
        })

        self.assertEqual(registration.points_consumed, 5)
        self.assertEqual(membership.points_remaining, 15)

    def test_first_timer_coupon_applies_to_focus_club(self):
        discount = self.partner._get_first_timer_discount_record()

        self.assertTrue(discount)
        self.assertEqual(discount.event_type, 'regular_offline')
        self.assertTrue(discount._applies_to_event_type('regular_offline'))
        self.assertTrue(discount._applies_to_event_type('focus_club'))
        self.assertFalse(discount._applies_to_event_type('spclub'))
        self.assertTrue(self.partner.has_valid_first_timer_coupon('focus_club'))
