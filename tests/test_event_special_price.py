# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import fields
from odoo.tests.common import TransactionCase


class TestEventSpecialPrice(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({
            'name': 'Special Price Test Member',
            'email': 'special-price-test@example.com',
        })
        cls.plan = cls.env['popcorn.membership.plan'].create({
            'name': 'Goldie Regular Test Plan',
            'quota_mode': 'unlimited',
            'duration_days': 90,
            'activation_policy': 'immediate',
            'allowed_regular_offline': True,
            'price_normal': 100.0,
        })
        cls.membership = cls.env['popcorn.membership'].create({
            'partner_id': cls.partner.id,
            'membership_plan_id': cls.plan.id,
            'purchase_price_paid': 100.0,
            'purchase_channel': 'online',
            'price_tier': 'normal',
            'state': 'active',
            'activation_date': fields.Date.today(),
        })

    def _create_event(self, **values):
        start = fields.Datetime.now() + timedelta(days=7)
        event_values = {
            'name': 'Membership Special Price Event',
            'date_begin': start,
            'date_end': start + timedelta(hours=2),
            'event_price': 150.0,
        }
        event_values.update(values)
        return self.env['event.event'].create(event_values)

    def test_second_price_applies_without_social_experience_type(self):
        event = self._create_event(
            second_price=95.0,
            membership_plans_second_price_ids=[(6, 0, self.plan.ids)],
        )

        details = event._get_special_price_details(partner=self.partner)

        self.assertEqual(details['price'], 95.0)
        self.assertEqual(details['tier'], 'second')
        self.assertEqual(details['membership'], self.membership)

    def test_main_price_remains_for_unlisted_membership(self):
        other_plan = self.env['popcorn.membership.plan'].create({
            'name': 'Unlisted Plan',
            'quota_mode': 'unlimited',
            'duration_days': 90,
            'activation_policy': 'immediate',
            'price_normal': 100.0,
        })
        event = self._create_event(
            second_price=95.0,
            membership_plans_second_price_ids=[(6, 0, other_plan.ids)],
        )

        self.assertFalse(event._get_special_price_details(partner=self.partner))

    def test_paid_registration_does_not_attach_or_consume_membership(self):
        event = self._create_event(
            second_price=95.0,
            membership_plans_second_price_ids=[(6, 0, self.plan.ids)],
        )

        registration = self.env['event.registration'].with_context(
            skip_membership_auto_selection=True
        ).create({
            'event_id': event.id,
            'partner_id': self.partner.id,
            'name': self.partner.name,
            'email': self.partner.email,
            'state': 'open',
            'payment_amount': 95.0,
        })

        self.assertFalse(registration.membership_id)
        self.assertEqual(registration.consumption_state, 'pending')
