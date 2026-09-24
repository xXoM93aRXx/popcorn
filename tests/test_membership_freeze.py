# -*- coding: utf-8 -*-

from datetime import datetime, time, timedelta

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
        cls.partner = cls.env['res.partner'].create({
            'name': 'Freeze Test Member',
            'email': 'freeze-test@example.com',
        })
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

    def _create_registration(self, membership, event_day, name):
        event_start = datetime.combine(event_day, time(12, 0))
        event = self.env['event.event'].create({
            'name': name,
            'date_begin': event_start,
            'date_end': event_start + timedelta(hours=2),
            'date_tz': 'UTC',
            'cancellation_deadline_hours': 1000,
        })
        return self.env['event.registration'].create({
            'event_id': event.id,
            'partner_id': self.partner.id,
            'membership_id': membership.id,
            'name': self.partner.name,
            'email': self.partner.email,
            'state': 'open',
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

    def test_penalty_freeze_starts_tomorrow_and_cancels_bookings(self):
        membership = self._create_membership()
        first_penalty_day = self.today + timedelta(days=1)
        inside_registration = self._create_registration(
            membership, first_penalty_day, 'Inside Penalty Period',
        )
        outside_registration = self._create_registration(
            membership, first_penalty_day + timedelta(days=3), 'Outside Penalty Period',
        )

        membership._apply_attendance_policy_freeze(3)

        self.assertEqual(membership.freeze_start, first_penalty_day)
        self.assertEqual(membership.freeze_end, first_penalty_day + timedelta(days=2))
        self.assertTrue(membership.freeze_is_penalty)
        self.assertEqual(membership.state, 'active')
        self.assertEqual(inside_registration.state, 'cancel')
        self.assertEqual(outside_registration.state, 'open')
        self.assertFalse(inside_registration.late_no_show_incident)

    def test_penalty_replaces_separate_scheduled_freeze_and_releases_days(self):
        membership = self._create_membership()
        membership.action_freeze(5, self.today + timedelta(days=10))
        self.assertEqual(membership.freeze_total_days_used, 5)

        membership._apply_attendance_policy_freeze(3)

        self.assertEqual(membership.freeze_start, self.today + timedelta(days=1))
        self.assertEqual(membership.freeze_end, self.today + timedelta(days=3))
        self.assertEqual(membership.freeze_total_days_used, 0)
        self.assertTrue(membership.freeze_is_penalty)

    def test_third_incident_applies_penalty_and_cancels_booking(self):
        membership = self._create_membership()
        for index in range(3):
            incident = self._create_registration(
                membership,
                self.today - timedelta(days=index + 1),
                'Incident %s' % index,
            )
            incident.write({
                'late_no_show_incident': True,
                'late_no_show_incident_date': fields.Datetime.now(),
            })
        affected_booking = self._create_registration(
            membership,
            self.today + timedelta(days=2),
            'Booking Cancelled by Penalty',
        )

        membership._evaluate_unlimited_late_no_show_policy()

        self.assertTrue(membership.freeze_is_penalty)
        self.assertEqual(membership.attendance_policy_freeze_count, 1)
        self.assertEqual(affected_booking.state, 'cancel')
