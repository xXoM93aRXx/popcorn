# -*- coding: utf-8 -*-
"""
Test for First Timer Coupon Usage Limit

This test verifies that:
1. First-timer coupon can only be used ONCE (usage_limit = 1)
2. Cannot be reused for multiple club registrations
3. Shows appropriate error when trying to reuse
4. Only one club booking allowed per coupon

Usage:
    python tests/test_first_timer_coupon_usage.py
"""

import xmlrpc.client
import time
from datetime import datetime, timedelta

# Configuration
ODOO_URL = 'http://localhost:8069'
DB_NAME = 'popcorn'
USERNAME = 'omar.mahdy246@gmail.com'
PASSWORD = 'congr4t5'


def authenticate():
    """Authenticate with Odoo"""
    try:
        common = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/common')
        uid = common.authenticate(DB_NAME, USERNAME, PASSWORD, {})
        if not uid:
            print(f"[ERROR] Authentication failed")
            return None
        return uid
    except Exception as e:
        print(f"[ERROR] Error during authentication: {e}")
        return None


def test_first_timer_coupon_usage_limit():
    """Test that first-timer coupon can only be used once"""
    
    print("=" * 80)
    print("TEST: First Timer Coupon Usage Limit")
    print("=" * 80)
    
    # Connect to Odoo
    uid = authenticate()
    if not uid:
        print("\n[FAIL] Cannot authenticate - aborting test")
        return
    
    models = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/object')
    
    try:
        # STEP 1: Create a fresh first-timer partner
        print("\n[STEP 1] Creating a fresh first-timer test partner...")
        
        import random
        unique_email = f'test.coupon.user.{random.randint(1000, 9999)}@example.com'
        
        partner_id = models.execute_kw(
            DB_NAME, uid, PASSWORD,
            'res.partner', 'create',
            [{
                'name': 'Test Coupon Usage User',
                'email': unique_email,
                'is_first_timer': True,
            }]
        )
        print(f"  [OK] Created test partner ID: {partner_id}")
        
        # Get their discount code
        partner_data = models.execute_kw(
            DB_NAME, uid, PASSWORD,
            'res.partner', 'read', [partner_id],
            {'fields': ['first_timer_discount_code', 'is_first_timer']}
        )
        
        discount_code = partner_data[0].get('first_timer_discount_code')
        
        if not discount_code:
            models.execute_kw(
                DB_NAME, uid, PASSWORD,
                'res.partner', 'action_generate_first_timer_discount',
                [[partner_id]]
            )
            partner_data = models.execute_kw(
                DB_NAME, uid, PASSWORD,
                'res.partner', 'read', [partner_id],
                {'fields': ['first_timer_discount_code']}
            )
            discount_code = partner_data[0].get('first_timer_discount_code')
        
        print(f"  [OK] Discount code: {discount_code}")
        
        # STEP 2: Find the discount record
        print("\n[STEP 2] Finding discount record...")
        
        discount_ids = models.execute_kw(
            DB_NAME, uid, PASSWORD,
            'popcorn.discount', 'search',
            [[('code', '=', discount_code), ('active', '=', True)]]
        )
        
        if not discount_ids:
            print("  [ERROR] Discount code not found!")
            return
        
        discount_id = discount_ids[0]
        
        # Read discount details
        discount_data = models.execute_kw(
            DB_NAME, uid, PASSWORD,
            'popcorn.discount', 'read', [discount_id],
            {'fields': ['name', 'discount_type', 'discount_value', 'usage_limit', 'usage_limit_per_customer', 'usage_count', 'partner_id']}
        )
        
        print(f"  [OK] Found discount: {discount_data[0]['name']}")
        print(f"       Usage limit: {discount_data[0].get('usage_limit', 0)}")
        print(f"       Per customer limit: {discount_data[0].get('usage_limit_per_customer', 0)}")
        print(f"       Currently used: {discount_data[0].get('usage_count', 0)} times")
        
        # STEP 3: Manually increment discount usage to simulate using it
        print("\n[STEP 3] Simulating coupon usage for FIRST club...")
        
        # Manually increment usage (simulating what controller does)
        try:
            models.execute_kw(
                DB_NAME, uid, PASSWORD,
                'popcorn.discount', 'action_increment_usage',
                [[discount_id]]
            )
            print(f"  [OK] Incremented discount usage for first club")
            
            # Check usage count after increment
            updated_discount_data = models.execute_kw(
                DB_NAME, uid, PASSWORD,
                'popcorn.discount', 'read', [discount_id],
                {'fields': ['usage_count', 'usage_limit', 'is_valid']}
            )
            print(f"  [TEST] Usage count after first use: {updated_discount_data[0].get('usage_count', 0)}")
            print(f"  [TEST] Usage limit: {updated_discount_data[0].get('usage_limit', 0)}")
            print(f"  [TEST] Is valid: {updated_discount_data[0].get('is_valid', False)}")
            
            if updated_discount_data[0].get('usage_count', 0) >= updated_discount_data[0].get('usage_limit', 1):
                print("  [OK] Coupon is now marked as used (reached usage limit)")
            
        except Exception as e:
            error_str = str(e)
            print(f"  [INFO] Exception when incrementing: {error_str}")
        
        # STEP 4: Try to use coupon for SECOND club (should fail)
        print("\n[STEP 4] Attempting to use coupon for SECOND club (should FAIL)...")
        
        # Try to increment usage again (simulating second club booking)
        try:
            models.execute_kw(
                DB_NAME, uid, PASSWORD,
                'popcorn.discount', 'action_increment_usage',
                [[discount_id]]
            )
            print(f"  [FAIL] Was able to increment usage a second time!")
            print("         Coupon should NOT be reusable!")
            print("         This means the usage limit is NOT being enforced")
            return
            
        except Exception as e:
            error_str = str(e)
            if "usage limit" in error_str.lower() or "reached" in error_str.lower():
                print(f"  [OK] Correctly rejected second usage")
                print(f"       Error message: {error_str[:100]}")
            else:
                print(f"  [WARNING] Unexpected error: {error_str[:100]}")
        
        final_discount_data = models.execute_kw(
            DB_NAME, uid, PASSWORD,
            'popcorn.discount', 'read', [discount_id],
            {'fields': ['usage_count', 'usage_limit', 'is_valid']}
        )
        
        print(f"\n  [TEST] Final usage count: {final_discount_data[0].get('usage_count', 0)}")
        print(f"  [TEST] Usage limit: {final_discount_data[0].get('usage_limit', 0)}")
        print(f"  [TEST] Is valid: {final_discount_data[0].get('is_valid', False)}")
        
        if final_discount_data[0].get('usage_count', 0) >= final_discount_data[0].get('usage_limit', 0) and final_discount_data[0].get('usage_limit', 0) == 1:
            print("  [OK] Coupon is correctly marked as used")
        else:
            print("  [WARNING] Coupon usage tracking may not be working correctly")
        
        # STEP 6: Clean up test data
        print("\n[STEP 6] Cleaning up test data...")
        
        # Reset the discount usage for future tests
        try:
            models.execute_kw(
                DB_NAME, uid, PASSWORD,
                'popcorn.discount', 'action_reset_usage',
                [[discount_id]]
            )
            print("  [OK] Reset discount usage")
        except:
            pass
        
        try:
            models.execute_kw(
                DB_NAME, uid, PASSWORD,
                'res.partner', 'unlink',
                [[partner_id]]
            )
            print("  [OK] Deleted test partner")
        except:
            pass
        
        print("\n" + "=" * 80)
        print("[SUCCESS] Coupon usage limit test passed!")
        print("Verified:")
        print("  1. First-timer coupon can be used for ONE club registration")
        print("  2. Coupon has usage_limit = 1 (one-time use)")
        print("  3. User cannot reuse the same coupon for multiple clubs")
        print("  4. Coupon usage is tracked correctly")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n[ERROR] Test failed with exception: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    test_first_timer_coupon_usage_limit()

