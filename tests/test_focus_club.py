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

    def test_first_timer_coupon_follows_event_setting(self):
        discount = self.partner._get_first_timer_discount_record()
        event = self._create_event('Focus Club Coupon Opt In')

        self.assertTrue(discount)
        self.assertTrue(event.allow_first_timer_coupon)

        event.allow_first_timer_coupon = False

        self.assertFalse(event.allow_first_timer_coupon)
        self.assertFalse(discount._applies_to_event(event))
        self.assertFalse(self.partner.has_valid_first_timer_coupon(event))

        event.allow_first_timer_coupon = True

        self.assertTrue(discount._applies_to_event(event))
        self.assertTrue(self.partner.has_valid_first_timer_coupon(event))

    def test_event_opt_in_supports_existing_type_restricted_coupons(self):
        discount = self.partner._get_first_timer_discount_record()
        event = self._create_event('Focus Club Legacy Coupon')
        event.allow_first_timer_coupon = True

        # Simulate an existing generated coupon from before event-level opt-in.
        discount.event_type = 'regular_offline'

        self.assertEqual(event.club_type, 'focus_club')
        self.assertTrue(discount._applies_to_event(event))

    def test_ordinary_discount_keeps_club_type_restriction(self):
        event = self._create_event('Focus Club Ordinary Coupon')
        event.allow_first_timer_coupon = True
        discount = self.env['popcorn.discount'].create({
            'name': 'Regular Offline Promotion',
            'code': 'OFFLINEONLY',
            'discount_type': 'fixed_amount',
            'discount_value': 10,
            'customer_type': 'all',
            'event_type': 'regular_offline',
        })

        self.assertFalse(discount._is_first_timer_coupon())
        self.assertFalse(discount._applies_to_event(event))
