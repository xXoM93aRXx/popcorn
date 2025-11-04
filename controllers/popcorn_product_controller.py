# -*- coding: utf-8 -*-

from odoo import http, fields, _
from odoo.http import request
from odoo.exceptions import ValidationError
import logging
import time

_logger = logging.getLogger(__name__)


class PopcornProductController(http.Controller):
    """Controller for direct product purchase with WeChat payment"""
    
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
                # Custom format - find by reference
                transaction = request.env['payment.transaction'].sudo().search([
                    ('reference', '=', transaction_id),
                    ('provider_code', '=', 'wechat')
                ], limit=1)
            else:
                return request.redirect('/shop?error=missing_transaction')
            
            if not transaction:
                return request.redirect('/shop?error=transaction_not_found')
            
            # Mark transaction as done (WeChat payment was successful)
            # Same approach as membership payments - trust WeChat callback and mark as done immediately
            # The webhook will verify later, but we proceed with order confirmation now
            if transaction.state == 'draft':
                transaction.write({'state': 'done'})
                
                # Manually confirm the order without sending emails (to avoid PDF generation errors)
                # Public users may not have access to mail templates or Wkhtmltopdf may not be installed
                # We don't call _post_process() here because it tries to send emails with public user context
                # Instead, we confirm the order manually and mark as post-processed
                order = transaction.sale_order_ids[0] if transaction.sale_order_ids else None
                if order and order.state in ('draft', 'sent'):
                    # Check if payment amount is sufficient for confirmation
                    if order._is_confirmation_amount_reached():
                        # Confirm order without sending email to avoid PDF/access errors
                        order.with_context(send_email=False).action_confirm()
                
                # Mark transaction as post-processed to prevent cron/webhook from trying again
                # This avoids email sending issues while still allowing webhook verification
                transaction.write({'is_post_processed': True})
                
                # Refresh order to get updated state
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
