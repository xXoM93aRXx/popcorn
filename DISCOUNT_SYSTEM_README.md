# Popcorn Club Discount System

## Overview

The Popcorn Club discount system provides a flexible way to create and manage discounts for membership plans. Instead of hardcoded first-timer pricing, you can now create various types of discounts and link them to specific membership plans.

## Features

### Discount Types

1. **Percentage Discount**: Apply a percentage discount (e.g., 15% off)
2. **Fixed Amount Discount**: Apply a fixed dollar amount discount (e.g., $50 off)
3. **First Timer Price**: Use the plan's first-timer price
4. **Upgrade Discount**: Special discount for membership upgrades

### Customer Restrictions

- **All Customers**: Available to everyone
- **First Timer Only**: Only for first-time customers
- **Existing Customers Only**: Only for returning customers
- **New Customers Only**: Only for new customers

### Usage Controls

- **Usage Limit**: Maximum number of times the discount can be used
- **Per Customer Limit**: Maximum times one customer can use the discount
- **Date Range**: Valid from/to dates
- **Plan Restrictions**: Link to specific membership plans or apply globally

## How to Use

### Creating Discounts

1. Go to **Popcorn Club > Discounts**
2. Click **Create** to add a new discount
3. Fill in the discount details:
   - **Name**: Display name for the discount
   - **Code**: Optional code for customers to enter
   - **Discount Type**: Choose from percentage, fixed amount, first timer, or upgrade
   - **Discount Value**: The discount amount or percentage
   - **Customer Type**: Who can use this discount
   - **Applicable Plans**: Which membership plans this applies to (leave empty for all plans)

### Linking Discounts to Plans

1. Go to **Popcorn Club > Membership Plans**
2. Open a membership plan
3. Go to the **Available Discounts** tab
4. Add discounts that should apply to this plan

### Applying Discounts to Memberships

#### Programmatically

```python
# Get a membership and discount
membership = self.env['popcorn.membership'].browse(membership_id)
discount = self.env['popcorn.discount'].browse(discount_id)

# Apply the discount
membership.apply_discount(discount)

# Remove the discount
membership.remove_discount()
```

#### Getting Available Discounts

```python
# Get available discounts for a plan and customer
plan = self.env['popcorn.membership.plan'].browse(plan_id)
customer = self.env['res.partner'].browse(customer_id)

available_discounts = plan.get_available_discounts(customer)

# Get the best discount price
best_price, best_discount = plan.get_best_discount_price(customer)
```

### Sample Discounts

The system comes with several sample discounts:

1. **Early Bird Special**: 15% off for early registrations
2. **First Timer Welcome**: Uses first-timer pricing for new customers
3. **Student Special**: $50 off for students
4. **Referral Bonus**: 10% off for referred customers
5. **Upgrade Special**: $25 off for membership upgrades
6. **Holiday Special**: 20% off during holidays

## Migration from Hardcoded Pricing

The old hardcoded first-timer pricing is still available through the `price_first_timer` field on membership plans. However, you can now create a "First Timer Welcome" discount that uses this pricing instead of hardcoding it in your application logic.

### Benefits of the New System

1. **Flexibility**: Create unlimited discount types and combinations
2. **Control**: Set usage limits, date ranges, and customer restrictions
3. **Tracking**: Monitor discount usage and effectiveness
4. **Marketing**: Create targeted campaigns for different customer segments
5. **Analytics**: Track which discounts are most popular
6. **Automation**: Set up automatic discount application based on customer attributes

## Security

- **User Access**: Regular users can view discounts but not modify them
- **Manager Access**: System administrators can create, modify, and delete discounts
- **Portal Access**: Portal users can view public discounts

## Best Practices

1. **Test Discounts**: Always test discounts before making them public
2. **Set Limits**: Use usage limits to prevent abuse
3. **Monitor Usage**: Regularly check discount usage statistics
4. **Date Ranges**: Set appropriate validity periods for time-limited offers
5. **Customer Segmentation**: Use customer type restrictions to target specific groups
6. **Plan Linking**: Link discounts to specific plans when appropriate

## Troubleshooting

### Common Issues

1. **Discount Not Applied**: Check if the discount is active, valid, and applies to the selected plan
2. **Customer Restrictions**: Ensure the customer meets the discount's customer type requirements
3. **Usage Limits**: Check if the discount has reached its usage limit
4. **Date Validity**: Verify the discount is within its valid date range

### Support

For technical support or questions about the discount system, contact your system administrator.
