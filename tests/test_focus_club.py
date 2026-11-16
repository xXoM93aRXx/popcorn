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
        cls.focus_90_tag = cls.env['event.tag'].search([
            ('name', '=', 'Focus Club 90'),
            ('category_id', '=', cls.focus_tag.category_id.id),
        ], limit=1)
        cls.focus_120_tag = cls.env['event.tag'].search([
            ('name', '=', 'Focus Club 120'),
            ('category_id', '=', cls.focus_tag.category_id.id),
        ], limit=1)
        cls.online_tag = cls.env['event.tag'].create({
            'name': 'Regular Online Test',
            'category_id': cls.focus_tag.category_id.id,
        })
        cls.offline_tag = cls.env['event.tag'].create({
            'name': 'Regular Offline Test',
            'category_id': cls.focus_tag.category_id.id,
        })
        cls.social_tag = cls.env['event.tag'].create({
            'name': 'Social Experience Test',
            'category_id': cls.focus_tag.category_id.id,
        })
        cls.special_tag = cls.env['event.tag'].create({
            'name': 'Special Club Test',
            'category_id': cls.focus_tag.category_id.id,
        })
        cls.partner = cls.env['res.partner'].create({
            'name': 'Focus Club Test Member',
            'email': 'focus-club-test@example.com',
            'is_first_timer': True,
        })
        cls.today = fields.Date.today()

    def _create_event(self, name):
        return self._create_focus_event(name, self.focus_tag)

    def _create_focus_event(self, name, tag, day_offset=7):
        start = fields.Datetime.now() + timedelta(days=day_offset)
        return self.env['event.event'].create({
            'name': name,
            'date_begin': start,
            'date_end': start + timedelta(hours=2),
            'tag_ids': [(6, 0, tag.ids)],
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

    def test_freedom_plan_has_focus_duration_point_costs(self):
        freedom_plan = self.env.ref('popcorn.membership_plan_freedom')

        self.assertTrue(freedom_plan.allowed_focus_club)
        self.assertEqual(freedom_plan.points_per_focus, 2)
        self.assertEqual(freedom_plan.points_per_focus_90, 3)
        self.assertEqual(freedom_plan.points_per_focus_120, 4)

    def test_focus_duration_types_use_2_3_4_points_and_snapshot_history(self):
        self.assertTrue(self.focus_90_tag)
        self.assertTrue(self.focus_120_tag)
        self.assertTrue(self.focus_90_tag.color)
        self.assertTrue(self.focus_120_tag.color)

        plan = self.env['popcorn.membership.plan'].create({
            'name': 'Focus Duration Points Plan',
            'quota_mode': 'points',
            'duration_days': 90,
            'activation_policy': 'immediate',
            'allowed_focus_club': True,
            'points_start': 20,
            'points_per_focus': 2,
            'points_per_focus_90': 3,
            'points_per_focus_120': 4,
            'price_normal': 100.0,
        })
        membership = self._create_membership(plan)
        cases = (
            (self.focus_tag, 'focus_club', 2),
            (self.focus_90_tag, 'focus_club_90', 3),
            (self.focus_120_tag, 'focus_club_120', 4),
        )
        registrations = []
        for index, (tag, club_type, points) in enumerate(cases, start=1):
            event = self._create_focus_event(
                f'{club_type} Points',
                tag,
                day_offset=7 + index,
            )
            registration = self.env['event.registration'].create({
                'event_id': event.id,
                'partner_id': self.partner.id,
                'membership_id': membership.id,
                'name': self.partner.name,
                'email': self.partner.email,
                'state': 'open',
            })
            self.assertEqual(event.club_type, club_type)
            self.assertEqual(registration.club_type, club_type)
            self.assertEqual(registration.points_consumed, points)
            registrations.append(registration)

        self.assertEqual(membership.points_remaining, 11)

        focus_90_registration = registrations[1]
        focus_90_registration.event_id.tag_ids = [(6, 0, self.focus_120_tag.ids)]
        plan.points_per_focus_90 = 9

        self.assertEqual(focus_90_registration.event_id.club_type, 'focus_club_120')
        self.assertEqual(focus_90_registration.club_type, 'focus_club_90')
        self.assertEqual(focus_90_registration.points_consumed, 3)
        self.assertEqual(membership.points_remaining, 11)

    def test_focus_duration_types_share_focus_session_bucket(self):
        plan = self.env['popcorn.membership.plan'].create({
            'name': 'Focus Duration Bucket Plan',
            'quota_mode': 'bucket_counts',
            'duration_days': 90,
            'activation_policy': 'immediate',
            'allowed_focus_club': True,
            'quota_focus': 2,
            'price_normal': 100.0,
        })
        membership = self._create_membership(plan)

        for index, tag in enumerate((self.focus_90_tag, self.focus_120_tag), start=1):
            event = self._create_focus_event(
                f'Focus Bucket {index}',
                tag,
                day_offset=10 + index,
            )
            self.env['event.registration'].create({
                'event_id': event.id,
                'partner_id': self.partner.id,
                'membership_id': membership.id,
                'name': self.partner.name,
                'email': self.partner.email,
                'state': 'open',
            })

        self.assertEqual(membership.remaining_focus, 0)

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

    def test_first_timer_coupon_defaults_follow_club_type(self):
        start = fields.Datetime.now() + timedelta(days=7)
        cases = (
            ('Regular Offline', self.offline_tag, 'regular_offline', True),
            ('Focus Club', self.focus_tag, 'focus_club', True),
            ('Focus Club 90', self.focus_90_tag, 'focus_club_90', True),
            ('Focus Club 120', self.focus_120_tag, 'focus_club_120', True),
            ('Regular Online', self.online_tag, 'regular_online', False),
            ('Social Experience', self.social_tag, 'social_experience', False),
            ('Special Club', self.special_tag, 'spclub', False),
        )
        for name, tag, club_type, expected in cases:
            with self.subTest(club_type=club_type):
                event = self.env['event.event'].create({
                    'name': f'{name} Coupon Default',
                    'date_begin': start,
                    'date_end': start + timedelta(hours=2),
                    'tag_ids': [(6, 0, tag.ids)],
                })

                self.assertEqual(event.club_type, club_type)
                self.assertEqual(event.allow_first_timer_coupon, expected)

        explicitly_enabled_event = self.env['event.event'].create({
            'name': 'Regular Online Coupon Enabled',
            'date_begin': start,
            'date_end': start + timedelta(hours=2),
            'tag_ids': [(6, 0, self.online_tag.ids)],
            'allow_first_timer_coupon': True,
        })

        self.assertTrue(explicitly_enabled_event.allow_first_timer_coupon)

        self.env.flush_all()
        self.cr.precommit.run()
        messages_before = explicitly_enabled_event.message_ids

        explicitly_enabled_event.allow_first_timer_coupon = False
        self.env.flush_all()
        self.cr.precommit.run()

        tracking_message = explicitly_enabled_event.message_ids - messages_before
        self.assertEqual(len(tracking_message), 1)
        tracking_value = tracking_message.tracking_value_ids.filtered(
            lambda value: value.field_id.name == 'allow_first_timer_coupon'
        )
        self.assertEqual(len(tracking_value), 1)
        self.assertEqual(tracking_value.old_value_integer, 1)
        self.assertEqual(tracking_value.new_value_integer, 0)

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

        focus_discount = self.env['popcorn.discount'].create({
            'name': 'All Focus Promotion',
            'code': 'ALLFOCUS',
            'discount_type': 'fixed_amount',
            'discount_value': 10,
            'customer_type': 'all',
            'event_type': 'focus_club',
        })
        focus_90_event = self._create_focus_event(
            'Focus 90 Ordinary Coupon',
            self.focus_90_tag,
        )
        focus_120_event = self._create_focus_event(
            'Focus 120 Ordinary Coupon',
            self.focus_120_tag,
        )

        self.assertTrue(focus_discount._applies_to_event(focus_90_event))
        self.assertTrue(focus_discount._applies_to_event(focus_120_event))
