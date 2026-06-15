# -*- coding: utf-8 -*-

from odoo import http, _
from odoo.http import request
from odoo.exceptions import ValidationError
import json
import logging
from odoo import fields
from werkzeug.exceptions import NotFound
from werkzeug.utils import redirect

_logger = logging.getLogger(__name__)

class PopcornMembershipController(http.Controller):
    """Controller for standalone membership purchase"""
    
    def _is_sms_config_active(self):
        """Check if SMS configuration is active"""
        try:
            sms_config = request.env['sms.config'].sudo().search([('is_active', '=', True)], limit=1)
            return bool(sms_config and sms_config.is_active)
        except Exception as e:
            _logger.warning('Failed to check SMS config status: %s', str(e))
            return False
    
    @http.route(['/memberships/upload_document'], type='http', auth='user', website=True, methods=['POST'])
    def upload_membership_document(self, **post):
        """AJAX endpoint: upload student card or ID card, return attachment_id.
        Expects multipart field name matching the doc_type param ('student_card' or 'id_card').
        """
        import base64
        try:
            doc_type = post.get('doc_type', 'student_card')
            uploaded_file = request.httprequest.files.get(doc_type)
            if not uploaded_file or not uploaded_file.filename:
                return request.make_response(
                    json.dumps({'error': 'No file provided'}),
                    headers=[('Content-Type', 'application/json')]
                )

            allowed_mimetypes = {'image/jpeg', 'image/png', 'image/gif', 'image/webp', 'application/pdf'}
            if uploaded_file.content_type not in allowed_mimetypes:
                return request.make_response(
                    json.dumps({'error': 'Invalid file type. Please upload JPG, PNG, or PDF.'}),
                    headers=[('Content-Type', 'application/json')]
                )

            file_data = uploaded_file.read()
            if len(file_data) > 5 * 1024 * 1024:
                return request.make_response(
                    json.dumps({'error': 'File too large. Maximum size is 5MB.'}),
                    headers=[('Content-Type', 'application/json')]
                )

            attachment = request.env['ir.attachment'].sudo().create({
                'name': uploaded_file.filename,
                'type': 'binary',
                'datas': base64.b64encode(file_data).decode('utf-8'),
                'mimetype': uploaded_file.content_type,
                'res_model': 'popcorn.membership',
                'res_id': 0,
            })

            return request.make_response(
                json.dumps({'attachment_id': attachment.id, 'filename': uploaded_file.filename}),
                headers=[('Content-Type', 'application/json')]
            )
        except Exception as e:
            _logger.error(f"Document upload failed: {str(e)}", exc_info=True)
            return request.make_response(
                json.dumps({'error': 'Upload failed. Please try again.'}),
                headers=[('Content-Type', 'application/json')]
            )

    # Keep old route as alias for backwards compatibility
    @http.route(['/memberships/upload_student_card'], type='http', auth='user', website=True, methods=['POST'])
    def upload_student_card(self, **post):
        post['doc_type'] = 'student_card'
        return self.upload_membership_document(**post)

    @http.route(['/memberships'], type='http', auth="public", website=True)
    def memberships_list(self, **post):
        """Display all available membership plans"""
        # Check if user is logged in (public user means not logged in)
        if request.env.user.id == request.env.ref('base.public_user').id:
            return request.redirect('/web/login?redirect=' + request.httprequest.url)
        
        # Get all active and published membership plans
        membership_plans = request.env['popcorn.membership.plan'].search([
            ('active', '=', True),
            ('website_published', '=', True)
        ], order='sequence, name')
        
        # Get error message from URL parameter if present
        error_message = request.params.get('error', '')
        
        if error_message:
            # URL decode the error message
            import urllib.parse
            error_message = urllib.parse.unquote(error_message)
        
        # Also check for session-based error message
        if not error_message and 'error_message' in request.session:
            error_message = request.session['error_message']
            # Clear the session error message to prevent it from showing again
            del request.session['error_message']
        
        
        # Check if user is a first-timer
        is_first_timer = request.env.user.partner_id.is_first_timer
        
        # Check for renewable memberships
        active_memberships = request.env['popcorn.membership'].search([
            ('partner_id', '=', request.env.user.partner_id.id),
            ('state', 'in', ['active', 'frozen'])
        ])
        
        renewal_banner_info = None
        for membership in active_memberships:
            if membership.is_eligible_for_renewal():
                plan = membership.membership_plan_id
                
                # Calculate days/points left for banner display
                days_left = 0
                points_left = 0
                
                # Get user name for placeholder replacement
                user_name = ''
                if request.env.user.partner_id:
                    user_name = request.env.user.partner_id.name or ''
                
                if plan.quota_mode == 'points':
                    # Freedom card - show points left
                    points_left = membership.points_remaining
                    banner_text = plan.renewal_banner_text or ''
                    banner_text = banner_text.replace('{points_left}', str(points_left))
                    banner_text = banner_text.replace('{name}', user_name)
                elif plan.quota_mode == 'bucket_counts':
                    # Experience card - no renewal discount, use no-discount banner text
                    if membership.activation_date and plan.renewal_window_end_days > 0:
                        days_since_activation = (fields.Date.today() - membership.activation_date).days
                        days_left = plan.renewal_window_end_days - days_since_activation
                    banner_text = plan.renewal_banner_text_no_discount or plan.renewal_banner_text or ''
                    banner_text = banner_text.replace('{days_left}', str(max(0, days_left)))
                    banner_text = banner_text.replace('{name}', user_name)
                else:
                    # Gold cards: days left until early_renew_window_days before expiry
                    if membership.effective_end_date:
                        days_until_expiry = (membership.effective_end_date - fields.Date.today()).days
                        min_days = plan.early_renew_window_days or 30
                        days_left = days_until_expiry - min_days
                        banner_text = plan.renewal_banner_text or ''
                        banner_text = banner_text.replace('{days_left}', str(max(0, days_left)))
                        banner_text = banner_text.replace('{name}', user_name)
                    else:
                        banner_text = plan.renewal_banner_text or ''
                        banner_text = banner_text.replace('{name}', user_name)
                
                renewal_banner_info = {
                    'membership': membership,
                    'banner_text': banner_text,
                    'days_left': days_left,
                    'points_left': points_left,
                }
                break  # Only show banner for first eligible membership
        
        # Check if user is eligible for renewal discount (has active membership eligible for renewal)
        has_renewal_discount = False
        for membership in active_memberships:
            if membership.is_eligible_for_renewal_discount():
                has_renewal_discount = True
                break
        
        # Get discount information for each plan
        plan_discounts = {}
        for plan in membership_plans:
            # First-timer and renewal pricing are exclusive — no additional discounts stack
            if has_renewal_discount or is_first_timer:
                best_price = plan.price_first_timer if plan.price_first_timer > 0 else plan.price_normal
                available_discounts = request.env['popcorn.discount'].browse([])
                best_discount = None
                extra_days = 0
            else:
                available_discounts = plan.get_available_discounts(request.env.user.partner_id)
                best_price, best_discount, extra_days = plan.get_best_discount_with_extra_days(request.env.user.partner_id, original_price=plan.price_normal)
            
            plan_discounts[plan.id] = {
                'available_discounts': available_discounts,
                'best_price': best_price,
                'best_discount': best_discount,
                'original_price': plan.price_normal,
                'first_timer_price': plan.price_first_timer,
                'extra_days': extra_days,
                'is_renewal': has_renewal_discount,
            }
        
        # First-timer grace period banner
        partner = request.env.user.partner_id
        first_timer_pending_date = False
        if partner.is_first_timer and partner.pdb_pending_date:
            today = fields.Date.today()
            if partner.pdb_pending_date >= today:
                first_timer_pending_date = partner.pdb_pending_date
            else:
                # Grace period already expired; apply PDB now in case cron hasn't run
                partner.sudo().write({'pdb': True, 'is_first_timer': False})

        # Find the highest-priority active public discount to show in the banner
        public_discount = request.env['popcorn.discount'].sudo().search([
            ('is_public', '=', True),
            ('active', '=', True),
            ('is_valid', '=', True),
        ], order='sequence, name', limit=1)

        values = {
            'membership_plans': membership_plans,
            'error_message': error_message,
            'is_first_timer': is_first_timer,
            'plan_discounts': plan_discounts,
            'renewal_banner_info': renewal_banner_info,
            'public_discount': public_discount or False,
            'first_timer_pending_date': str(first_timer_pending_date) if first_timer_pending_date else False,
        }

        return request.render('popcorn.membership_plans_website_page', values)
    
    @http.route(['/memberships/website'], type='http', auth="public", website=True)
    def memberships_website_page(self, **post):
        """Display membership plans as a website page (editable by website editor)"""
        # Check if user is logged in (public user means not logged in)
        if request.env.user.id == request.env.ref('base.public_user').id:
            return request.redirect('/web/login?redirect=' + request.httprequest.url)
        
        return request.render('popcorn.membership_plans_website_page')
    
    @http.route(['/memberships/<model("popcorn.membership.plan"):plan>'], type='http', auth="public", website=True)
    def membership_plan_detail(self, plan, **post):
        """Display detailed information about a specific membership plan"""
        # Check if user is logged in (public user means not logged in)
        if request.env.user.id == request.env.ref('base.public_user').id:
            return request.redirect('/web/login?redirect=' + request.httprequest.url)
        
        
        values = {
            'plan': plan,
            'benefits': plan.get_membership_benefits(),
        }
        
        return request.render('popcorn.membership_plan_detail_page', values)
    
    @http.route(['/memberships/<model("popcorn.membership.plan"):plan>/checkout'], type='http', auth="public", website=True)
    def membership_checkout(self, plan, **post):
        """Display checkout page for membership purchase"""
        # Check if user is logged in (public user means not logged in)
        if request.env.user.id == request.env.ref('base.public_user').id:
            return request.redirect('/web/login?redirect=' + request.httprequest.url)
        
        # Check if this is an upgrade (from URL parameters)
        is_upgrade = post.get('upgrade') == 'true' or request.params.get('upgrade') == 'true'
        upgrade_details = None
        
        if is_upgrade:
            # Get upgrade details from URL parameters (not session)
            membership_id = post.get('membership_id') or request.params.get('membership_id')
            upgrade_price = post.get('upgrade_price') or request.params.get('upgrade_price')
            
            if not membership_id or not upgrade_price:
                return request.redirect('/my/cards')
            
            try:
                upgrade_details = {
                    'membership_id': int(membership_id),
                    'target_plan_id': plan.id,
                    'upgrade_price': float(upgrade_price),
                    'is_upgrade': True
                }
            except (ValueError, TypeError):
                return request.redirect('/my/cards')
        
        # Check if this is a renewal (from URL parameter or from renewal eligibility)
        is_renewal = post.get('renew') == 'true'
        renewal_details = None
        
        if is_renewal:
            renewal_details = request.session.get('renewal_details', {})
            if not renewal_details or renewal_details.get('plan_id') != plan.id:
                return request.redirect('/my/cards')
        
        # Auto-detect renewal eligibility if user has an active membership eligible for renewal discount
        # IMPORTANT: Only check for renewal if NOT an upgrade (upgrade takes precedence)
        if not is_renewal and not is_upgrade:
            active_memberships = request.env['popcorn.membership'].search([
                ('partner_id', '=', request.env.user.partner_id.id),
                ('state', 'in', ['active', 'frozen'])
            ])
            for membership in active_memberships:
                if membership.is_eligible_for_renewal_discount():
                    is_renewal = True
                    break
        
        # Check if user is a first-timer
        is_first_timer = request.env.user.partner_id.is_first_timer
        
        partner = request.env.user.partner_id
        payment_providers = request.env['payment.provider'].sudo().search([('state', '=', 'enabled')])
        
        # First-timer and renewal pricing are exclusive — no additional discounts stack
        if is_renewal or is_first_timer:
            best_price = plan.price_first_timer if plan.price_first_timer > 0 else plan.price_normal
            best_discount = None
            extra_days = 0
        else:
            best_price, best_discount, extra_days = plan.get_best_discount_with_extra_days(request.env.user.partner_id, original_price=plan.price_normal)
        
        plan_discounts = {
            plan.id: {
                'best_price': best_price,
                'best_discount': best_discount,
                'original_price': plan.price_normal,
                'extra_days': extra_days,
            }
        }
        
        # Check if SMS config is active - only require verification if SMS is active
        sms_config_active = self._is_sms_config_active()
        phone_verification_required = sms_config_active and not partner.phone
        
        checkout_error_map = {
            'phone_already_used': '哎呀，好像这个操作无法完成，因为该手机号码已被另一个会员使用。请联系小帕寻求帮助。',
        }
        checkout_error_code = request.params.get('error', '')
        checkout_error_message = checkout_error_map.get(checkout_error_code, '')

        values = {
            'plan': plan,
            'payment_providers': payment_providers,
            'is_upgrade': is_upgrade,
            'is_renewal': is_renewal,
            'upgrade_details': upgrade_details,
            'renewal_details': renewal_details,
            'is_first_timer': is_first_timer,
            'plan_discounts': plan_discounts,
            'phone_verification_required': phone_verification_required,
            'sms_config_active': sms_config_active,
            'partner': partner,
            'checkout_error_message': checkout_error_message,
        }

        return request.render('popcorn.membership_checkout_page', values)
    
    @http.route(['/memberships/<model("popcorn.membership.plan"):plan>/process_checkout'], type='http', auth="public", website=True, methods=['POST'])
    def process_membership_checkout(self, plan, **post):
        """Process the checkout form and initiate payment transaction"""
        # Check if user is logged in (public user means not logged in)
        if request.env.user.id == request.env.ref('base.public_user').id:
            return request.redirect('/web/login?redirect=' + request.httprequest.url)
        
        try:
            # Get partner first (needed for renewal check)
            partner = request.env.user.partner_id
            
            # Check if this is an upgrade (from URL parameters or POST data)
            is_upgrade = post.get('upgrade') == 'true' or request.params.get('upgrade') == 'true'
            upgrade_details = None
            
            _logger.info(f"process_membership_checkout - Initial check: is_upgrade from post.get('upgrade'): {post.get('upgrade')}, from request.params.get('upgrade'): {request.params.get('upgrade')}, final is_upgrade: {is_upgrade}")
            
            if is_upgrade:
                # Get upgrade details from URL parameters or POST data (not session)
                membership_id = post.get('membership_id') or request.params.get('membership_id')
                upgrade_price = post.get('upgrade_price') or request.params.get('upgrade_price')
                
                if membership_id and upgrade_price:
                    try:
                        upgrade_details = {
                            'membership_id': int(membership_id),
                            'target_plan_id': plan.id,
                            'upgrade_price': float(upgrade_price),
                            'is_upgrade': True
                        }
                    except (ValueError, TypeError):
                        # Invalid upgrade parameters - treat as new purchase
                        is_upgrade = False
                        upgrade_details = None
                else:
                    # Missing upgrade parameters - treat as new purchase
                    is_upgrade = False
                    upgrade_details = None
            
            # Check if this is a renewal (determined by checking actual membership data, not session)
            # User has ANY active/frozen membership (any plan) that's eligible for renewal discount
            # Renewal discount can be applied to purchase ANY plan
            # IMPORTANT: Upgrade takes precedence - don't check renewal if upgrade is in progress
            is_renewal = False
            
            # Only check for renewal eligibility if NOT an upgrade
            if not is_upgrade:
                # Check for ANY active/frozen memberships (any plan) - renewal can apply to any plan purchase
                active_memberships = request.env['popcorn.membership'].search([
                    ('partner_id', '=', partner.id),
                    ('state', 'in', ['active', 'frozen'])
                ])
                _logger.info(f"Checking renewal eligibility for plan {plan.id} (name: {plan.name}), partner {partner.id}, found {len(active_memberships)} active/frozen memberships (any plan)")
                
                # Log details of found memberships
                for membership in active_memberships:
                    _logger.info(f"DEBUG: Found active/frozen membership ID {membership.id}: plan_id={membership.membership_plan_id.id}, plan_name={membership.membership_plan_id.name if membership.membership_plan_id else 'N/A'}, state={membership.state}, eligible_check={membership.is_eligible_for_renewal_discount()}")
                    if membership.is_eligible_for_renewal_discount():
                        is_renewal = True
                        _logger.info(f"Renewal detected: Membership {membership.id} (plan: {membership.membership_plan_id.name if membership.membership_plan_id else 'N/A'}) is eligible for renewal discount - applying to purchase of plan {plan.name}")
                        break
                
                if not is_renewal:
                    _logger.info(f"Not a renewal: No eligible memberships found for renewal discount")
            else:
                _logger.info(f"Upgrade in progress - skipping renewal eligibility check")
            
            # Check if user wants to use popcorn money
            use_popcorn_money = post.get('use_popcorn_money') == 'on'
            
            # Ensure partner exists (important for internal users)
            if not partner or not partner.exists():
                _logger.error(f"User {request.env.user.login} does not have a partner record")
                return request.redirect('/memberships/%s/checkout?error=no_partner' % plan.id)
            
            popcorn_money_balance = partner.popcorn_money_balance
            
            # Update partner name immediately
            partner.write({'name': post.get('name')})

            Users = request.env['res.users'].sudo()
            sanitized_input_phone = Users._sanitize_phone(post.get('phone'))
            if not sanitized_input_phone:
                return request.redirect('/memberships/%s/checkout?error=invalid_phone_format' % plan.id)

            # Check if SMS config is active - only require verification if SMS is active
            sms_config_active = self._is_sms_config_active()
            sanitized_partner_phone = Users._sanitize_phone(partner.phone)
            phone_needs_verification = False

            if phone_needs_verification:
                verification_code = (post.get('phone_verification_code') or '').strip()
                if not verification_code:
                    return request.redirect('/memberships/%s/checkout?error=phone_verification_required' % plan.id)

                candidate_phone = request.session.get('phone_verification_candidate')
                if not candidate_phone or candidate_phone != sanitized_input_phone:
                    _logger.warning(
                        'Phone verification mismatch for membership checkout: input=%s, candidate=%s, partner_id=%s',
                        sanitized_input_phone,
                        candidate_phone,
                        partner.id,
                    )
                    return request.redirect('/memberships/%s/checkout?error=phone_verification_mismatch' % plan.id)

                user = request.env.user.sudo()
                is_valid, error_msg = user.verify_phone_code(verification_code)
                if not is_valid:
                    request.session.pop('phone_verification_candidate', None)
                    return request.redirect('/memberships/%s/checkout?error=invalid_verification_code' % plan.id)

                try:
                    partner.write({
                        'phone': sanitized_input_phone,
                        'mobile': sanitized_input_phone,
                    })
                except ValidationError:
                    return request.redirect('/memberships/%s/checkout?error=phone_already_used' % plan.id)
                request.session.pop('phone_verification_candidate', None)
            else:
                try:
                    partner.write({
                        'phone': sanitized_input_phone,
                        'mobile': sanitized_input_phone,
                    })
                except ValidationError:
                    return request.redirect('/memberships/%s/checkout?error=phone_already_used' % plan.id)
            
            # Get customer signature if provided
            customer_signature = post.get('customer_signature')
            
            # Get applied discount ID from coupon code (if any)
            applied_discount_id = post.get('applied_discount_id')
            applied_discount = None
            
            if applied_discount_id:
                try:
                    applied_discount = request.env['popcorn.discount'].browse(int(applied_discount_id))
                    if not applied_discount.exists() or not applied_discount._is_currently_valid():
                        applied_discount = None
                except (ValueError, TypeError):
                    applied_discount = None
            
            # Calculate the amount to charge
            # Priority: Upgrade takes precedence over renewal pricing
            # If upgrade is in progress, use upgrade pricing. Otherwise, if user is eligible for renewal discount, they get renewal pricing (first-timer + discounts)
            if is_upgrade:
                # Upgrade pricing (takes precedence)
                amount = upgrade_details.get('upgrade_price', 0)
                _logger.info(f"Amount calculation: Upgrade - amount = {amount}")
            elif is_renewal:
                # Renewal pricing is exclusive — first-timer price only, no discounts stack
                amount = plan.price_first_timer if plan.price_first_timer > 0 else plan.price_normal
                best_discount = None
                extra_days = 0
                _logger.info(f"Amount calculation: Renewal - amount = {amount} (no discount stacking)")
            else:
                if partner.is_first_timer and plan.price_first_timer > 0:
                    # First-timer pricing is exclusive — first-timer price only, no discounts stack
                    amount = plan.price_first_timer
                    best_discount = None
                    extra_days = 0
                elif applied_discount:
                    amount = applied_discount.get_discounted_price(plan, plan.price_normal, partner)
                    best_discount = applied_discount
                    extra_days = applied_discount.get_extra_days(plan, partner)
                else:
                    best_price, best_discount, extra_days = plan.get_best_discount_with_extra_days(partner, original_price=plan.price_normal)
                    amount = best_price
            
            # Calculate how much popcorn money to use and remaining amount
            popcorn_money_to_use = 0
            remaining_amount = amount
            
            if use_popcorn_money and popcorn_money_balance > 0:
                popcorn_money_to_use = min(popcorn_money_balance, amount)
                remaining_amount = amount - popcorn_money_to_use
                _logger.info(f"Popcorn money calculation: balance = {popcorn_money_balance}, to_use = {popcorn_money_to_use}, remaining = {remaining_amount}")
            else:
                _logger.info(f"No popcorn money used, remaining amount = {remaining_amount}")
            
            # Validate form data
            if not post.get('name') or not post.get('phone'):
                return request.redirect('/memberships/%s/checkout?error=missing_fields' % plan.id)
            # Require friend's phone if buy-together is enabled
            if plan.buy_together_enabled:
                friend_phone_raw = (post.get('friend_phone') or '').strip()
                if not friend_phone_raw:
                    return request.redirect('/memberships/%s/checkout?error=friend_phone_required' % plan.id)
            
            if not post.get('payment_method_id') and remaining_amount > 0:
                return request.redirect('/memberships/%s/checkout?error=missing_payment_method' % plan.id)
            
            if not post.get('terms_accepted'):
                return request.redirect('/memberships/%s/checkout?error=terms_not_accepted' % plan.id)

            # Validate student card and ID card uploads if this is a student plan
            student_card_attachment_id = None
            id_card_attachment_id = None
            if plan.is_student_plan:
                for field_name, error_code in [
                    ('student_card_attachment_id', 'student_card_required'),
                    ('id_card_attachment_id', 'id_card_required'),
                ]:
                    raw_id = post.get(field_name, '').strip()
                    if not raw_id:
                        return request.redirect('/memberships/%s/checkout?error=%s' % (plan.id, error_code))
                    try:
                        att_id = int(raw_id)
                        attachment = request.env['ir.attachment'].sudo().browse(att_id)
                        if not attachment.exists():
                            return request.redirect('/memberships/%s/checkout?error=%s_invalid' % (plan.id, field_name))
                        if field_name == 'student_card_attachment_id':
                            student_card_attachment_id = att_id
                        else:
                            id_card_attachment_id = att_id
                    except (ValueError, TypeError):
                        return request.redirect('/memberships/%s/checkout?error=%s_invalid' % (plan.id, field_name))

            # Get payment method/provider ID
            payment_method_id = post.get('payment_method_id')
            
            # If popcorn money covers the full amount, treat as manual payment
            if remaining_amount <= 0:
                payment_method_id = 'manual'
            
            # Check if it's a manual payment (fallback)
            if payment_method_id == 'manual':
                # Handle upgrade vs renewal vs new membership
                # Renewal takes precedence - create new membership with renewal pricing
                if is_renewal:
                    # Create new membership with renewal pricing (first-timer + discounts)
                    membership = self._create_membership_from_plan(
                        plan,
                        partner,
                        customer_signature=customer_signature,
                        applied_discount=applied_discount,
                        is_renewal=is_renewal,
                        student_card_attachment_id=student_card_attachment_id,
                        id_card_attachment_id=id_card_attachment_id,
                    )
                    _logger.info(f"Renewal membership created with ID: {membership.id}")
                    
                    
                    # Deduct popcorn money if used
                    if use_popcorn_money and popcorn_money_to_use > 0:
                        _logger.info(f"Deducting popcorn money: {popcorn_money_to_use}")
                        partner.deduct_popcorn_money(popcorn_money_to_use, f'Membership renewal: {plan.display_name}')
                    
                    # Log the renewal
                    if remaining_amount <= 0:
                        payment_message = _('Membership renewal completed using Popcorn Money. Price: %s%s. Popcorn money used: %s%s. No additional payment required.') % (plan.currency_id.symbol, amount, plan.currency_id.symbol, popcorn_money_to_use)
                    else:
                        payment_message = _('Manual payment requested for renewal. Payment method: Manual')
                        if use_popcorn_money and popcorn_money_to_use > 0:
                            payment_message += _('. Popcorn money used: %s%s. Remaining: %s%s') % (plan.currency_id.symbol, popcorn_money_to_use, plan.currency_id.symbol, remaining_amount)
                    
                    membership.message_post(body=payment_message)
                    
                    # Redirect based on payment status
                    if remaining_amount <= 0:
                        return request.redirect('/memberships/success?membership_id=%s&payment_completed=true' % membership.id)
                    else:
                        return request.redirect('/memberships/success?membership_id=%s&payment_pending=true' % membership.id)
                elif is_upgrade:
                    # Upgrade existing membership
                    # Pass remaining_amount (actual money paid) instead of full upgrade_price
                    membership = self._create_upgrade_membership(
                        plan, 
                        partner, 
                        upgrade_details,
                        actual_payment_amount=remaining_amount  # Use actual money paid, not full upgrade_price
                    )
                    _logger.info(f"Upgrade membership created with ID: {membership.id}")
                    
                    
                    # Deduct popcorn money if used
                    if use_popcorn_money and popcorn_money_to_use > 0:
                        _logger.info(f"Deducting popcorn money: {popcorn_money_to_use}")
                        partner.deduct_popcorn_money(popcorn_money_to_use, f'Membership upgrade: {plan.display_name}')
                    
                    # Log the upgrade
                    if remaining_amount <= 0:
                        payment_message = _('Membership upgrade completed using Popcorn Money. Price: %s%s. Popcorn money used: %s%s. No additional payment required.') % (plan.currency_id.symbol, amount, plan.currency_id.symbol, popcorn_money_to_use)
                    else:
                        payment_message = _('Manual payment requested for upgrade. Payment method: Manual')
                        if use_popcorn_money and popcorn_money_to_use > 0:
                            payment_message += _('. Popcorn money used: %s%s. Remaining: %s%s') % (plan.currency_id.symbol, popcorn_money_to_use, plan.currency_id.symbol, remaining_amount)
                    
                    membership.message_post(body=payment_message)
                    
                    # Redirect to upgrade success page
                    if remaining_amount <= 0:
                        return request.redirect('/my/cards/upgrade/success?membership_id=%s&payment_completed=true' % membership.id)
                    else:
                        return request.redirect('/my/cards/upgrade/success?membership_id=%s&payment_pending=true' % membership.id)
                else:
                    # Create new membership
                    membership = self._create_membership_from_plan(
                        plan,
                        partner,
                        customer_signature=customer_signature,
                        applied_discount=applied_discount,
                        is_renewal=is_renewal,
                        student_card_attachment_id=student_card_attachment_id,
                        id_card_attachment_id=id_card_attachment_id,
                    )
                    
                    # Pair activation by phone for buy-together enabled plans
                    if plan.buy_together_enabled:
                        # Always start as pending_buy_together
                        membership.write({'state': 'pending_buy_together'})
                        friend_phone = (post.get('friend_phone') or '').strip()
                        # Normalize whitespace (exact match)
                        normalized_phone = friend_phone.replace(' ', '')
                        if normalized_phone:
                            # Find other pending membership of same plan with exact phone match
                            other = request.env['popcorn.membership'].sudo().search([
                                ('id', '!=', membership.id),
                                ('membership_plan_id', '=', plan.id),
                                ('state', '=', 'pending_buy_together'),
                                ('partner_id.phone', '!=', False),
                                ('partner_id.phone', '=', normalized_phone)
                            ], limit=1, order='create_date asc')
                            if other and other.partner_id and other.partner_id.id != partner.id:
                                today = fields.Date.today()
                                # Link and activate both
                                membership.write({
                                    'buy_together_partner_id': other.partner_id.id,
                                    'state': 'active',
                                    'activation_date': today,
                                })
                                other.write({
                                    'buy_together_partner_id': partner.id,
                                    'state': 'active',
                                    'activation_date': today,
                                })
                                membership.message_post(body=_('Activated together with %s') % (other.partner_id.name or ''))
                                other.message_post(body=_('Activated together with %s') % (partner.name or ''))
                        # If not found or no phone provided, remain pending_buy_together
                    else:
                        # Respect the plan's activation policy instead of forcing state
                        if remaining_amount <= 0:
                            # Fully paid with Popcorn Money - follow plan's activation policy
                            if plan.activation_policy == 'immediate':
                                membership.write({'state': 'active', 'activation_date': fields.Date.today()})
                                _logger.info("Membership activated immediately (plan policy)")
                            elif plan.activation_policy == 'first_attendance':
                                membership.write({'state': 'pending'})  # Will be activated on first event registration
                                _logger.info("Membership set to pending (will activate on first event registration)")
                            elif plan.activation_policy == 'manual':
                                membership.write({'state': 'pending'})  # Requires manual activation
                                _logger.info("Membership set to pending (requires manual activation)")
                        else:
                            # Partial payment - mark as pending payment
                            membership.write({'state': 'pending_payment'})
                            _logger.info("Membership set to pending_payment (partial payment)")
                    
                    _logger.info(f"Membership created: {membership.id} with state: {membership.state}, activation_date: {membership.activation_date}")
                    
                    # Deduct popcorn money if used
                    if use_popcorn_money and popcorn_money_to_use > 0:
                        _logger.info(f"Deducting popcorn money: {popcorn_money_to_use}")
                        partner.deduct_popcorn_money(popcorn_money_to_use, f'Membership purchase: {plan.display_name}')
                    
                    # Log the payment request
                    if remaining_amount <= 0:
                        payment_message = _('Membership purchase completed using Popcorn Money. Price: %s%s. Popcorn money used: %s%s. No additional payment required.') % (plan.currency_id.symbol, amount, plan.currency_id.symbol, popcorn_money_to_use)
                    else:
                        payment_message = _('Manual payment requested. Payment method: Manual')
                        if use_popcorn_money and popcorn_money_to_use > 0:
                            payment_message += _('. Popcorn money used: %s%s. Remaining: %s%s') % (plan.currency_id.symbol, popcorn_money_to_use, plan.currency_id.symbol, remaining_amount)
                    
                    membership.message_post(body=payment_message)
                    
                    # Redirect based on payment status
                    if remaining_amount <= 0:
                        return request.redirect('/memberships/success?membership_id=%s&payment_completed=true' % membership.id)
                    else:
                        return request.redirect('/memberships/success?membership_id=%s&payment_pending=true' % membership.id)
            
            # Otherwise, it should be a payment provider ID
            try:
                provider_id = int(payment_method_id)
                
                # Use payment.provider (Odoo 18)
                payment_provider = None
                try:
                    payment_provider = request.env['payment.provider'].browse(provider_id)
                    
                    if not payment_provider or not payment_provider.exists() or payment_provider.state != 'enabled':
                        return request.redirect('/memberships/%s/checkout?error=invalid_payment_method' % plan.id)
                except Exception as e:
                    _logger.error(f"Failed to access payment provider: {str(e)}")
                    return request.redirect('/memberships/%s/checkout?error=payment_access_denied' % plan.id)
                    
            except (ValueError, TypeError):
                return request.redirect('/memberships/%s/checkout?error=invalid_payment_method' % plan.id)
            
            # Check if this is an event purchase
            is_event_purchase = request.params.get('event_purchase') == 'true'
            
            # All data will be stored on the transaction model - no session needed
            # Handle different payment methods based on provider name
            _logger.info(f"Payment provider name: '{payment_provider.name}', lowercase: '{payment_provider.name.lower()}'")
            if payment_provider.name.lower() in ['bank transfer', 'bank_transfer']:
                # For bank transfer, create membership immediately but mark as pending payment
                membership = self._create_membership_from_plan(plan, partner, customer_signature=customer_signature, applied_discount=applied_discount, is_renewal=is_renewal, student_card_attachment_id=student_card_attachment_id, id_card_attachment_id=id_card_attachment_id)
                if not plan.is_student_plan:
                    membership.write({'state': 'pending_payment'})
                
                # Log the bank transfer payment request
                membership.message_post(
                    body=_('Bank transfer payment requested. Payment method: %s') % payment_provider.name
                )
                
                # Redirect to success page with pending payment status
                return request.redirect('/memberships/success?membership_id=%s&payment_pending=true' % membership.id)
            elif payment_provider.name.lower() in ['wechat', 'wechat pay', 'wechatpay']:
                # For WeChat payments, redirect to WeChat OAuth2 flow
                _logger.info(f"Creating WeChat payment transaction for provider: {payment_provider.name}")
                
                # Get or create a default payment method for the provider
                payment_method = request.env['payment.method'].sudo().search([
                    ('provider_ids', 'in', payment_provider.id),
                    ('active', '=', True)
                ], limit=1)
                
                if not payment_method:
                    # Create a default payment method for this provider
                    payment_method = request.env['payment.method'].sudo().create({
                        'name': f'{payment_provider.name} Payment',
                        'code': payment_provider.code.lower().replace(' ', '_'),
                        'provider_ids': [(6, 0, [payment_provider.id])],
                        'active': True,
                    })
                
                # Create payment transaction with unique reference (NO membership created yet)
                import time
                timestamp = int(time.time())
                
                _logger.info(f"Creating WeChat payment transaction - is_upgrade: {is_upgrade}, is_renewal: {is_renewal}, upgrade_details: {upgrade_details}")
                
                # Ensure upgrade and renewal are mutually exclusive
                # If upgrade, renewal must be False
                final_is_upgrade = bool(is_upgrade)
                final_is_renewal = bool(is_renewal) if not final_is_upgrade else False
                
                payment_transaction = request.env['payment.transaction'].sudo().create({
                    'provider_id': payment_provider.id,
                    'payment_method_id': payment_method.id,
                    'amount': remaining_amount,
                    'currency_id': plan.currency_id.id,
                    'partner_id': partner.id,
                    'reference': f'MEMBERSHIP-{plan.id}-{partner.id}-{timestamp}',
                    'state': 'draft',
                    # Store popcorn transaction data directly on transaction
                    'popcorn_transaction_type': 'membership',
                    'membership_plan_id': plan.id,
                    'is_upgrade': final_is_upgrade,
                    'is_renewal': final_is_renewal,
                    'upgrade_details': upgrade_details if final_is_upgrade else None,
                    'use_popcorn_money': use_popcorn_money,
                    'popcorn_money_to_use': popcorn_money_to_use,
                    'remaining_amount': remaining_amount,
                    'applied_discount_id': applied_discount.id if applied_discount else False,
                    'customer_signature': customer_signature,
                    'student_card_attachment_id': student_card_attachment_id,
                    'id_card_attachment_id': id_card_attachment_id,
                })

                _logger.info(f"WeChat payment transaction created with ID: {payment_transaction.id}, "
                           f"plan: {plan.name}, is_upgrade: {payment_transaction.is_upgrade}, "
                           f"is_renewal: {payment_transaction.is_renewal}, upgrade_details: {payment_transaction.upgrade_details}")
                
                # Verify transaction was created with correct flags
                if final_is_upgrade and not payment_transaction.is_upgrade:
                    _logger.error(f"CRITICAL: Transaction {payment_transaction.id} was created with is_upgrade=False but should be True!")
                if final_is_upgrade and payment_transaction.is_renewal:
                    _logger.error(f"CRITICAL: Transaction {payment_transaction.id} has both is_upgrade=True and is_renewal=True!")
                
                # Verify transaction was created with correct flags
                if final_is_upgrade and not payment_transaction.is_upgrade:
                    _logger.error(f"CRITICAL: Transaction {payment_transaction.id} was created with is_upgrade=False but should be True!")
                if final_is_upgrade and payment_transaction.is_renewal:
                    _logger.error(f"CRITICAL: Transaction {payment_transaction.id} has both is_upgrade=True and is_renewal=True!")
                
                # All data is now stored on transaction - no session needed
                # Redirect to WeChat OAuth2 flow
                wechat_oauth_url = f'/payment/wechat/oauth2/authorize?transaction_id={payment_transaction.reference}'
                _logger.info(f"Redirecting to WeChat OAuth2: {wechat_oauth_url}")
                return request.redirect(wechat_oauth_url)
            elif payment_provider.name.lower() in ['alipay']:
                # For Alipay payments, create transaction and redirect to Alipay WAP payment
                _logger.info(f"Creating Alipay payment transaction for provider: {payment_provider.name}")
                
                # Get or create a default payment method for the provider
                payment_method = request.env['payment.method'].sudo().search([
                    ('provider_ids', 'in', payment_provider.id),
                    ('active', '=', True)
                ], limit=1)
                
                if not payment_method:
                    # Create a default payment method for this provider
                    payment_method = request.env['payment.method'].sudo().create({
                        'name': f'{payment_provider.name} Payment',
                        'code': payment_provider.code.lower().replace(' ', '_'),
                        'provider_ids': [(6, 0, [payment_provider.id])],
                        'active': True,
                    })
                
                # Create payment transaction with unique reference (NO membership created yet)
                import time
                timestamp = int(time.time())
                
                # Generate access token for secure return URL
                from odoo.addons.payment import utils as payment_utils
                access_token = payment_utils.generate_access_token(
                    partner.id, remaining_amount, plan.currency_id.id
                )
                
                # Define landing route for Alipay redirect after payment
                landing_route = '/memberships/success'
                
                # Ensure upgrade and renewal are mutually exclusive
                # If upgrade, renewal must be False
                final_is_upgrade = bool(is_upgrade)
                final_is_renewal = bool(is_renewal) if not final_is_upgrade else False
                
                payment_transaction = request.env['payment.transaction'].sudo().create({
                    'provider_id': payment_provider.id,
                    'payment_method_id': payment_method.id,
                    'amount': remaining_amount,
                    'currency_id': plan.currency_id.id,
                    'partner_id': partner.id,
                    'reference': f'MEMBERSHIP-{plan.id}-{partner.id}-{timestamp}',
                    'state': 'draft',
                    # Store popcorn transaction data directly on transaction
                    'popcorn_transaction_type': 'membership',
                    'membership_plan_id': plan.id,
                    'is_upgrade': final_is_upgrade,
                    'is_renewal': final_is_renewal,
                    'upgrade_details': upgrade_details if final_is_upgrade else None,
                    'use_popcorn_money': use_popcorn_money,
                    'popcorn_money_to_use': popcorn_money_to_use,
                    'remaining_amount': remaining_amount,
                    'applied_discount_id': applied_discount.id if applied_discount else False,
                    'customer_signature': customer_signature,
                    'landing_route': landing_route,
                    'student_card_attachment_id': student_card_attachment_id,
                    'id_card_attachment_id': id_card_attachment_id,
                })
                
                # Update landing route with access token for secure redirect
                from odoo.addons.payment.controllers.portal import PaymentPortal
                PaymentPortal._update_landing_route(payment_transaction, access_token)
                
                from odoo.addons.payment.controllers.post_processing import PaymentPostProcessing
                PaymentPostProcessing.monitor_transaction(payment_transaction)
                
                _logger.info(f"Alipay payment transaction created with ID: {payment_transaction.id}")
                _logger.info(f"Pending purchase data stored in transaction for webhook processing")
                
                # Store transaction ID and membership data in session for callback (NO membership created yet)
                request.session['payment_transaction_id'] = payment_transaction.id
                # Get Alipay payment URL using the same method as product purchase (which works)
                try:
                    payment_link = payment_transaction._get_specific_rendering_values(None)
                    if payment_link and 'action_url' in payment_link:
                        alipay_payment_url = payment_link['action_url']
                        _logger.info(f"Got URL from action_url: {alipay_payment_url[:150]}")
                    else:
                        # Fallback to direct payment link method
                        alipay_payment_url = payment_transaction._get_payment_link()
                        _logger.info(f"Got URL from _get_payment_link: {alipay_payment_url[:150] if alipay_payment_url else 'None'}")
                    
                    if alipay_payment_url:
                        # Ensure URL is absolute
                        if not alipay_payment_url.startswith('http://') and not alipay_payment_url.startswith('https://'):
                            _logger.error(f"Payment URL is not absolute: {alipay_payment_url}")
                            # Fix relative URL
                            if alipay_payment_url.startswith('/gateway.do') or alipay_payment_url.startswith('gateway.do'):
                                provider = payment_transaction.provider_id
                                gateway_base = 'https://openapi-sandbox.dl.alipaydev.com' if provider.alipay_sandbox else 'https://openapi.alipay.com'
                                if '?' in alipay_payment_url:
                                    query_params = alipay_payment_url.split('?', 1)[1]
                                    alipay_payment_url = f"{gateway_base}/gateway.do?{query_params}"
                                else:
                                    alipay_payment_url = f"{gateway_base}/gateway.do"

                        # WeChat browser blocks Alipay URLs — show copy-link page instead
                        user_agent = request.httprequest.headers.get('User-Agent', '')
                        if 'MicroMessenger' in user_agent:
                            _logger.info(f"WeChat browser detected — redirecting to Alipay copy-link page for: {payment_transaction.reference}")
                            return request.redirect(f'/payment/alipay/wechat_redirect?ref={payment_transaction.reference}')

                        _logger.info(f"Redirecting to Alipay payment URL: {alipay_payment_url[:100]}...")
                        return redirect(alipay_payment_url, code=302)
                except Exception as e:
                    _logger.error(f"Failed to get Alipay payment URL: {str(e)}", exc_info=True)
                
                # If we get here, payment URL generation failed
                _logger.error("Failed to get Alipay payment URL - no action_url or payment_link available")
                request.session.pop('pending_membership', None)
                return request.redirect('/memberships/payment/failed?error=gateway_unavailable')
            else:
                # For all other online payments (Stripe/PayPal/etc), create payment transaction and redirect to gateway
                _logger.info(f"Creating payment transaction for provider: {payment_provider.name}")
                
                # Get or create a default payment method for the provider
                payment_method = request.env['payment.method'].sudo().search([
                    ('provider_ids', 'in', payment_provider.id),
                    ('active', '=', True)
                ], limit=1)
                
                if not payment_method:
                    # Create a default payment method for this provider
                    payment_method = request.env['payment.method'].sudo().create({
                        'name': f'{payment_provider.name} Payment',
                        'code': payment_provider.code.lower().replace(' ', '_'),
                        'provider_ids': [(6, 0, [payment_provider.id])],
                        'active': True,
                    })
                
                # Create payment transaction with unique reference (NO membership created yet)
                import time
                timestamp = int(time.time())
                
                # Ensure upgrade and renewal are mutually exclusive
                # If upgrade, renewal must be False
                final_is_upgrade = bool(is_upgrade)
                final_is_renewal = bool(is_renewal) if not final_is_upgrade else False
                
                payment_transaction = request.env['payment.transaction'].sudo().create({
                    'provider_id': payment_provider.id,
                    'payment_method_id': payment_method.id,
                    'amount': remaining_amount,
                    'currency_id': plan.currency_id.id,
                    'partner_id': partner.id,
                    'reference': f'MEMBERSHIP-{plan.id}-{partner.id}-{timestamp}',
                    'state': 'draft',
                    # Store popcorn transaction data directly on transaction
                    'popcorn_transaction_type': 'membership',
                    'membership_plan_id': plan.id,
                    'is_upgrade': final_is_upgrade,
                    'is_renewal': final_is_renewal,
                    'upgrade_details': upgrade_details if final_is_upgrade else None,
                    'use_popcorn_money': use_popcorn_money,
                    'popcorn_money_to_use': popcorn_money_to_use,
                    'remaining_amount': remaining_amount,
                    'applied_discount_id': applied_discount.id if applied_discount else False,
                    'customer_signature': customer_signature,
                    'student_card_attachment_id': student_card_attachment_id,
                    'id_card_attachment_id': id_card_attachment_id,
                })

                _logger.info(f"Payment transaction created with ID: {payment_transaction.id}, "
                           f"plan: {plan.name}, signature provided: {bool(customer_signature)}")
                
                # Store transaction ID and membership data in session for callback (NO membership created yet)
                request.session['payment_transaction_id'] = payment_transaction.id
                # Let the payment gateway handle the payment flow
                try:
                    payment_link = payment_transaction._get_specific_rendering_values(None)
                    if payment_link and 'action_url' in payment_link:
                        _logger.info(f"Redirecting to payment gateway: {payment_link['action_url']}")
                        return request.redirect(payment_link['action_url'])
                except Exception as e:
                    _logger.warning(f"Failed to get payment link: {str(e)}")
                
                # Fallback: if no payment link available, redirect to payment failed page
                    _logger.warning("No payment link available, redirecting to payment failed page")
                    return request.redirect('/memberships/payment/failed?error=gateway_unavailable')
            
        except Exception as e:
            _logger.error(f"Failed to process checkout: {str(e)}", exc_info=True)
            return request.redirect('/memberships/%s/checkout?error=processing_failed' % plan.id)
    
    @http.route(['/memberships/payment/process'], type='http', auth="public", website=True, methods=['GET', 'POST'])
    def membership_payment_process(self, **post):
        """Process payment simulation and create membership upon successful payment"""
        try:
            # Get payment method and details from URL parameters
            payment_method = request.params.get('method')
            plan_id = request.params.get('plan_id')
            amount = request.params.get('amount')
            
            if not payment_method or not plan_id:
                return request.redirect('/memberships?error=payment_failed')
            
            # Get pending membership details from session
            pending_membership = request.session.get('pending_membership')
            if not pending_membership:
                return request.redirect('/memberships?error=session_expired')
            
            # Get the plan and partner
            plan = request.env['popcorn.membership.plan'].browse(int(plan_id))
            partner = request.env['res.partner'].browse(pending_membership['partner_id'])
            
            if not plan.exists() or not partner.exists():
                return request.redirect('/memberships?error=invalid_data')
            
            # Get the payment provider
            payment_provider = None
            try:
                payment_provider = request.env['payment.provider'].browse(pending_membership['payment_provider_id'])
                
                if not payment_provider or not payment_provider.exists():
                    return request.redirect('/memberships?error=payment_provider_not_found')
            except Exception as e:
                _logger.error(f"Failed to access payment provider in processing: {str(e)}")
                # Use fallback provider name from session
                payment_provider = type('obj', (object,), {'name': pending_membership.get('payment_provider_name', 'Unknown Provider')})
            
            # Create actual payment transaction
            _logger.info(f"Creating payment transaction for provider: {payment_provider.name}")
            
            # Get or create a default payment method for the provider
            payment_method = request.env['payment.method'].sudo().search([
                ('provider_ids', 'in', payment_provider.id),
                ('active', '=', True)
            ], limit=1)
            
            if not payment_method:
                # Create a default payment method for this provider
                payment_method = request.env['payment.method'].sudo().create({
                    'name': f'{payment_provider.name} Payment',
                    'code': payment_provider.code.lower().replace(' ', '_'),
                    'provider_ids': [(6, 0, [payment_provider.id])],
                    'active': True,
                })
            
            # Create payment transaction with unique reference
            import time
            timestamp = int(time.time())
            
            # Ensure upgrade and renewal are mutually exclusive
            # If upgrade, renewal must be False
            pending_is_upgrade = bool(pending_membership.get('is_upgrade', False))
            pending_is_renewal = bool(pending_membership.get('is_renewal', False))
            final_is_upgrade = pending_is_upgrade
            final_is_renewal = pending_is_renewal if not final_is_upgrade else False
            
            payment_transaction = request.env['payment.transaction'].sudo().create({
                'provider_id': payment_provider.id,
                'payment_method_id': payment_method.id,
                'amount': amount,
                'currency_id': plan.currency_id.id,
                'partner_id': partner.id,
                'reference': f'MEMBERSHIP-{plan.id}-{partner.id}-{timestamp}',
                'state': 'draft',
                # Store popcorn transaction data directly on transaction
                'popcorn_transaction_type': 'membership',
                'membership_plan_id': plan.id,
                'is_upgrade': final_is_upgrade,
                'is_renewal': final_is_renewal,
                'upgrade_details': pending_membership.get('upgrade_details') if final_is_upgrade else None,
                'use_popcorn_money': pending_membership.get('use_popcorn_money', False),
                'popcorn_money_to_use': pending_membership.get('popcorn_money_to_use', 0),
                'remaining_amount': amount,
                'applied_discount_id': pending_membership.get('applied_discount_id') or False,
                'customer_signature': pending_membership.get('customer_signature'),
            })
            
            _logger.info(f"Payment transaction created with ID: {payment_transaction.id}, "
                       f"plan: {plan.name}, signature provided: {bool(pending_membership.get('customer_signature'))}")
            
            # Generate payment link and redirect to actual payment gateway
            payment_link = payment_transaction._get_specific_rendering_values(None)
            
            if payment_link and 'action_url' in payment_link:
                # Store transaction ID in session for callback
                request.session['payment_transaction_id'] = payment_transaction.id
                request.session['pending_membership'] = pending_membership  # Keep membership data
                
                _logger.info(f"Redirecting to payment gateway: {payment_link['action_url']}")
                return request.redirect(payment_link['action_url'])
            else:
                # Fallback: create membership directly if no payment link available
                _logger.warning("No payment link available, creating membership directly")
                
                # Create the membership
                # Upgrade takes precedence over renewal
                if pending_membership.get('is_upgrade', False):
                    # Handle upgrade
                    applied_discount = None
                    applied_discount_id = pending_membership.get('applied_discount_id')
                    if applied_discount_id:
                        try:
                            applied_discount = request.env['popcorn.discount'].browse(int(applied_discount_id))
                            if not applied_discount.exists() or not applied_discount._is_currently_valid():
                                applied_discount = None
                        except (ValueError, TypeError):
                            applied_discount = None
                    
                    # Calculate actual payment amount (upgrade_price - popcorn_money)
                    upgrade_details_from_session = pending_membership['upgrade_details']
                    upgrade_price = upgrade_details_from_session.get('upgrade_price', 0) if upgrade_details_from_session else 0
                    popcorn_money_used = pending_membership.get('popcorn_money_to_use', 0) or 0
                    actual_payment_amount = max(0, amount - popcorn_money_used)  # amount already accounts for discounts
                    
                    membership = self._create_upgrade_membership(
                        plan, 
                        partner, 
                        upgrade_details_from_session,
                        payment_transaction_id=None,
                        payment_reference=None,
                        applied_discount=applied_discount,
                        actual_payment_amount=actual_payment_amount
                    )
                    _logger.info(f"Upgrade membership created with ID: {membership.id}")
                    
                    
                    # Log the upgrade
                    membership.message_post(
                        body=_('Membership upgraded through %s payment. Amount: %s') % (payment_provider.name, amount)
                    )
                    
                    # Clear pending membership from session
                    request.session.pop('pending_membership', None)
                    
                    _logger.info(f"Redirecting to upgrade success page: /my/cards/upgrade/success?membership_id={membership.id}")
                    # Redirect to upgrade success page
                    return request.redirect('/my/cards/upgrade/success?membership_id=%s' % membership.id)
                elif pending_membership.get('is_renewal', False):
                    # Handle renewal
                    applied_discount = None
                    applied_discount_id = pending_membership.get('applied_discount_id')
                    if applied_discount_id:
                        try:
                            applied_discount = request.env['popcorn.discount'].browse(int(applied_discount_id))
                            if not applied_discount.exists() or not applied_discount._is_currently_valid():
                                applied_discount = None
                        except (ValueError, TypeError):
                            applied_discount = None
                    
                    membership = self._create_membership_from_plan(
                        plan, 
                        partner, 
                        customer_signature=pending_membership.get('customer_signature'),
                        applied_discount=applied_discount,
                        is_renewal=True
                    )
                    _logger.info(f"Renewal membership created with ID: {membership.id}")
                    
                    # Clear upgrade details from session if renewal takes precedence
                    
                    # Log the renewal
                    membership.message_post(
                        body=_('Membership renewed through %s payment. Amount: %s') % (payment_provider.name, amount)
                    )
                else:
                    # Get applied discount if any
                    applied_discount = None
                    applied_discount_id = pending_membership.get('applied_discount_id')
                    if applied_discount_id:
                        try:
                            applied_discount = request.env['popcorn.discount'].browse(int(applied_discount_id))
                            if not applied_discount.exists() or not applied_discount._is_currently_valid():
                                applied_discount = None
                        except (ValueError, TypeError):
                            applied_discount = None
                    
                    # Create regular membership
                    membership = self._create_membership_from_plan(
                        plan, 
                        partner, 
                        customer_signature=pending_membership.get('customer_signature'),
                        applied_discount=applied_discount,
                        is_renewal=pending_membership.get('is_renewal', False)
                    )
                    _logger.info(f"Regular membership created with ID: {membership.id}")
                    
                    # Log the purchase
                    membership.message_post(
                        body=_('Membership purchased through %s payment. Amount: %s') % (payment_provider.name, amount)
                    )
                    
                    # Clear pending membership from session
                    request.session.pop('pending_membership', None)
                    
                    _logger.info(f"Redirecting to success page: /memberships/success?membership_id={membership.id}")
                    # Redirect to success page
                    return request.redirect('/memberships/success?membership_id=%s' % membership.id)
                
        except Exception as e:
            _logger.error(f"Failed to process payment: {str(e)}")
            # Clear session data on error
            request.session.pop('pending_membership', None)
            return request.redirect('/memberships?error=payment_processing_failed')

    @http.route(['/memberships/payment/callback'], type='http', auth="public", website=True, methods=['GET', 'POST'])
    def membership_payment_callback(self, **post):
        """Handle payment callback from payment gateway"""
        try:
            # Check if this is a WeChat payment success redirect (from JavaScript)
            payment_success = post.get('payment_success')
            transaction_id_param = post.get('transaction_id')
            
            if payment_success == 'true' and transaction_id_param:
                # This is a WeChat payment success redirect from JavaScript
                _logger.info(f"WeChat payment success redirect for transaction: {transaction_id_param}")
                
                # Check transaction ID prefix to determine payment type (not session data)
                # Event: EVENT-{event.id}-{partner.id}-{timestamp}
                # Membership: MEMBERSHIP-{plan.id}-{partner.id}-{timestamp}
                if transaction_id_param.startswith('EVENT-'):
                    _logger.info("Event purchase redirect detected (transaction ID prefix), redirecting to event purchase success handler")
                    return self._handle_event_purchase_redirect(transaction_id_param)
                
                # Get the transaction (try by ID first, then by reference)
                transaction = None
                try:
                    transaction = request.env['payment.transaction'].sudo().browse(int(transaction_id_param))
                    if not transaction.exists():
                        transaction = None
                except (ValueError, TypeError):
                    pass
                
                if not transaction or not transaction.exists():
                    transaction = request.env['payment.transaction'].sudo().search([
                        ('reference', '=', transaction_id_param),
                        ('provider_code', '=', 'wechat')
                    ], limit=1)
                
                if not transaction or not transaction.exists():
                    _logger.error(f"Transaction {transaction_id_param} not found")
                    return request.redirect('/memberships/payment/failed?error=transaction_not_found')
                
                # Check if membership already exists for this transaction (backend polling may have created it)
                existing_membership = request.env['popcorn.membership'].sudo().search([
                    ('payment_transaction_id', '=', transaction.id)
                ], limit=1)
                
                if existing_membership:
                    _logger.info(f"Membership {existing_membership.id} already exists for transaction {transaction.reference}, "
                               f"skipping creation (likely created by backend polling)")
                    redirect_url = '/memberships/success?membership_id=%s' % existing_membership.id
                    return request.redirect(redirect_url)
                
                # Mark transaction as done if not already done (backend polling may have done this)
                # This will trigger backend auto-creation of membership via write() override
                if transaction.state != 'done':
                    # Write will trigger our override which creates membership synchronously
                    transaction.write({'state': 'done'})
                
                # Refresh transaction to see if membership was created by backend
                transaction.invalidate_recordset(['popcorn_processed'])
                
                # Check if membership was created by backend (write() override creates it synchronously)
                existing_membership = request.env['popcorn.membership'].sudo().search([
                    ('payment_transaction_id', '=', transaction.id)
                ], limit=1)
                
                if existing_membership:
                    _logger.info(f"Membership {existing_membership.id} created by backend for transaction {transaction.reference}")
                    redirect_url = '/memberships/success?membership_id=%s' % existing_membership.id
                    return request.redirect(redirect_url)
                
                # If still no membership after backend processing, log warning and redirect
                _logger.warning(f"No membership found after marking transaction {transaction.reference} as done. "
                              f"Backend should have created it. Redirecting to membership page...")
                
                # Redirect to membership page - backend will create membership soon
                return request.redirect('/memberships?warning=processing')
            
            # Original callback logic for other payment gateways
            # Get transaction ID from params or session (fallback)
            transaction_id = request.params.get('transaction_id') or request.session.get('payment_transaction_id')
            
            if not transaction_id:
                _logger.error("No transaction ID found")
                return request.redirect('/memberships/payment/failed?error=transaction_not_found')
            
            # Get the transaction - all data is stored on the transaction model
            transaction = request.env['payment.transaction'].sudo().browse(int(transaction_id))
            
            if not transaction.exists():
                _logger.error(f"Transaction {transaction_id} not found")
                return request.redirect('/memberships/payment/failed?error=transaction_not_found')
            
            # Check payment status
            if transaction.state == 'done':
                # Transaction processing is handled by _process_membership_transaction() via write()/_set_done()
                # Just find the created membership and redirect
                membership = request.env['popcorn.membership'].search([
                    ('payment_transaction_id', '=', transaction.id)
                ], limit=1)
                
                if not membership:
                    _logger.error(f"No membership found for transaction {transaction_id}")
                    return request.redirect('/memberships/payment/failed?error=membership_not_created')
                
                # Redirect based on transaction type
                if transaction.is_upgrade:
                    redirect_url = '/my/cards/upgrade/success?membership_id=%s' % membership.id
                else:
                    redirect_url = '/memberships/success?membership_id=%s' % membership.id
                
                _logger.info(f"Payment successful. Membership ID: {membership.id}")
                return request.redirect(redirect_url)
                
            elif transaction.state == 'cancel':
                # Payment cancelled
                _logger.info(f"Payment cancelled for transaction {transaction_id}")
                return request.redirect('/memberships/payment/failed?error=payment_cancelled')
                
            else:
                # Payment pending or failed - no membership created
                _logger.warning(f"Payment not completed for transaction {transaction_id}. State: {transaction.state}")
                return request.redirect('/memberships/payment/failed?error=payment_failed')
                
        except Exception as e:
            _logger.error(f"Failed to handle payment callback: {str(e)}")
            return request.redirect('/memberships/payment/failed?error=callback_failed')

    def _find_membership_by_transaction_reference(self, transaction_reference):
        """Find membership by transaction reference"""
        try:
            # Parse transaction reference: MEMBERSHIP-{plan_id}-{partner_id}-{timestamp}
            if not transaction_reference.startswith('MEMBERSHIP-'):
                return None
            
            parts = transaction_reference.split('-')
            if len(parts) < 3:
                return None
            
            partner_id = int(parts[2])
            
            # Find pending membership for this partner
            membership = request.env['popcorn.membership'].sudo().search([
                ('partner_id', '=', partner_id),
                ('state', '=', 'pending_payment'),
                ('purchase_channel', '=', 'online')
            ], order='create_date desc', limit=1)
            
            return membership
            
        except (ValueError, IndexError) as e:
            _logger.error("Failed to parse transaction reference %s: %s", transaction_reference, str(e))
            return None
        except Exception as e:
            _logger.error("Failed to find membership for transaction %s: %s", transaction_reference, str(e))
            return None

    @http.route(['/memberships/<model("popcorn.membership.plan"):plan>/purchase'], type='http', auth="public", website=True)
    def membership_purchase(self, plan, **post):
        """Handle membership purchase"""
        # Check if user is logged in (public user means not logged in)
        if request.env.user.id == request.env.ref('base.public_user').id:
            return request.redirect('/web/login?redirect=' + request.httprequest.url)
        
        if request.httprequest.method == 'POST':
            # Handle the purchase
            try:
                # Create a direct membership purchase
                membership = self._create_membership_from_plan(plan, request.env.user.partner_id)
                
                # Redirect to success page
                return request.redirect('/memberships/success')
                
            except Exception as e:
                _logger.error(f"Failed to create membership: {str(e)}")
                return request.redirect('/memberships/error')
        
        # Display purchase form
        values = {
            'plan': plan,
        }
        
        return request.render('popcorn.membership_purchase_page', values)
    
    @http.route(['/memberships/success'], type='http', auth="public", website=True)
    def membership_success(self, **post):
        """Display success page after membership purchase"""
        # Check if user is logged in (public user means not logged in)
        if request.env.user.id == request.env.ref('base.public_user').id:
            return request.redirect('/web/login?redirect=' + request.httprequest.url)
        
        # Check if this is an event purchase redirect (determined by transaction ID prefix, not session data)
        payment_success = post.get('payment_success')
        transaction_id_param = post.get('transaction_id')
        
        # Check transaction ID prefix to determine payment type
        # Event: EVENT-{event.id}-{partner.id}-{timestamp}
        # Membership: MEMBERSHIP-{plan.id}-{partner.id}-{timestamp}
        if payment_success == 'true' and transaction_id_param and transaction_id_param.startswith('EVENT-'):
            _logger.info(f"Event purchase redirect detected in membership success route (transaction ID: {transaction_id_param}), redirecting to event handler")
            return self._handle_event_purchase_redirect(transaction_id_param)
        
        membership_id = post.get('membership_id')
        membership = None
        
        # Handle WeChat payment success redirect
        if payment_success == 'true' and transaction_id_param:
            _logger.info(f"=== WeChat payment success redirect ===")
            _logger.info(f"Transaction ID: {transaction_id_param}")
            
            # Get the transaction (all data is stored on transaction, not session)
            transaction = None
            _logger.info(f"Looking for transaction with ID/reference: {transaction_id_param}")
            
            try:
                # First try as integer ID
                transaction = request.env['payment.transaction'].sudo().browse(int(transaction_id_param))
                _logger.info(f"Tried as integer ID, found: {transaction.exists() if transaction else False}")
                if not transaction.exists():
                    transaction = None
            except (ValueError, TypeError) as e:
                _logger.info(f"Failed to parse as integer ID: {e}")
                pass
            
            # If not found as ID, try as reference
            if not transaction or not transaction.exists():
                _logger.info(f"Trying to find by reference: {transaction_id_param}")
                transaction = request.env['payment.transaction'].sudo().search([
                    ('reference', '=', transaction_id_param)
                ], limit=1)
                _logger.info(f"Found by reference: {transaction.exists() if transaction else False}")
            
            if not transaction or not transaction.exists():
                _logger.error(f"Transaction {transaction_id_param} not found")
                return request.redirect('/memberships/payment/failed?error=transaction_not_found')
            
            _logger.info(f"Found transaction: {transaction.id}, State: {transaction.state}, Provider: {transaction.provider_id.name if transaction.provider_id else 'None'}")
            
            # IMPORTANT: Do NOT create membership here - backend polling/webhook handles it
            # The frontend should only check status and display confirmation screen
            
            # Check if membership already exists (backend polling may have created it)
            existing_membership = request.env['popcorn.membership'].sudo().search([
                ('payment_transaction_id', '=', transaction.id)
            ], limit=1)
            
            if existing_membership:
                _logger.info(f"Membership {existing_membership.id} already exists for transaction {transaction.reference}, "
                           f"showing success page (created by backend polling)")
                # Show success page with existing membership
                membership = existing_membership
            else:
                # Membership doesn't exist yet - backend polling is still processing
                # Mark transaction as 'done' if not already (triggers backend processing)
                if transaction.state != 'done':
                    _logger.info(f"Transaction {transaction.reference} not yet 'done', marking as done to trigger backend processing")
                    transaction.write({'state': 'done'})
                    # Invalidate to read latest state
                    transaction.invalidate_recordset(['popcorn_processed', 'state'])
                
                # Re-check for membership after triggering backend processing
                existing_membership = request.env['popcorn.membership'].sudo().search([
                    ('payment_transaction_id', '=', transaction.id)
                ], limit=1)
                
                if existing_membership:
                    _logger.info(f"Membership {existing_membership.id} created by backend, showing success page")
                    membership = existing_membership
                else:
                    _logger.info(f"Payment successful for transaction {transaction.reference}, but membership not yet created. "
                               f"Showing processing screen - backend polling will create membership.")
                    # Show processing page that will poll for membership status
                    values = {
                        'membership': None,
                        'transaction': transaction,
                        'transaction_id': transaction.reference,
                        'processing': True,  # Flag to enable client-side polling in template
                    }
                    return request.render('popcorn.membership_success_page', values)
        
        # Regular success page handling
        if membership_id:
            membership = request.env['popcorn.membership'].browse(int(membership_id))
        
        values = {
            'membership': membership,
        }
        
        return request.render('popcorn.membership_success_page', values)
    
    @http.route(['/memberships/wechat/success'], type='http', auth="public", website=True)
    def wechat_membership_success(self, **post):
        """Handle WeChat payment success and create membership"""
        # Check if user is logged in (public user means not logged in)
        if request.env.user.id == request.env.ref('base.public_user').id:
            return request.redirect('/web/login?redirect=' + request.httprequest.url)
        
        try:
            transaction_id_param = post.get('transaction_id')
            _logger.info(f"=== WeChat membership success route called ===")
            _logger.info(f"Transaction ID: {transaction_id_param}")
            
            if not transaction_id_param:
                _logger.error("WeChat membership success failed - Transaction ID required")
                return request.redirect('/memberships/payment/failed?error=transaction_id_required')
            
            # Get the transaction (all data is stored on transaction, not session)
            transaction = None
            _logger.info(f"Looking for transaction with ID/reference: {transaction_id_param}")
            
            try:
                # First try as integer ID
                transaction = request.env['payment.transaction'].sudo().browse(int(transaction_id_param))
                _logger.info(f"Tried as integer ID, found: {transaction.exists() if transaction else False}")
                if not transaction.exists():
                    transaction = None
            except (ValueError, TypeError) as e:
                _logger.info(f"Failed to parse as integer ID: {e}")
                pass
            
            # If not found as ID, try as reference
            if not transaction or not transaction.exists():
                _logger.info(f"Trying to find by reference: {transaction_id_param}")
                transaction = request.env['payment.transaction'].sudo().search([
                    ('reference', '=', transaction_id_param)
                ], limit=1)
                _logger.info(f"Found by reference: {transaction.exists() if transaction else False}")
            
            if not transaction or not transaction.exists():
                _logger.error(f"Transaction {transaction_id_param} not found")
                return request.redirect('/memberships/payment/failed?error=transaction_not_found')
            
            _logger.info(f"Found transaction: {transaction.id}, State: {transaction.state}, Provider: {transaction.provider_id.name if transaction.provider_id else 'None'}")
            
            # IMPORTANT: Do NOT create membership here - backend polling/webhook handles it
            # The frontend should only check status and display confirmation screen
            
            # Check if membership already exists (backend polling may have created it)
            existing_membership = request.env['popcorn.membership'].sudo().search([
                ('payment_transaction_id', '=', transaction.id)
            ], limit=1)
            
            if existing_membership:
                _logger.info(f"Membership {existing_membership.id} already exists for transaction {transaction.reference}, "
                           f"redirecting to success page (created by backend polling)")
                # Redirect to membership success page with membership_id
                redirect_url = '/memberships/success?membership_id=%s' % existing_membership.id
                _logger.info(f"Redirecting to: {redirect_url}")
                return request.redirect(redirect_url)
            
            # Membership doesn't exist yet - backend polling is still processing
            # Mark transaction as 'done' if not already (triggers backend processing)
            if transaction.state != 'done':
                _logger.info(f"Transaction {transaction.reference} not yet 'done', marking as done to trigger backend processing")
                transaction.write({'state': 'done'})
                # Invalidate to read latest state
                transaction.invalidate_recordset(['popcorn_processed', 'state'])
            
            # Re-check for membership after triggering backend processing
            existing_membership = request.env['popcorn.membership'].sudo().search([
                ('payment_transaction_id', '=', transaction.id)
            ], limit=1)
            
            if existing_membership:
                _logger.info(f"Membership {existing_membership.id} created by backend, redirecting to success page")
                redirect_url = '/memberships/success?membership_id=%s' % existing_membership.id
                _logger.info(f"Redirecting to: {redirect_url}")
                return request.redirect(redirect_url)
            
            # Still no membership - backend is processing, redirect to success page with processing flag
            _logger.info(f"Payment successful for transaction {transaction.reference}, but membership not yet created. "
                       f"Redirecting to success page - backend polling will create membership.")
            redirect_url = '/memberships/success?payment_success=true&transaction_id=%s&processing=true' % transaction.reference
            return request.redirect(redirect_url)
            
        except Exception as e:
            _logger.error(f"Failed to handle WeChat membership success: {str(e)}", exc_info=True)
            _logger.error(f"Exception type: {type(e).__name__}")
            return request.redirect('/memberships/payment/failed?error=processing_failed')
    
    @http.route(['/memberships/payment/failed'], type='http', auth="public", website=True)
    def membership_payment_failed(self, **post):
        """Display payment failed page"""
        # Check if user is logged in (public user means not logged in)
        if request.env.user.id == request.env.ref('base.public_user').id:
            return request.redirect('/web/login?redirect=' + request.httprequest.url)
        
        # Get error message from URL parameter
        error_message = post.get('error', '')
        
        # Map error codes to user-friendly messages
        error_messages = {
            'session_expired': 'Your payment session has expired. Please try again.',
            'transaction_not_found': 'Payment transaction not found. Please contact support.',
            'payment_cancelled': 'Payment was cancelled. No membership was created.',
            'payment_failed': 'Payment failed. No membership was created.',
            'gateway_unavailable': 'Payment gateway is currently unavailable. Please try again later.',
            'callback_failed': 'Payment processing failed. Please contact support.',
        }
        
        user_message = error_messages.get(error_message, 'Payment failed. Please try again.')
        
        values = {
            'error_message': user_message,
            'error_code': error_message,
        }
        
        return request.render('popcorn.membership_payment_failed_page', values)
    
    def _create_upgrade_membership(self, plan, partner, upgrade_details, payment_transaction_id=None, payment_reference=None, applied_discount=None, actual_payment_amount=None):
        """Upgrade an existing membership to a new plan
        
        Args:
            plan: Target membership plan
            partner: Partner record
            upgrade_details: Dictionary with upgrade information (membership_id, upgrade_price, etc.)
            payment_transaction_id: Optional payment transaction ID
            payment_reference: Optional payment reference
            applied_discount: Optional discount record
            actual_payment_amount: Actual money paid for upgrade (excludes popcorn money)
                If not provided, defaults to upgrade_price (for backward compatibility)
        """
        membership_id = upgrade_details.get('membership_id')
        upgrade_price = upgrade_details.get('upgrade_price', 0)
        
        # Use actual payment amount if provided, otherwise fall back to upgrade_price
        # This ensures purchase_price_paid only reflects real money paid, not popcorn money
        payment_amount_for_purchase_price = actual_payment_amount if actual_payment_amount is not None else upgrade_price
        
        # Get the original membership
        original_membership = request.env['popcorn.membership'].browse(int(membership_id))
        
        # Use model method to upgrade
        # Pass actual payment amount so purchase_price_paid only reflects real money
        upgraded_membership = original_membership.action_upgrade_to_plan(
            plan,
            payment_amount_for_purchase_price,  # Use actual money paid, not full upgrade_price
            payment_transaction_id=payment_transaction_id,
            payment_reference=payment_reference,
            applied_discount=applied_discount
        )
        
        return upgraded_membership
    
    def _create_membership_from_plan(self, plan, partner, purchase_channel='online', price_tier=None, upgrade_discount_allowed=False, first_timer_customer=False, payment_transaction_id=None, payment_reference=None, customer_signature=None, applied_discount=None, is_renewal=False, student_card_attachment_id=None, id_card_attachment_id=None):
        """Create a membership directly from a plan (bypassing sales orders)"""
        # Determine price tier if not provided
        if price_tier is None:
            if is_renewal:
                # For renewals, use first-timer price as base
                price_tier = 'first_timer'
            else:
                price_tier = 'first_timer'
                existing_memberships = request.env['popcorn.membership'].search([
                    ('partner_id', '=', partner.id),
                    ('state', 'in', ['active', 'frozen'])
                ], limit=1)
                
                if existing_memberships:
                    price_tier = 'normal'
        
        # Determine purchase price
        # For renewals, always use first-timer price as base (even if customer has existing memberships)
        if is_renewal:
            purchase_price = plan.price_first_timer if plan.price_first_timer > 0 else plan.price_normal
        elif price_tier == 'first_timer' and plan.price_first_timer > 0:
            purchase_price = plan.price_first_timer
        else:
            purchase_price = plan.price_normal
        
        # First-timer and renewal pricing are exclusive — no additional discounts stack
        if is_renewal or partner.is_first_timer:
            best_price = purchase_price
            best_discount = None
            extra_days = 0
        elif applied_discount:
            _logger.info(f"Using applied discount: {applied_discount.name} (Code: {applied_discount.code}, ID: {applied_discount.id})")
            best_price = applied_discount.get_discounted_price(plan, purchase_price, partner)
            best_discount = applied_discount
            extra_days = applied_discount.get_extra_days(plan, partner)
        else:
            best_price, best_discount, extra_days = plan.get_best_discount_with_extra_days(partner, original_price=purchase_price)
        
        # Create membership values
        membership_vals = {
            'partner_id': partner.id,
            'membership_plan_id': plan.id,
            'state': 'pending',
            'purchase_price_paid': best_price,
            'price_tier': 'discount' if best_discount else price_tier,
            'purchase_channel': purchase_channel,
            'upgrade_discount_allowed': upgrade_discount_allowed,
            'first_timer_customer': first_timer_customer,
            'applied_discount_id': best_discount.id if best_discount else False,
            'extra_days_extension': extra_days,
        }
        
        # Add payment information if provided
        if payment_transaction_id:
            membership_vals['payment_transaction_id'] = payment_transaction_id
        if payment_reference:
            membership_vals['payment_reference'] = payment_reference
        
        # Set activation date based on plan policy (default behavior)
        if plan.activation_policy == 'immediate':
            membership_vals['activation_date'] = fields.Date.today()
            membership_vals['state'] = 'active'
        elif plan.activation_policy == 'first_attendance':
            membership_vals['state'] = 'pending'
        elif plan.activation_policy == 'manual':
            membership_vals['state'] = 'pending'

        # Student plans always override to pending_student_verification
        if plan.is_student_plan:
            membership_vals.pop('activation_date', None)
            membership_vals['state'] = 'pending_student_verification'

        # Buy-Together deferred activation handling - determine state before creating record
        prev_usage_count = None

        # Create the membership
        membership = request.env['popcorn.membership'].create(membership_vals)
        
        # Create discount usage record if discount was applied
        if best_discount:
            request.env['popcorn.discount.usage'].create_usage_record(
                discount_id=best_discount.id,
                partner_id=partner.id,
                original_price=purchase_price,
                discounted_price=best_price,
                currency_id=plan.currency_id.id,
                membership_plan_id=plan.id,
                membership_id=membership.id,
                extra_days=extra_days
            )
        
        # Increment discount usage if a discount was applied
        if best_discount:
            try:
                _logger.info(f"Incrementing usage for discount: {best_discount.code} (ID: {best_discount.id})")
                _logger.info(f"Usage count before: {best_discount.usage_count}, limit: {best_discount.usage_limit}")
                best_discount.action_increment_usage()
                _logger.info(f"Usage count after: {best_discount.usage_count}")
            except Exception as e:
                _logger.error(f"Failed to increment discount usage: {e}", exc_info=True)
                # Don't fail the membership creation if discount increment fails

        # Buy-together by discount removed
        
        # Create contract with signature if provided
        if customer_signature:
            contract_vals = {
                'membership_id': membership.id,
                'contract_type': 'standard',
                'state': 'draft',
                'customer_signature': customer_signature,
                'customer_signature_date': fields.Datetime.now(),
                'signed_by_customer': True,
            }
            contract = request.env['popcorn.contract'].sudo().create(contract_vals)
            membership.write({'contract_id': contract.id})
            membership.message_post(body=_('Contract created and signed by customer during checkout'))

        # Link student card and ID card attachments if present
        if plan.is_student_plan:
            for att_id, field in [
                (student_card_attachment_id, 'student_card_attachment_id'),
                (id_card_attachment_id, 'id_card_attachment_id'),
            ]:
                if att_id:
                    try:
                        attachment = request.env['ir.attachment'].sudo().browse(att_id)
                        if attachment.exists():
                            attachment.write({'res_id': membership.id})
                            membership.write({field: attachment.id})
                    except Exception as e:
                        _logger.error(f"Failed to link attachment {field}: {str(e)}")
            if student_card_attachment_id or id_card_attachment_id:
                membership.message_post(body=_('Student card and/or ID card uploaded. Awaiting staff verification before activation.'))

        # Log the creation
        membership.message_post(
            body=_('Membership created directly from plan %s') % plan.name
        )

        if plan.is_student_plan:
            membership.message_post(
                body=_('Student membership requires staff verification. Please review the uploaded student card and activate manually.')
            )
        elif plan.activation_policy == 'immediate':
            membership.message_post(
                body=_('Membership automatically activated upon purchase')
            )
        elif plan.activation_policy == 'first_attendance':
            membership.message_post(
                body=_('Membership will be activated upon first event attendance')
            )
        elif plan.activation_policy == 'manual':
            membership.message_post(
                body=_('Membership requires manual activation by staff')
            )

        return membership
    
    def _handle_event_purchase_redirect(self, transaction_id_param):
        """Handle WeChat payment success redirect for event purchases"""
        try:
            _logger.info(f"=== _handle_event_purchase_redirect called ===")
            _logger.info(f"Transaction ID: {transaction_id_param}")
            _logger.info(f"Session keys: {list(request.session.keys())}")
            
            # Get pending event purchase data from session (try both keys)
            pending_event_purchase = request.session.get('wechat_pending_event_purchase')
            _logger.info(f"WeChat pending event purchase: {pending_event_purchase}")
            
            if not pending_event_purchase:
                _logger.warning("No WeChat pending event purchase found, trying regular event purchase details")
                pending_event_purchase = request.session.get('event_purchase_details')
                _logger.info(f"Regular event purchase details: {pending_event_purchase}")
                
            if not pending_event_purchase:
                _logger.error("No pending event purchase found in session (neither WeChat nor regular)")
                _logger.error(f"Session contents: {dict(request.session)}")
                return request.redirect('/event?error=session_expired')
            
            # Get the transaction
            transaction = None
            _logger.info(f"Looking for transaction with ID/reference: {transaction_id_param}")
            
            # First try as reference (since our transaction IDs are references like EVENT-27519-11-1758453437)
            transaction = request.env['payment.transaction'].sudo().search([
                ('reference', '=', transaction_id_param)
            ], limit=1)
            _logger.info(f"Found by reference: {transaction.exists() if transaction else False}")
            
            # If not found as reference, try as integer ID
            if not transaction or not transaction.exists():
                try:
                    _logger.info(f"Trying as integer ID: {transaction_id_param}")
                    transaction = request.env['payment.transaction'].sudo().browse(int(transaction_id_param))
                    _logger.info(f"Tried as integer ID, found: {transaction.exists() if transaction else False}")
                except (ValueError, TypeError) as e:
                    _logger.info(f"Failed to parse as integer ID: {e}")
                    pass
            
            if not transaction or not transaction.exists():
                _logger.error(f"WeChat transaction {transaction_id_param} not found")
                # Let's also search without provider_code filter for debugging
                all_transactions = request.env['payment.transaction'].sudo().search([
                    ('reference', '=', transaction_id_param)
                ])
                _logger.error(f"Found {len(all_transactions)} transactions with reference {transaction_id_param}")
                for t in all_transactions:
                    _logger.error(f"  Transaction ID: {t.id}, Provider: {t.provider_id.name if t.provider_id else 'None'}, Code: {t.provider_code}")
                return request.redirect('/event?error=transaction_not_found')
            
            _logger.info(f"Found transaction: {transaction.id}, State: {transaction.state}, Provider: {transaction.provider_id.name if transaction.provider_id else 'None'}")
            
            # Mark transaction as done (WeChat payment was successful)
            transaction.write({'state': 'done'})
            
            # Create event registration now
            _logger.info(f"Creating event registration with data: {pending_event_purchase}")
            event = request.env['event.event'].sudo().browse(pending_event_purchase['event_id'])
            partner = request.env['res.partner'].sudo().browse(pending_event_purchase['partner_id'])
            
            _logger.info(f"Event exists: {event.exists()}, Partner exists: {partner.exists()}")
            _logger.info(f"Event name: {event.name if event.exists() else 'N/A'}, Partner name: {partner.name if partner.exists() else 'N/A'}")
            
            if not event.exists() or not partner.exists():
                _logger.error(f"Invalid event or partner - Event ID: {pending_event_purchase.get('event_id')}, Partner ID: {pending_event_purchase.get('partner_id')}")
                return request.redirect('/event?error=invalid_data')
            
            # Deduct popcorn money if used
            if pending_event_purchase.get('use_popcorn_money') and pending_event_purchase.get('popcorn_money_to_use', 0) > 0:
                partner.deduct_popcorn_money(pending_event_purchase['popcorn_money_to_use'], f'Event registration: {event.name}')
            
            # CRITICAL: Apply discount if used (must mark discount as used to prevent reuse)
            applied_discount_id = pending_event_purchase.get('applied_discount_id')
            applied_discount = None
            if applied_discount_id:
                applied_discount = request.env['popcorn.discount'].sudo().browse(applied_discount_id)
                if applied_discount.exists():
                    _logger.info(f"Applying discount: {applied_discount.code}")
                    _logger.info(f"Discount usage count before: {applied_discount.usage_count}")
                    applied_discount.action_increment_usage()
                    _logger.info(f"Discount usage count after: {applied_discount.usage_count}")
                    
                    # Calculate discounted price (pass None for membership_plan since this is an event)
                    discounted_price = applied_discount.get_discounted_price(None, event.event_price, partner)
                    
                    # Create usage record
                    request.env['popcorn.discount.usage'].sudo().create({
                        'discount_id': applied_discount.id,
                        'partner_id': partner.id,
                        'original_price': event.event_price,
                        'discounted_price': discounted_price,
                        'currency_id': event.currency_id.id if event.currency_id else request.env.company.currency_id.id,
                        'event_id': event.id,
                        'extra_days': applied_discount.get_extra_days(None, partner)
                    })
                    _logger.info(f"✅ Discount usage record created for WeChat event payment")
            
            # Create the event registration (using only standard fields)
            _logger.info("Creating event registration with vals:")
            registration_vals = {
                'event_id': event.id,
                'partner_id': partner.id,
                'name': partner.name,
                'email': partner.email,
                'phone': partner.phone,
                'state': 'open',
                'payment_amount': pending_event_purchase.get('event_price', 0),
                'payment_transaction_id': transaction.id,
            }
            _logger.info(f"Registration vals: {registration_vals}")
            
            registration = request.env['event.registration'].sudo().create(registration_vals)
            _logger.info(f"Event registration created with ID: {registration.id}, State: {registration.state}, Payment Transaction: {transaction.id}")
            
            payment_message = _('Direct purchase registration for event: %s. Price: %s. Payment successful via %s. Transaction: %s. Event registration created and activated.') % (event.name, pending_event_purchase['event_price'], transaction.provider_id.name, transaction.reference)
            if pending_event_purchase.get('use_popcorn_money') and pending_event_purchase.get('popcorn_money_to_use', 0) > 0:
                payment_message += _('. Popcorn money used: %s%s. Remaining: %s%s') % (event.currency_id.symbol, pending_event_purchase['popcorn_money_to_use'], event.currency_id.symbol, pending_event_purchase.get('remaining_amount', 0))
            
            registration.message_post(body=payment_message)
            _logger.info(f"Event registration message posted")
            
            # Clear session data
            request.session.pop('payment_transaction_id', None)
            request.session.pop('event_purchase_details', None)
            request.session.pop('wechat_pending_event_purchase', None)
            
            _logger.info(f"WeChat event payment successful. Registration created with ID: {registration.id}")
            _logger.info(f"Final registration details - ID: {registration.id}, State: {registration.state}, Partner: {registration.partner_id.name}")
            
            # Redirect to event success page (same pattern as membership success)
            redirect_url = f'/popcorn/event/{event.id}/purchase/success?registration_id={registration.id}'
            _logger.info(f"Redirecting to event success page: {redirect_url}")
            return request.redirect(redirect_url)
            
        except Exception as e:
            _logger.error(f"Failed to handle event purchase redirect: {str(e)}", exc_info=True)
            # Clear session data on error
            request.session.pop('wechat_pending_event_purchase', None)
            request.session.pop('event_purchase_details', None)
            return request.redirect('/event?error=processing_failed')

    def _handle_event_purchase(self, plan, partner, payment_transaction_id=None, payment_reference=None):
        """Handle event purchase instead of membership creation"""
        # Get event purchase details from session
        event_purchase_details = request.session.get('event_purchase_details', {})
        
        if not event_purchase_details:
            _logger.error("No event purchase details found in session")
            return None
        
        # Get the event
        event = request.env['event.event'].sudo().browse(event_purchase_details['event_id'])
        if not event.exists():
            _logger.error(f"Event {event_purchase_details['event_id']} not found")
            return None
        
        # Deduct popcorn money if used
        if event_purchase_details.get('use_popcorn_money') and event_purchase_details.get('popcorn_money_to_use', 0) > 0:
            partner.deduct_popcorn_money(event_purchase_details['popcorn_money_to_use'], f'Event registration: {event.name}')
        
        # Create the event registration (using only standard fields)
        registration_vals = {
            'event_id': event.id,
            'partner_id': partner.id,
            'name': partner.name,
            'email': partner.email,
            'phone': partner.phone,
            'state': 'open',
        }
        
        # Create the registration
        registration = request.env['event.registration'].sudo().create(registration_vals)
        
        # Log the direct purchase
        registration.message_post(
            body=_('Direct purchase registration for club: %s. Price: %s%s') % (event.name, event.currency_id.symbol, event.event_price)
        )
        
        # Clear the session data
        request.session.pop('event_purchase_details', None)
        
        _logger.info(f"Event registration created with ID: {registration.id}")
        return registration

