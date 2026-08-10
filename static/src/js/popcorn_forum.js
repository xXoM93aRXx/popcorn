/**
 * Popcorn Club Forum
 * Opens the "Share something" sheet from the floating button, so the feed
 * is what the page shows on arrival.
 */

odoo.define('popcorn.forum', [], function () {
    'use strict';

    $(document).ready(function () {
        var $modal = $('#popcornForumModal');
        if (!$modal.length) {
            // Not the forum page, or the visitor cannot post.
            return;
        }

        var $body = $('body');

        function openModal() {
            $modal.addClass('is-open');
            $body.addClass('popcorn-forum-modal-open');
            // Skip autofocus on touch devices: the keyboard covers the sheet.
            if (!('ontouchstart' in window)) {
                $modal.find('#popcorn_forum_title').trigger('focus');
            }
        }

        function closeModal() {
            $modal.removeClass('is-open');
            $body.removeClass('popcorn-forum-modal-open');
        }

        $(document).on('click', '[data-forum-open]', function (event) {
            event.preventDefault();
            openModal();
        });

        $modal.on('click', '[data-forum-close]', function (event) {
            event.preventDefault();
            closeModal();
        });

        $(document).on('keydown', function (event) {
            if (event.key === 'Escape' && $modal.hasClass('is-open')) {
                closeModal();
            }
        });

        // Moderation runs while the request is in flight, so the response can
        // take a few seconds. Block the second click that would double post.
        $modal.on('submit', 'form', function () {
            var $submit = $(this).find('.popcorn-forum-submit');
            $submit.prop('disabled', true);
        });

        // Reopen the sheet when the post bounced on validation, so the member
        // can correct it rather than hunting for the button again.
        var params = new URLSearchParams(window.location.search);
        var reopenOn = ['empty', 'too_long'];
        if (reopenOn.indexOf(params.get('error')) !== -1) {
            openModal();
        }
    });
});
