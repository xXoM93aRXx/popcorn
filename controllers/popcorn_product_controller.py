# -*- coding: utf-8 -*-

from odoo import http, fields, _
from odoo.http import request
from odoo.exceptions import ValidationError
from werkzeug.utils import redirect
import logging
import time

_logger = logging.getLogger(__name__)


class PopcornProductController(http.Controller):
    """Controller for direct product purchase with WeChat and Alipay payment"""
    
    @http.route('/shop/buy_now/checkout', type='http', auth='public', website=True, methods=['GET', 'POST'])
    def buy_now_checkout(self, **kwargs):
        """
        Direct checkout flow from cart: Create payment transaction and redirect to WeChat payment
        
        This bypasses the standard checkout process.
        """
        try:
            # Get current sale order (cart)
            order = request.website.sale_get_order(force_create=False)
            
            if not order or not order.website_order_line:
                return request.redirect('/shop/cart?error=empty_cart')
            
            # Ensure cart is ready
            if not order._is_cart_ready():
                return request.redirect('/shop/cart?error=cart_not_ready')
            
            # Get website and partner
            website = request.website
            partner = request.env.user.partner_id if request.env.user != request.website.user_id else website.partner_id
            
            # Get WeChat payment provider
            wechat_provider = request.env['payment.provider'].sudo().search([
                ('code', '=', 'wechat'),
                ('state', '=', 'enabled'),
                ('is_published', '=', True),
            ], limit=1)
            
            if not wechat_provider:
                _logger.error("WeChat payment provider not found or not enabled")
                return request.redirect('/shop/cart?error=wechat_not_available')
            
            # Calculate total amount
            amount = order.amount_total
            
            if amount <= 0:
                # Free order - confirm directly
                order.action_confirm()
                return request.redirect('/shop/confirmation')
            
            # Create payment transaction
            timestamp = int(time.time())
            payment_method = request.env['payment.method'].sudo().search([
                ('provider_ids', 'in', wechat_provider.id),
                ('active', '=', True)
            ], limit=1)
            
            if not payment_method:
                # Create default payment method if needed
                payment_method = request.env['payment.method'].sudo().create({
                    'name': 'WeChat Pay',
                    'code': 'wechat',
                    'provider_ids': [(6, 0, [wechat_provider.id])],
                    'active': True,
                })
            
            # Generate access token for landing route
            from odoo.addons.payment import utils as payment_utils
            access_token = payment_utils.generate_access_token(
                partner.id, amount, order.currency_id.id
            )
            
            # Set landing route for payment completion
            landing_route = '/shop/buy_now/success'
            
            # Create payment transaction with landing_route
            transaction = request.env['payment.transaction'].sudo().create({
                'provider_id': wechat_provider.id,
                'payment_method_id': payment_method.id,
                'amount': amount,
                'currency_id': order.currency_id.id,
                'partner_id': partner.id,
                'reference': f'SO-{order.id}-{timestamp}',
                'state': 'draft',
                'sale_order_ids': [(6, 0, [order.id])],
                'landing_route': landing_route,
                'operation': 'online_direct',
            })
            
            # Update landing route with transaction ID and access token
            from odoo.addons.payment.controllers.portal import PaymentPortal
            PaymentPortal._update_landing_route(transaction, access_token)
            
            # Monitor transaction for payment status polling
            from odoo.addons.payment.controllers.post_processing import PaymentPostProcessing
            PaymentPostProcessing.monitor_transaction(transaction)
            
            _logger.info(f"Created payment transaction {transaction.reference} for sale order {order.name}")
            
            # Store transaction and order in session for callback
            request.session['payment_transaction_id'] = transaction.id
            request.session['wechat_pending_order'] = {
                'order_id': order.id,
                'transaction_id': transaction.id,
            }
            
            # Redirect to WeChat OAuth2 flow
            wechat_oauth_url = f'/payment/wechat/oauth2/authorize?transaction_id={transaction.reference}'
            _logger.info(f"Redirecting to WeChat OAuth2: {wechat_oauth_url}")
            return request.redirect(wechat_oauth_url)
            
        except Exception as e:
            _logger.error(f"Error in buy_now_checkout: {str(e)}", exc_info=True)
            return request.redirect('/shop/cart?error=payment_failed')
    
    @http.route('/shop/buy_now', type='http', auth='public', website=True, methods=['GET', 'POST'])
    def buy_now(self, product_id=None, add_qty=1, **kwargs):
        """
        Direct purchase flow: Create sale order and redirect to WeChat payment
        
        This bypasses the cart and checkout process.
        """
        try:
            # Validate product
            if not product_id:
                return request.redirect('/shop?error=missing_product')
            
            product = request.env['product.product'].sudo().browse(int(product_id))
            if not product.exists() or not product.sale_ok:
                return request.redirect('/shop?error=invalid_product')
            
            # Get website and partner
            website = request.website
            partner = request.env.user.partner_id if request.env.user != request.website.user_id else website.partner_id
            
            # Get WeChat payment provider
            wechat_provider = request.env['payment.provider'].sudo().search([
                ('code', '=', 'wechat'),
                ('state', '=', 'enabled'),
                ('is_published', '=', True),
            ], limit=1)
            
            if not wechat_provider:
                _logger.error("WeChat payment provider not found or not enabled")
                return request.redirect('/shop?error=wechat_not_available')
            
            # Create sale order directly (keep in draft until payment confirmed)
            order = request.env['sale.order'].sudo().create({
                'partner_id': partner.id,
                'website_id': website.id,
                'order_line': [(0, 0, {
                    'product_id': product.id,
                    'product_uom_qty': float(add_qty),
                    'price_unit': product.list_price,
                })],
            })
            
            # Order remains in draft state until payment is confirmed
            # Odoo's payment framework will automatically confirm it when transaction is done
            
            # Create payment transaction
            timestamp = int(time.time())
            payment_method = request.env['payment.method'].sudo().search([
                ('provider_ids', 'in', wechat_provider.id),
                ('active', '=', True)
            ], limit=1)
            
            if not payment_method:
                # Create default payment method if needed
                payment_method = request.env['payment.method'].sudo().create({
                    'name': 'WeChat Pay',
                    'code': 'wechat',
                    'provider_ids': [(6, 0, [wechat_provider.id])],
                    'active': True,
                })
            
            # Calculate total amount
            amount = order.amount_total
            
            # Generate access token for landing route
            from odoo.addons.payment import utils as payment_utils
            access_token = payment_utils.generate_access_token(
                partner.id, amount, order.currency_id.id
            )
            
            # Set landing route for payment completion
            landing_route = '/shop/buy_now/success'
            
            # Create payment transaction with landing_route
            transaction = request.env['payment.transaction'].sudo().create({
                'provider_id': wechat_provider.id,
                'payment_method_id': payment_method.id,
                'amount': amount,
                'currency_id': order.currency_id.id,
                'partner_id': partner.id,
                'reference': f'SO-{order.id}-{timestamp}',
                'state': 'draft',
                'sale_order_ids': [(6, 0, [order.id])],
                'landing_route': landing_route,
                'operation': 'online_direct',
            })
            
            # Update landing route with transaction ID and access token
            from odoo.addons.payment.controllers.portal import PaymentPortal
            PaymentPortal._update_landing_route(transaction, access_token)
            
            # Monitor transaction for payment status polling
            from odoo.addons.payment.controllers.post_processing import PaymentPostProcessing
            PaymentPostProcessing.monitor_transaction(transaction)
            
            _logger.info(f"Created payment transaction {transaction.reference} for sale order {order.name}")
            
            # Store transaction and order in session for callback
            request.session['payment_transaction_id'] = transaction.id
            request.session['wechat_pending_order'] = {
                'order_id': order.id,
                'transaction_id': transaction.id,
            }
            
            # Redirect to WeChat OAuth2 flow
            wechat_oauth_url = f'/payment/wechat/oauth2/authorize?transaction_id={transaction.reference}'
            _logger.info(f"Redirecting to WeChat OAuth2: {wechat_oauth_url}")
            return request.redirect(wechat_oauth_url)
            
        except Exception as e:
            _logger.error(f"Error in buy_now: {str(e)}", exc_info=True)
            return request.redirect('/shop?error=payment_failed')
    
    @http.route('/shop/buy_now/success', type='http', auth='public', website=True)
    def buy_now_success(self, tx_id=None, access_token=None, transaction_id=None, **kwargs):
        """Handle successful payment completion"""
        try:
            # Support both Odoo standard format (tx_id + access_token) and our custom format (transaction_id)
            if tx_id and access_token:
                # Standard Odoo payment confirmation format
                tx_id = int(tx_id)
                transaction = request.env['payment.transaction'].sudo().browse(tx_id)
                
                # Verify access token
                from odoo.addons.payment import utils as payment_utils
                if not payment_utils.check_access_token(
                    access_token, transaction.partner_id.id, transaction.amount, transaction.currency_id.id
                ):
                    return request.redirect('/shop?error=invalid_access_token')
                    
            elif transaction_id:
                # Custom format - find by reference (support both WeChat and Alipay)
                transaction = request.env['payment.transaction'].sudo().search([
                    ('reference', '=', transaction_id),
                    ('provider_code', 'in', ['wechat', 'alipay'])
                ], limit=1)
            else:
                return request.redirect('/shop?error=missing_transaction')
            
            if not transaction:
                return request.redirect('/shop?error=transaction_not_found')
            
            # Do not force state changes here. If the provider already confirmed the transaction,
            # confirm the order without creating accounting payments and mark as post-processed.
            if transaction.state == 'done' and not transaction.is_post_processed:
                order = transaction.sale_order_ids[0] if transaction.sale_order_ids else None
                if order and order.state in ('draft', 'sent') and order._is_confirmation_amount_reached():
                    order.with_context(send_email=False).action_confirm()
                transaction.write({'is_post_processed': True})
                if transaction.sale_order_ids:
                    transaction.sale_order_ids.invalidate_recordset(['state'])
            
            # Check transaction state after marking as done
            if transaction.state not in ['done', 'pending', 'authorized']:
                # Transaction failed or cancelled
                return request.redirect('/shop?error=transaction_failed')
            
            order = transaction.sale_order_ids[0] if transaction.sale_order_ids else None
            if not order:
                return request.redirect('/shop?error=order_not_found')
            
            # Clean up session
            request.session.pop('payment_transaction_id', None)
            request.session.pop('wechat_pending_order', None)
            
            return request.render('popcorn.product_buy_now_success', {
                'order': order,
                'transaction': transaction,
            })
            
        except Exception as e:
            _logger.error(f"Error in buy_now_success: {str(e)}", exc_info=True)
            return request.redirect('/shop?error=success_page_error')
    
    @http.route('/shop/buy_now/alipay', type='http', auth='public', website=True, methods=['GET', 'POST'])
    def buy_now_alipay(self, product_id=None, add_qty=1, **kwargs):
        """
        Direct purchase flow using Alipay WAP payment
        """
        try:
            if not product_id:
                return request.redirect('/shop?error=missing_product')
            
            product = request.env['product.product'].sudo().browse(int(product_id))
            if not product.exists() or not product.sale_ok:
                return request.redirect('/shop?error=invalid_product')
            
            website = request.website
            partner = request.env.user.partner_id if request.env.user != request.website.user_id else website.partner_id
            
            alipay_provider = request.env['payment.provider'].sudo().search([
                ('code', '=', 'alipay'),
                ('state', '=', 'enabled'),
                ('is_published', '=', True),
            ], limit=1)
            
            if not alipay_provider:
                _logger.error("Alipay payment provider not found or not enabled")
                return request.redirect('/shop?error=alipay_not_available')
            
            order = request.env['sale.order'].sudo().create({
                'partner_id': partner.id,
                'website_id': website.id,
                'order_line': [(0, 0, {
                    'product_id': product.id,
                    'product_uom_qty': float(add_qty),
                    'price_unit': product.list_price,
                })],
            })
            
            timestamp = int(time.time())
            payment_method = request.env['payment.method'].sudo().search([
                ('provider_ids', 'in', alipay_provider.id),
                ('active', '=', True)
            ], limit=1)
            
            if not payment_method:
                payment_method = request.env['payment.method'].sudo().create({
                    'name': 'Alipay',
                    'code': 'alipay',
                    'provider_ids': [(6, 0, [alipay_provider.id])],
                    'active': True,
                })
            
            amount = order.amount_total
            
            from odoo.addons.payment import utils as payment_utils
            access_token = payment_utils.generate_access_token(
                partner.id, amount, order.currency_id.id
            )
            
            landing_route = '/shop/buy_now/success'
            
            transaction = request.env['payment.transaction'].sudo().create({
                'provider_id': alipay_provider.id,
                'payment_method_id': payment_method.id,
                'amount': amount,
                'currency_id': order.currency_id.id,
                'partner_id': partner.id,
                'reference': f'SO-{order.id}-{timestamp}',
                'state': 'draft',
                'sale_order_ids': [(6, 0, [order.id])],
                'landing_route': landing_route,
                'operation': 'online_direct',
            })
            
            from odoo.addons.payment.controllers.portal import PaymentPortal
            PaymentPortal._update_landing_route(transaction, access_token)
            
            from odoo.addons.payment.controllers.post_processing import PaymentPostProcessing
            PaymentPostProcessing.monitor_transaction(transaction)
            
            # Get Alipay payment URL using the same method as other payment providers
            # This ensures consistency and proper redirect handling
            try:
                payment_link = transaction._get_specific_rendering_values(None)
                if payment_link and 'action_url' in payment_link:
                    payment_url = payment_link['action_url']
                    _logger.info(f"Redirecting to Alipay payment URL for product purchase: {payment_url[:100]}...")
                    return redirect(payment_url, code=302)
                else:
                    # Fallback to direct payment link method
                    payment_url = transaction._get_payment_link()
                    if payment_url:
                        _logger.info(f"Redirecting to Alipay payment URL for product purchase (fallback): {payment_url[:100]}...")
                        return redirect(payment_url, code=302)
            except Exception as e:
                _logger.error(f"Failed to get Alipay payment URL for product: {str(e)}", exc_info=True)
            
            # If we get here, payment URL generation failed
            _logger.error("Failed to create Alipay payment URL")
            return request.redirect('/shop?error=alipay_payment_failed')
        
        except Exception as e:
            _logger.error(f"Error in buy_now_alipay: {str(e)}", exc_info=True)
            return request.redirect('/shop?error=alipay_payment_failed')
    
    @http.route('/shop/buy_now/alipay/checkout', type='http', auth='public', website=True, methods=['GET', 'POST'])
    def buy_now_alipay_checkout(self, **kwargs):
        """
        Direct checkout from cart using Alipay payment
        """
        try:
            order = request.website.sale_get_order(force_create=False)
            if not order or not order.website_order_line:
                return request.redirect('/shop/cart?error=empty_cart')
            
            if not order._is_cart_ready():
                return request.redirect('/shop/cart?error=cart_not_ready')
            
            website = request.website
            partner = request.env.user.partner_id if request.env.user != request.website.user_id else website.partner_id
            
            alipay_provider = request.env['payment.provider'].sudo().search([
                ('code', '=', 'alipay'),
                ('state', '=', 'enabled'),
                ('is_published', '=', True),
            ], limit=1)
            
            if not alipay_provider:
                _logger.error("Alipay payment provider not found or not enabled")
                return request.redirect('/shop/cart?error=alipay_not_available')
            
            amount = order.amount_total
            if amount <= 0:
                order.action_confirm()
                return request.redirect('/shop/confirmation')
            
            timestamp = int(time.time())
            payment_method = request.env['payment.method'].sudo().search([
                ('provider_ids', 'in', alipay_provider.id),
                ('active', '=', True)
            ], limit=1)
            
            if not payment_method:
                payment_method = request.env['payment.method'].sudo().create({
                    'name': 'Alipay',
                    'code': 'alipay',
                    'provider_ids': [(6, 0, [alipay_provider.id])],
                    'active': True,
                })
            
            from odoo.addons.payment import utils as payment_utils
            access_token = payment_utils.generate_access_token(
                partner.id, amount, order.currency_id.id
            )
            
            landing_route = '/shop/buy_now/success'
            
            transaction = request.env['payment.transaction'].sudo().create({
                'provider_id': alipay_provider.id,
                'payment_method_id': payment_method.id,
                'amount': amount,
                'currency_id': order.currency_id.id,
                'partner_id': partner.id,
                'reference': f'SO-{order.id}-{timestamp}',
                'state': 'draft',
                'sale_order_ids': [(6, 0, [order.id])],
                'landing_route': landing_route,
                'operation': 'online_direct',
            })
            
            from odoo.addons.payment.controllers.portal import PaymentPortal
            PaymentPortal._update_landing_route(transaction, access_token)
            
            from odoo.addons.payment.controllers.post_processing import PaymentPostProcessing
            PaymentPostProcessing.monitor_transaction(transaction)
            
            # Get Alipay payment URL using the same method as other payment providers
            # This ensures consistency and proper redirect handling
            try:
                payment_link = transaction._get_specific_rendering_values(None)
                if payment_link and 'action_url' in payment_link:
                    payment_url = payment_link['action_url']
                    _logger.info(f"Redirecting to Alipay payment URL for cart checkout: {payment_url[:100]}...")
                    return redirect(payment_url, code=302)
                else:
                    # Fallback to direct payment link method
                    payment_url = transaction._get_payment_link()
                    if payment_url:
                        _logger.info(f"Redirecting to Alipay payment URL for cart checkout (fallback): {payment_url[:100]}...")
                        return redirect(payment_url, code=302)
            except Exception as e:
                _logger.error(f"Failed to get Alipay payment URL for checkout: {str(e)}", exc_info=True)
            
            # If we get here, payment URL generation failed
            _logger.error("Failed to create Alipay payment URL for checkout")
            return request.redirect('/shop/cart?error=alipay_payment_failed')
        
        except Exception as e:
            _logger.error(f"Error in buy_now_alipay_checkout: {str(e)}", exc_info=True)
            return request.redirect('/shop/cart?error=alipay_payment_failed')