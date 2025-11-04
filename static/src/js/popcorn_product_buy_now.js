/** @odoo-module **/

import publicWidget from '@web/legacy/js/public/public_widget';
import { jsonrpc } from '@web/core/network/rpc_service';

publicWidget.registry.BuyNowButton = publicWidget.Widget.extend({
    selector: 'body',
    events: {
        'click #buy_now_button': '_onClickBuyNow',
    },

    /**
     * Start method - inject Buy Now button into product page
     */
    start: function () {
        // Only run on product pages
        if (!this.$el.find('.oe_website_sale').length && !this.$el.find('[data-product-id]').length) {
            return this._super();
        }
        
        // Try to find where to inject the button
        const $addToCartForm = this.$el.find('form[action*="/shop/cart/update"]');
        const $addToCartButton = this.$el.find('button:contains("Add to Cart"), a:contains("Add to Cart")');
        const $productDetails = this.$el.find('#product_details, .product_details');
        
        // Get product ID from page
        let productId = null;
        const $productIdInput = this.$el.find('input[name="product_id"]');
        if ($productIdInput.length) {
            productId = $productIdInput.val();
        } else {
            // Try to get from data attribute or URL
            const $productData = this.$el.find('[data-product-id]');
            if ($productData.length) {
                productId = $productData.first().data('product-id');
            }
        }
        
        if (!productId) {
            console.warn('Buy Now button: Could not find product ID');
            return this._super();
        }
        
        // Create Buy Now button
        const $buyNowButton = $('<a>')
            .attr('href', '#')
            .attr('id', 'buy_now_button')
            .attr('data-product-id', productId)
            .addClass('btn btn-primary btn-lg')
            .html('<i class="fa fa-shopping-cart"/> Buy Now with WeChat Pay');
        
        const $buyNowContainer = $('<div>')
            .addClass('mt-3')
            .append($buyNowButton);
        
        // Inject button after Add to Cart form or button
        if ($addToCartForm.length) {
            $addToCartForm.after($buyNowContainer);
        } else if ($addToCartButton.length) {
            $addToCartButton.after($buyNowContainer);
        } else if ($productDetails.length) {
            $productDetails.append($buyNowContainer);
        } else {
            // Fallback: inject before any existing form
            const $firstForm = this.$el.find('form').first();
            if ($firstForm.length) {
                $firstForm.after($buyNowContainer);
            }
        }
        
        return this._super();
    },

    /**
     * Handle Buy Now button click
     * Redirects to direct purchase flow with WeChat payment
     */
    _onClickBuyNow: function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        
        const $button = $(ev.currentTarget);
        const productId = $button.data('product-id');
        
        if (!productId) {
            console.error('Product ID not found');
            return;
        }
        
        // Get quantity from form if available
        let quantity = 1;
        const $quantityInput = $('input[name="add_qty"]');
        if ($quantityInput.length) {
            quantity = parseFloat($quantityInput.val()) || 1;
        }
        
        // Build URL
        const url = `/shop/buy_now?product_id=${productId}&add_qty=${quantity}`;
        
        // Redirect to buy now flow
        window.location.href = url;
    },
});

export default publicWidget.registry.BuyNowButton;

