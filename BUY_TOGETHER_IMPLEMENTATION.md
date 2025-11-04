# Buy Together Feature Implementation

## Overview
This feature allows customers to generate a shareable discount code, invite a friend to purchase the same membership, and both receive a discount.

## How It Works

### Flow
1. **Person A** goes to checkout for a membership plan that has buy-together enabled
2. **Person A** enters their friend's name in the "Buy Together with a Friend" section
3. **Person A** clicks "Generate Code" → System creates a unique discount code
4. **Person A** shares the code with **Person B**
5. **Person B** goes to checkout, enters the code → Gets discount and purchases FIRST
6. **Person A** can now use the same code and also gets the discount

### Key Implementation Details

#### Backend (Models)
- **popcorn_membership_plan.py**: Added 3 fields:
  - `buy_together_enabled`: Boolean to enable this feature on a plan
  - `buy_together_instructions`: Text instructions shown to customers
  - `buy_together_discount_amount`: Percentage discount amount

- **popcorn_discount.py**: Added 1 field:
  - `buy_together_discount`: Boolean flag to mark buy-together discounts

#### Backend (Controllers)
- **popcorn_discount_controller.py**:
  - Updated `validate_discount_code()` to enforce usage order (Person B must use first)
  - Added new endpoint `/popcorn/buy-together/generate` to create discount codes

#### Frontend (Templates)
- **popcorn_membership_website_templates.xml**:
  - Added "Buy Together with a Friend" section on checkout page
  - Shows input for friend's name, generate button, and code display area
  - Only visible when `buy_together_enabled=True` and not upgrade/renewal

#### Frontend (JavaScript)
- **popcorn_buy_together.js**:
  - Handles code generation AJAX call
  - Displays generated code with copy functionality
  - Manages UI state during code generation

#### Frontend (CSS)
- **popcorn_buy_together_styles.css**:
  - Matches existing popcorn design system
  - Responsive design for mobile devices
  - Visual feedback for success/error states

## Configuration

### Enable Buy Together on a Membership Plan
1. Go to **Popcorn > Membership Plans**
2. Open the desired membership plan
3. Go to **Buy Together Settings** section
4. Check **Enable Buy Together**
5. Set **Buy Together Discount (%)** (e.g., 10 for 10% off)
6. Add **Buy Together Instructions** (e.g., "Share this code with a friend and both of you get 10% off!")

### How to Use (Customer Flow)

1. Customer A goes to membership checkout
2. Fills in friend's name
3. Clicks "Generate Code"
4. Gets a unique code (e.g., "johnsmith-AND-janedoe-1234567890")
5. Shares code with friend
6. Friend uses code first → Gets discount
7. Customer A uses code second → Gets discount
8. Done!

## Technical Notes

### Discount Validation Logic
- For buy-together discounts, Person A cannot use code until Person B has used it (`usage_count >= 1`)
- Each person can only use the code once (`usage_limit_per_customer=1`)
- Maximum 2 uses total (`usage_limit=2`)

### Code Format
Generated codes follow the pattern:
```
{current_user_username}-AND-{friend_name}-{timestamp}
```

Example: `johnsmith-AND-janedoe-1734567890`

## Files Modified
1. `models/popcorn_membership_plan.py` - Added buy-together fields
2. `models/popcorn_discount.py` - Added buy-together flag
3. `views/popcorn_membership_plan_views.xml` - Added buy-together settings to form
4. `views/popcorn_membership_website_templates.xml` - Added buy-together section to checkout
5. `controllers/popcorn_discount_controller.py` - Added validation and generation logic
6. `__manifest__.py` - Registered new assets

## Files Created
1. `static/src/js/popcorn_buy_together.js` - JavaScript functionality
2. `static/src/css/popcorn_buy_together_styles.css` - Styling

## Testing Steps

1. Enable buy-together on a membership plan in backend
2. Go to checkout for that plan (as logged-in user)
3. Enter friend's name and click Generate Code
4. Share code with friend
5. Friend enters code at checkout → Should get discount
6. Original user enters same code → Should get discount
7. Verify both memberships were created with discount applied

