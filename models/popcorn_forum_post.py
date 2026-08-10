# -*- coding: utf-8 -*-

import json
import logging

import requests

from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)

DEEPSEEK_ENDPOINT = 'https://api.deepseek.com/chat/completions'
DEFAULT_MODEL = 'deepseek-v4-flash'
DEFAULT_TIMEOUT = 30

# The rules text configured in Settings is injected as %s. The instruction to
# answer with a json object must stay in the prompt: DeepSeek's json_object
# response format requires the word "json" to appear in the conversation.
MODERATION_PROMPT = """You are a content moderator for the Popcorn Club community forum.
Decide whether a member's post may be published, based ONLY on the club rules below.
If the post breaks no rule, allow it. Be lenient about tone, typos and short posts.

CLUB RULES:
%s

Respond with a json object only, in exactly this shape:
{"allowed": true or false, "rule_broken": "short rule reference or empty string", "reason": "one short sentence explaining the decision"}"""


class PopcornForumPost(models.Model):
    _name = 'popcorn.forum.post'
    _description = 'Popcorn Club Forum Post'
    _order = 'create_date desc'

    name = fields.Char(
        string='Title',
        required=True,
        help='Short title the member gave the post'
    )

    content = fields.Text(
        string='Content',
        required=True,
        help='Body of the post as written by the member'
    )

    author_id = fields.Many2one(
        'res.partner',
        string='Author',
        required=True,
        ondelete='cascade',
        index=True,
        help='Member who wrote the post'
    )

    state = fields.Selection([
        ('pending', 'Pending Moderation'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('failed', 'Moderation Failed'),
    ], string='Status', default='pending', required=True, index=True,
        help='Result of moderation. Only approved posts can appear on the website')

    is_published = fields.Boolean(
        string='Visible on Website',
        default=False,
        help='Untick to hide an approved post from the forum without changing the moderation verdict'
    )

    moderation_source = fields.Selection([
        ('ai', 'DeepSeek'),
        ('manual', 'Staff'),
    ], string='Decided By', help='Whether the current status came from the AI moderator or a staff override')

    moderation_reason = fields.Text(
        string='Moderation Reason',
        help='Explanation returned by the moderator. Never shown to the author'
    )

    moderation_rule_broken = fields.Char(
        string='Rule Broken',
        help='Rule the moderator considered violated, as free text'
    )

    moderation_date = fields.Datetime(
        string='Moderated On',
        help='When the current status was decided'
    )

    moderation_model = fields.Char(
        string='Model Used',
        help='DeepSeek model that produced the verdict'
    )

    moderation_rules_used = fields.Text(
        string='Rules Applied',
        help='Snapshot of the content regulations at the time of moderation, kept for audit'
    )

    moderation_response = fields.Text(
        string='Raw Response',
        help='Raw moderator response, kept for debugging'
    )

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    @api.model
    def _get_moderation_config(self):
        """Read the forum moderation settings from system parameters."""
        get_param = self.env['ir.config_parameter'].sudo().get_param
        return {
            'enabled': get_param('popcorn.forum_moderation_enabled', 'False') in ('True', 'true', '1'),
            'api_key': (get_param('popcorn.forum_deepseek_api_key') or '').strip(),
            'model': (get_param('popcorn.forum_deepseek_model') or '').strip() or DEFAULT_MODEL,
            'rules': (get_param('popcorn.forum_content_regulations') or '').strip(),
        }

    # ------------------------------------------------------------------
    # Moderation
    # ------------------------------------------------------------------

    def _call_deepseek(self, config):
        """Ask DeepSeek whether this post may be published.

        Returns a dict with allowed/rule_broken/reason/raw, or raises on any
        transport, HTTP or parsing problem so the caller can mark the post
        as failed and leave it for a human.
        """
        self.ensure_one()
        payload = {
            'model': config['model'],
            'messages': [
                {'role': 'system', 'content': MODERATION_PROMPT % config['rules']},
                {'role': 'user', 'content': 'Title: %s\n\nContent: %s' % (self.name or '', self.content or '')},
            ],
            'response_format': {'type': 'json_object'},
            'temperature': 0,
            # Both DeepSeek v4 models reason before answering, and reasoning
            # tokens come out of this budget. Too small a value returns empty
            # content with finish_reason "length".
            'max_tokens': 800,
        }
        response = requests.post(
            DEEPSEEK_ENDPOINT,
            headers={
                'Authorization': 'Bearer %s' % config['api_key'],
                'Content-Type': 'application/json',
            },
            json=payload,
            timeout=DEFAULT_TIMEOUT,
        )
        response.raise_for_status()
        body = response.json()
        message = body['choices'][0]['message']
        content = (message.get('content') or '').strip()
        if not content:
            raise ValueError('Moderator returned an empty verdict (finish_reason: %s)'
                             % body['choices'][0].get('finish_reason'))
        verdict = json.loads(content)
        return {
            'allowed': bool(verdict.get('allowed')),
            'rule_broken': (verdict.get('rule_broken') or '')[:255],
            'reason': verdict.get('reason') or '',
            'raw': content,
        }

    def run_moderation(self):
        """Moderate the posts in self and write the verdict on each.

        Never raises: a post that cannot be moderated is parked in the
        "failed" state so staff can deal with it, rather than being
        published unchecked or lost.
        """
        config = self._get_moderation_config()

        if not config['enabled']:
            # Moderation switched off: the forum is unfiltered by choice.
            self.write({
                'state': 'approved',
                'is_published': True,
                'moderation_source': False,
                'moderation_reason': _('Moderation is disabled in Settings, post published without review.'),
                'moderation_rule_broken': False,
                'moderation_date': fields.Datetime.now(),
                'moderation_model': False,
            })
            return True

        if not config['api_key'] or not config['rules']:
            missing = _('API key') if not config['api_key'] else _('content regulations')
            _logger.warning('Popcorn forum: moderation enabled but %s missing, parking %s post(s) for review',
                            missing, len(self))
            self.write({
                'state': 'failed',
                'is_published': False,
                'moderation_source': False,
                'moderation_reason': _('Moderation is enabled but the %s is not configured in Settings.') % missing,
                'moderation_date': fields.Datetime.now(),
            })
            return False

        for post in self:
            try:
                verdict = post._call_deepseek(config)
            except Exception as error:
                _logger.exception('Popcorn forum: moderation failed for post %s', post.id)
                post.write({
                    'state': 'failed',
                    'is_published': False,
                    'moderation_source': False,
                    'moderation_reason': _('Could not reach the moderator: %s') % error,
                    'moderation_date': fields.Datetime.now(),
                    'moderation_model': config['model'],
                    'moderation_rules_used': config['rules'],
                })
                continue

            post.write({
                'state': 'approved' if verdict['allowed'] else 'rejected',
                'is_published': verdict['allowed'],
                'moderation_source': 'ai',
                'moderation_reason': verdict['reason'],
                'moderation_rule_broken': verdict['rule_broken'] or False,
                'moderation_date': fields.Datetime.now(),
                'moderation_model': config['model'],
                'moderation_rules_used': config['rules'],
                'moderation_response': verdict['raw'],
            })
        return True

    # ------------------------------------------------------------------
    # Staff actions
    # ------------------------------------------------------------------

    def action_force_approve(self):
        """Publish a post regardless of what the AI decided."""
        self.write({
            'state': 'approved',
            'is_published': True,
            'moderation_source': 'manual',
            'moderation_date': fields.Datetime.now(),
        })

    def action_force_reject(self):
        """Take a post down regardless of what the AI decided."""
        self.write({
            'state': 'rejected',
            'is_published': False,
            'moderation_source': 'manual',
            'moderation_date': fields.Datetime.now(),
        })

    def action_rerun_moderation(self):
        """Re-submit the post to DeepSeek, e.g. after editing the regulations."""
        self.run_moderation()

    # ------------------------------------------------------------------
    # Cron
    # ------------------------------------------------------------------

    @api.model
    def _cron_moderate_backlog(self):
        """Retry posts that never got a verdict.

        Moderation normally runs inline when the member submits. This only
        picks up the leftovers from a DeepSeek outage or a half-finished
        configuration, so nothing stays invisible forever.
        """
        backlog = self.search([('state', 'in', ['pending', 'failed'])], limit=50)
        if backlog:
            _logger.info('Popcorn forum: re-moderating %s post(s) from the backlog', len(backlog))
            backlog.run_moderation()
