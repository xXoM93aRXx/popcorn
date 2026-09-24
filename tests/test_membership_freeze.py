# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import fields
from odoo.tests.common import TransactionCase


class TestMembershipFreeze(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.plan = cls.env['popcorn.membership.plan'].create({
            'name': 'Freeze Test Gold Card',
            'quota_mode': 'unlimited',
            'duration_days': 90,
            'activation_policy': 'immediate',
            'freeze_allowed': True,
            'freeze_min_days': 1,
            'freeze_max_total_days': 30,
            'price_normal': 100.0,
        })
        cls.partner = cls.env['res.partner'].create({'name': 'Freeze Test Member'})
        cls.today = fields.Date.today()

    def _create_membership(self):
        return self.env['popcorn.membership'].create({
            'partner_id': self.partner.id,
            'membership_plan_id': self.plan.id,
            'purchase_price_paid': 100.0,
            'purchase_channel': 'online',
            'price_tier': 'normal',
            'state': 'active',
            'activation_date': self.today,
        })

    def test_future_freeze_keeps_requested_dates(self):
        membership = self._create_membership()
        freeze_start = self.today + timedelta(days=10)

        membership.action_freeze(7, freeze_start)

        self.assertEqual(membership.freeze_start, freeze_start)
        self.assertEqual(membership.freeze_end, freeze_start + timedelta(days=6))
        self.assertEqual(membership.freeze_total_days_used, 7)
        self.assertEqual(membership.state, 'active')

    def test_cancel_before_start_restores_days_and_expiration(self):
        membership = self._create_membership()
        original_end = membership.effective_end_date
        membership.action_freeze(7, self.today + timedelta(days=10))
        self.assertEqual(membership.effective_end_date, original_end + timedelta(days=7))

        membership.action_unfreeze()

        self.assertFalse(membership.freeze_active)
        self.assertEqual(membership.freeze_total_days_used, 0)
        self.assertEqual(membership.effective_end_date, original_end)

    def test_early_unfreeze_keeps_only_elapsed_days(self):
        membership = self._create_membership()
        membership.action_freeze(7, self.today)
        membership.write({
            'freeze_start': self.today - timedelta(days=2),
            'freeze_end': self.today + timedelta(days=4),
            'state': 'frozen',
        })

        membership.action_unfreeze()

        self.assertEqual(membership.freeze_total_days_used, 3)
        self.assertEqual(membership.state, 'active')

    def test_freeze_end_date_is_inclusive(self):
        membership = self._create_membership()
        membership.action_freeze(7, self.today)

        self.assertTrue(membership.is_frozen_on(membership.freeze_start))
        self.assertTrue(membership.is_frozen_on(membership.freeze_end))
        self.assertFalse(membership.is_frozen_on(membership.freeze_end + timedelta(days=1)))

    def test_cron_completes_finished_freeze_without_changing_total(self):
        membership = self._create_membership()
        membership.action_freeze(7, self.today)
        membership.write({
            'freeze_start': self.today - timedelta(days=7),
            'freeze_end': self.today - timedelta(days=1),
            'state': 'frozen',
        })

        self.env['popcorn.membership']._cron_update_membership_freezes()

        self.assertFalse(membership.freeze_active)
        self.assertFalse(membership.freeze_start)
        self.assertFalse(membership.freeze_end)
        self.assertEqual(membership.freeze_total_days_used, 7)
        self.assertEqual(membership.state, 'active')
