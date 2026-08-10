# -*- coding: utf-8 -*-

import logging
from datetime import datetime, timedelta

from odoo import http, fields, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import pager as portal_pager

_logger = logging.getLogger(__name__)

POSTS_PER_PAGE = 20
TITLE_MAX_LENGTH = 120
CONTENT_MAX_LENGTH = 5000
# Each post costs one DeepSeek call, so cap how fast a single member can spend.
POSTS_PER_HOUR = 5


class PopcornForumController(http.Controller):
    """Member forum with AI moderation.

    Reading is public. Posting is limited to members with a live membership,
    and every post goes through DeepSeek before it can appear.
    """

    def _get_active_membership(self, partner):
        """Return the partner's live memberships, matching the rest of the module."""
        if not partner:
            return request.env['popcorn.membership']
        return request.env['popcorn.membership'].sudo().search([
            ('partner_id', '=', partner.id),
            ('state', 'in', ['active', 'frozen']),
        ])

    def _get_thank_you_message(self):
        """Company message in the visitor's language, falling back to the module translation."""
        message = request.env.company.sudo().forum_thank_you_message
        return message or _('Thanks for sharing with the club! Your post has been received.')

    @http.route(['/forum', '/forum/page/<int:page>'], type='http', auth="public", website=True, sitemap=True)
    def forum_page(self, page=1, **kwargs):
        """Public forum feed, with the posting form for members."""
        partner = request.env.user.partner_id if not request.env.user._is_public() else None
        is_member = bool(self._get_active_membership(partner))

        Post = request.env['popcorn.forum.post'].sudo()
        domain = [('state', '=', 'approved'), ('is_published', '=', True)]
        total = Post.search_count(domain)

        pager = portal_pager(
            url='/forum',
            total=total,
            page=page,
            step=POSTS_PER_PAGE,
        )
        posts = Post.search(domain, limit=POSTS_PER_PAGE, offset=pager['offset'])

        values = {
            'posts': posts,
            'pager': pager,
            'is_member': is_member,
            'is_logged_in': bool(partner),
            'thanks': kwargs.get('thanks') == '1',
            'thank_you_message': self._get_thank_you_message(),
            'error': kwargs.get('error'),
            'title_max_length': TITLE_MAX_LENGTH,
            'content_max_length': CONTENT_MAX_LENGTH,
        }
        return request.render('popcorn.popcorn_forum_page', values)

    @http.route(['/forum/submit'], type='http', auth="user", methods=['POST'], website=True, csrf=True)
    def forum_submit(self, **kwargs):
        """Accept a post, moderate it, and thank the member either way."""
        partner = request.env.user.partner_id

        if not self._get_active_membership(partner):
            return request.redirect('/forum?error=members_only')

        title = (kwargs.get('title') or '').strip()
        content = (kwargs.get('content') or '').strip()

        if not title or not content:
            return request.redirect('/forum?error=empty')
        if len(title) > TITLE_MAX_LENGTH or len(content) > CONTENT_MAX_LENGTH:
            return request.redirect('/forum?error=too_long')

        Post = request.env['popcorn.forum.post'].sudo()
        recent = Post.search_count([
            ('author_id', '=', partner.id),
            ('create_date', '>=', fields.Datetime.to_string(datetime.now() - timedelta(hours=1))),
        ])
        if recent >= POSTS_PER_HOUR:
            return request.redirect('/forum?error=rate_limited')

        # author_id comes from the session, never from the form.
        post = Post.create({
            'name': title,
            'content': content,
            'author_id': partner.id,
            'state': 'pending',
        })

        # Runs inline so an approved post is live by the time the member
        # lands back on the feed. Failures park the post rather than raise.
        try:
            post.run_moderation()
        except Exception:
            _logger.exception('Popcorn forum: unexpected error moderating post %s', post.id)

        # Same message whichever way the verdict went.
        return request.redirect('/forum?thanks=1')
