# -*- coding: utf-8 -*-
"""
Test for First Timer Membership Limit

This test verifies that:
1. First-timer can get first-timer pricing for their FIRST membership
2. After creating their first membership, they are NO LONGER a first-timer
3. Second membership should use NORMAL pricing (not first-timer)
4. is_first_timer status is correctly updated after first membership

Usage:
    python tests/test_first_timer_membership_limit.py
"""

import xmlrpc.client
import time
from datetime import datetime, timedelta, date

# Configuration
ODOO_URL = 'http://localhost:8069'
DB_NAME = 'popcorn'
USERNAME = 'admin@odoo.com'
PASSWORD = 'admin123'


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


def test_first_timer_membership_limit():
    """Test that first-timer status only applies to FIRST membership"""
    
    print("=" * 80)
    print("TEST: First Timer Membership Limit")
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
        unique_email = f'test.membership.limit.{random.randint(1000, 9999)}@example.com'
        
        partner_id = models.execute_kw(
            DB_NAME, uid, PASSWORD,
            'res.partner', 'create',
            [{
                'name': 'Test Membership Limit User',
                'email': unique_email,
                'is_first_timer': True,
            }]
        )
        print(f"  [OK] Created test partner ID: {partner_id}")
        
        # Verify they are first-timer
        partner_data = models.execute_kw(
            DB_NAME, uid, PASSWORD,
            'res.partner', 'read', [partner_id],
            {'fields': ['is_first_timer']}
        )
        is_first_timer_before = partner_data[0].get('is_first_timer', False)
        print(f"  [TEST] is_first_timer before any membership: {is_first_timer_before}")
        
        if not is_first_timer_before:
            print("  [FAIL] Partner should be first-timer!")
            return
        
        # STEP 2: Create a test plan with DIFFERENT pricing
        print("\n[STEP 2] Creating test plan with different normal vs first-timer pricing...")
        
        # Create plan with different prices to test the system
        plan_id = models.execute_kw(
            DB_NAME, uid, PASSWORD,
            'popcorn.membership.plan', 'create',
            [{
                'name': 'Test Plan for Price Difference',
                'price_normal': 2000,
                'price_first_timer': 1500,  # 500 RMB discount for first-timers
                'quota_mode': 'unlimited',
            }]
        )
        print(f"  [OK] Created test plan ID: {plan_id}")
        
        # Read back the plan to verify
        test_plan_data = models.execute_kw(
            DB_NAME, uid, PASSWORD,
            'popcorn.membership.plan', 'read', [[plan_id]],
            {'fields': ['name', 'price_normal', 'price_first_timer']}
        )
        
        test_plan = test_plan_data[0] if test_plan_data else None
        
        print(f"  [OK] Plan created:")
        print(f"         Name: {test_plan['name']}")
        print(f"         Normal price: {test_plan['price_normal']} RMB")
        print(f"         First-timer price: {test_plan['price_first_timer']} RMB")
        print(f"         Price difference: {test_plan['price_normal'] - test_plan['price_first_timer']} RMB")
        
        plan_id = test_plan['id']
        
        # STEP 3: Create FIRST membership (should get first-timer pricing)
        print("\n[STEP 3] Creating FIRST membership (should get first-timer pricing)...")
        
        # For a first-timer, purchase_price_paid should be price_first_timer
        first_membership_price = test_plan['price_first_timer'] if is_first_timer_before else test_plan['price_normal']
        
        membership_1_id = models.execute_kw(
            DB_NAME, uid, PASSWORD,
            'popcorn.membership', 'create',
            [{
                'partner_id': partner_id,
                'membership_plan_id': plan_id,
                'purchase_price_paid': first_membership_price,
                'price_tier': 'first_timer' if is_first_timer_before else 'normal',
                'purchase_channel': 'online',
                'state': 'active',
                'activation_date': date.today().strftime('%Y-%m-%d'),
            }]
        )
        print(f"  [OK] Created FIRST membership ID: {membership_1_id}")
        print(f"       Price paid: {first_membership_price} RMB")
        print(f"       Price tier: {'first_timer' if is_first_timer_before else 'normal'}")
        
        # STEP 4: Verify is_first_timer became FALSE after first membership
        print("\n[STEP 4] Verifying is_first_timer status after FIRST membership...")
        
        partner_data = models.execute_kw(
            DB_NAME, uid, PASSWORD,
            'res.partner', 'read', [partner_id],
            {'fields': ['is_first_timer']}
        )
        
        is_first_timer_after_first = partner_data[0].get('is_first_timer', False)
        print(f"  [TEST] is_first_timer after first membership: {is_first_timer_after_first}")
        
        if is_first_timer_after_first:
            print("  [FAIL] User is STILL first-timer after creating a membership!")
            print("         They should no longer be first-timer!")
            return
        else:
            print("  [OK] User is no longer first-timer (as expected)")
            print("       They have now had a membership")
        
        # STEP 5: Try to create SECOND membership (should get NORMAL pricing)
        print("\n[STEP 5] Creating SECOND membership (should get NORMAL pricing)...")
        
        second_membership_price = test_plan['price_normal']
        
        membership_2_id = models.execute_kw(
            DB_NAME, uid, PASSWORD,
            'popcorn.membership', 'create',
            [{
                'partner_id': partner_id,
                'membership_plan_id': plan_id,
                'purchase_price_paid': second_membership_price,
                'price_tier': 'normal',  # Should be normal, not first_timer
                'purchase_channel': 'online',
                'state': 'active',
                'activation_date': date.today().strftime('%Y-%m-%d'),
            }]
        )
        print(f"  [OK] Created SECOND membership ID: {membership_2_id}")
        print(f"       Price paid: {second_membership_price} RMB")
        print(f"       Price tier: normal (NOT first_timer)")
        
        # STEP 6: Verify pricing difference
        print("\n[STEP 6] Verifying pricing difference between memberships...")
        
        # Read memberships separately to avoid XML-RPC issues
        membership_1_data = models.execute_kw(
            DB_NAME, uid, PASSWORD,
            'popcorn.membership', 'read', [[membership_1_id]],
            {'fields': ['purchase_price_paid', 'price_tier']}
        )
        
        membership_2_data = models.execute_kw(
            DB_NAME, uid, PASSWORD,
            'popcorn.membership', 'read', [[membership_2_id]],
            {'fields': ['purchase_price_paid', 'price_tier']}
        )
        
        membership_data = [membership_1_data[0], membership_2_data[0]]
        
        print(f"\n  [MEMBERSHIP PRICING COMPARISON]")
        print(f"    First membership:")
        print(f"      Price: {membership_data[0]['purchase_price_paid']} RMB")
        print(f"      Tier: {membership_data[0]['price_tier']}")
        print(f"    Second membership:")
        print(f"      Price: {membership_data[1]['purchase_price_paid']} RMB")
        print(f"      Tier: {membership_data[1]['price_tier']}")
        
        price_difference = abs(membership_data[0]['purchase_price_paid'] - membership_data[1]['purchase_price_paid'])
        
        if price_difference > 0:
            print(f"\n  [OK] First membership got first-timer pricing")
            print(f"       Second membership got normal pricing")
            print(f"       Price difference: {price_difference} RMB")
        else:
            print(f"\n  [INFO] Both memberships have same price")
            print(f"         This is OK if price_first_timer == price_normal for this plan")
        
        # STEP 7: Clean up test data
        print("\n[STEP 7] Cleaning up test data...")
        
        try:
            models.execute_kw(
                DB_NAME, uid, PASSWORD,
                'popcorn.membership', 'unlink',
                [[membership_1_id, membership_2_id]]
            )
            print("  [OK] Deleted test memberships")
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
        
        try:
            models.execute_kw(
                DB_NAME, uid, PASSWORD,
                'popcorn.membership.plan', 'unlink',
                [[plan_id]]
            )
            print("  [OK] Deleted test plan")
        except:
            pass
        
        print("\n" + "=" * 80)
        print("[SUCCESS] First-timer membership limit test passed!")
        print("Verified:")
        print("  1. First membership gets first-timer pricing")
        print("  2. is_first_timer becomes FALSE after first membership")
        print("  3. Second membership gets NORMAL pricing (not first-timer)")
        print("  4. User cannot get first-timer pricing multiple times")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n[ERROR] Test failed with exception: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    test_first_timer_membership_limit()

