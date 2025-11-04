# Popcorn Club Tests

This directory contains tests for the Popcorn Club module.

## Test Files

- **test_concurrent_registrations.py** - Stress test for concurrent event registrations and waitlist promotion
- **test_membership_auto_expiration.py** - Test for automatic membership expiration
- **test_waitlist_promotion.py** - Test for waitlist functionality
- **test_event_timezone.py** - Test for event timezone conversion in notifications
- **test_frontend_race.py** - Test for frontend registration race condition fix (over-booking prevention)
- **test_first_timer_discount.py** - Test for first-timer discount bug fix (independent coupon and membership systems)
- **test_buy_together.py** - Comprehensive test for buy-together discount code generation and usage flow

## Running Tests

All tests in this directory are standalone XML-RPC tests that can be run directly with Python. Make sure your Odoo server is running before executing the tests.

To run the tests, execute them directly with Python from the `popcorn` module directory:

```bash
# From the module directory
python tests/test_concurrent_registrations.py
python tests/test_membership_auto_expiration.py
python tests/test_waitlist_promotion.py
python tests/test_event_timezone.py  # Tests timezone conversion fix
python tests/test_frontend_race.py   # Tests race condition fix (over-booking prevention)
python tests/test_first_timer_discount.py  # Tests first-timer discount bug fix
python tests/test_buy_together.py  # Tests buy-together discount feature
```

**Note:** For XML-RPC tests, you need to update the configuration at the top of each file:
- `ODOO_URL` - Your Odoo server URL
- `DB_NAME` - Your database name
- `USERNAME` - Your username
- `PASSWORD` - Your password

## Test Coverage

### test_event_timezone.py

This test verifies the fix for the "Today's Event" notification showing incorrect time (1 hour offset issue).

**Test cases included:**
1. **TEST 1-2**: Creates partner with Asia/Shanghai timezone and event at 4:00 PM CST
2. **TEST 3**: Creates registration for the partner
3. **TEST 4**: Verifies formatted time is "04:00 PM" (not "05:00 PM" with 1-hour bug)
4. **TEST 5**: Tests notification with event_time_formatted placeholder
5. **TEST 6**: Tests with different timezone (America/New_York) to verify conversion
6. **TEST 7**: Cleans up test data

**What it verifies:**
- Event time conversion respects partner's timezone (Asia/Shanghai UTC+8)
- No incorrect 1-hour offset is applied
- Notification displays correct time (4:00 PM, not 5:00 PM)
- Timezone fallback logic works correctly
- Different timezones convert correctly

**Expected results:**
- Shanghai partner (UTC+8): Should see 4:00 PM
- New York partner (UTC-5): Should see 3:00-4:00 AM
- **Bug detection**: If time shows as 5:00 PM for Shanghai, the 1-hour offset bug is still present

### test_frontend_race.py

This test verifies the fix for the frontend registration race condition that caused over-booking.

**What it tests:**
1. Creates test users with unlimited memberships
2. Fills event to capacity (5/5 seats)
3. Attempts 3 concurrent registrations for the same event
4. Verifies NO OVER-BOOKING occurs
5. Verifies excess registrations are added to waitlist

**What it verifies:**
- Race condition fix in model's create() method (lines 735-761)
- Uses flush_all() to see concurrent changes from other requests
- Uses search() instead of cached ORM relationships for fresh data
- Proper waitlist assignment when capacity exceeded

**Expected results:**
- Event capacity: 5 seats
- Fills 5 seats, then attempts 3 more
- **Should result in**: Exactly 5 confirmed, 3 waitlisted
- **Bug detection**: If 6+ confirmed, race condition fix is not working

**How to run:**
1. Update credentials at top of file (ODOO_URL, DB_NAME, USERNAME, PASSWORD)
2. Run: `python tests/test_frontend_race.py`
3. Enter Event ID (should have 5 seats capacity)
4. Test will:
   - Create 8 users with memberships
   - Fill 5 seats
   - Attempt 3 concurrent registrations
   - Report if over-booking occurred

**Note**: This is a backend XML-RPC test, but it exercises the EXACT same code path as frontend registrations since both call the model's create() method.

## Test Data

The timezone test creates:
- A test partner with Asia/Shanghai timezone
- An event starting at 4:00 PM Shanghai time (stored as 8:00 UTC)
- A registration for the partner

The test then verifies that:
- Time is formatted as "04:00 PM" in Shanghai timezone (not 5:00 PM)
- No incorrect 1-hour offset is applied
- Notifications display the correct time for the partner

### test_first_timer_discount.py

This test verifies the fix for the first-timer discount bug where users who use their coupon for club registrations can still get the first-timer discount for memberships.

**What it tests:**
1. First-timer can use their coupon for a club registration without affecting membership pricing
2. Discount calculation uses the correct original price (first-timer vs normal)
3. No validation error "Discounted price cannot be higher than original price"
4. Both systems work independently

**Bug that was fixed:**
- Previously, discount calculation always used `price_normal` as the base, but the usage record used `price_first_timer` as original_price
- This caused validation errors when discounted price from normal price > first-timer price
- Fix: Pass the correct original price (`purchase_price`) to discount calculation methods

**Usage:**
```bash
python tests/test_first_timer_discount.py
```

**Expected output:**
- Creates test first-timer user
- Generates discount code
- Tests discount calculation with correct pricing
- Verifies no validation errors occur
- Confirms systems are independent

### test_buy_together.py

This test verifies the complete buy-together discount flow where two people can purchase the same membership together with a shared discount code.

**What it tests:**
1. Code generation works correctly
2. Person B can use the code first (should succeed)
3. Person A can use the code second (should succeed)  
4. Person A cannot use the code before Person B (should fail)
5. Neither person can use the code more than once
6. Edge cases and error conditions

**Test scenarios covered:**
- ✅ Happy path: Person B uses, then Person A uses
- ❌ Person A tries to use before Person B → should fail
- ❌ Person A tries to use code twice → should fail
- ❌ Person B tries to use code twice → should fail
- ❌ Empty friend name → should fail
- ❌ Buy-together disabled → should fail
- ❌ Discount not configured → should fail

**Usage:**
```bash
python tests/test_buy_together.py
```

**Expected output:**
- Creates test membership plan with buy-together enabled
- Creates Person A and Person B
- Person A generates code successfully
- Person B uses code first → gets discount
- Person A uses code second → gets discount
- Both users cannot use code more than once
- Verifies all validation rules work correctly
- Confirms discount becomes invalid after 2 uses

**See detailed scenarios:** `tests/BUY_TOGETHER_TEST_SCENARIOS.md`

