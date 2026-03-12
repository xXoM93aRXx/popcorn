# -*- coding: utf-8 -*-

from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class BadgePrize(models.Model):
    _name = 'popcorn.badge.prize'
    _description = 'Badge Prize Award'
    _order = 'earned_date desc'

    partner_id = fields.Many2one('res.partner', string='Partner', required=True, ondelete='cascade', index=True)
    badge_id = fields.Many2one('popcorn.badge', string='Badge', required=True, ondelete='cascade')
    amount = fields.Float('Prize Amount', required=True, digits=(16, 2))
    earned_date = fields.Date('Earned Date', default=fields.Date.today, required=True)
    expiry_date = fields.Date('Expiry Date', help='Date after which this prize money will be deducted from the balance. Leave empty for no expiry.')
    expired = fields.Boolean('Expired', default=False, index=True)

    @api.model
    def _cron_expire_badge_prizes(self):
        """Deduct expired badge prize money from partner balances"""
        today = fields.Date.today()
        expired_prizes = self.search([
            ('expired', '=', False),
            ('expiry_date', '!=', False),
            ('expiry_date', '<', today),
        ])
        for prize in expired_prizes:
            partner = prize.partner_id
            if partner.popcorn_money_balance >= prize.amount:
                partner.deduct_popcorn_money(
                    prize.amount,
                    notes='Badge prize expired: %s' % prize.badge_id.name,
                )
            else:
                # Balance lower than prize (already spent) — just mark expired, don't go negative
                _logger.info(
                    'Badge prize expiry: partner %s balance %.2f < prize %.2f for badge %s — marking expired without deduction',
                    partner.id, partner.popcorn_money_balance, prize.amount, prize.badge_id.name,
                )
            prize.expired = True
        _logger.info('Badge prize expiry cron: processed %d expired prizes', len(expired_prizes))
