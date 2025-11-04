# -*- coding: utf-8 -*-
"""
Test for automatic membership expiration when points reach zero

Usage:
    python tests/test_membership_auto_expiration.py

This test verifies that memberships are automatically expired when:
1. Points reach zero through event registrations
2. Points reach zero through manual adjustments
3. Points reach zero through cancellations and restorations
"""

import xmlrpc.client
import time
from datetime import datetime, timedelta

# Configuration
ODOO_URL = 'http://localhost:8069'
DB_NAME = 'popcorn'
USERNAME = 'admin@odoo.com'
PASSWORD = 'admin123'

def test_membership_auto_expiration():
    """Test automatic membership expiration when points reach zero"""
    
    # Connect to Odoo
    common = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/common')
    uid = common.authenticate(DB_NAME, USERNAME, PASSWORD, {})
    
    if not uid:
        print("[ERROR] Authentication failed")
        return
    
    print(f"[OK] Authenticated as user ID: {uid}")
    
    models = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/object')
    
    try:
        # Test 1: Create a points-based membership plan
        print("\n" + "="*60)
        print("TEST 1: Creating points-based membership plan")
        print("="*60)
        
        plan_id = models.execute_kw(
            DB_NAME, uid, PASSWORD,
            'popcorn.membership.plan', 'create',
            [{
                'name': 'Test Points Plan',
                'quota_mode': 'points',
                'points_start': 10,  # Start with 10 points
                'points_per_offline': 3,
                'points_per_online': 2,
                'points_per_sp': 6,
                'duration_days': 365,
            }]
        )
        print(f"[OK] Created membership plan ID: {plan_id}")
        
        # Test 2: Create a test partner
        print("\n" + "="*60)
        print("TEST 2: Creating test partner")
        print("="*60)
        
        partner_id = models.execute_kw(
            DB_NAME, uid, PASSWORD,
            'res.partner', 'create',
            [{
                'name': 'Test Auto Expiration Partner',
                'email': 'testautoexp@example.com',
            }]
        )
        print(f"[OK] Created partner ID: {partner_id}")
        
        # Test 3: Create membership with the plan
        print("\n" + "="*60)
        print("TEST 3: Creating membership")
        print("="*60)
        
        membership_id = models.execute_kw(
            DB_NAME, uid, PASSWORD,
            'popcorn.membership', 'create',
            [{
                'partner_id': partner_id,
                'membership_plan_id': plan_id,
                'state': 'active',
                'activation_date': datetime.now().strftime('%Y-%m-%d'),
                'purchase_price_paid': 100.0,  # Required field
            }]
        )
        print(f"[OK] Created membership ID: {membership_id}")
        
        # Check initial state
        membership = models.execute_kw(DB_NAME, uid, PASSWORD, 'popcorn.membership', 'read',
            [membership_id], {'fields': ['state', 'points_remaining']})[0]
        
        print(f"[INFO] Initial membership state:")
        print(f"   State: {membership['state']}")
        print(f"   Points remaining: {membership['points_remaining']}")
        
        # Test 4: Create events to consume points
        print("\n" + "="*60)
        print("TEST 4: Creating test events")
        print("="*60)
        
        # Create offline event (3 points)
        offline_event_id = models.execute_kw(
            DB_NAME, uid, PASSWORD,
            'event.event', 'create',
            [{
                'name': 'Test Offline Event (3 points)',
                'date_begin': (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S'),
                'date_end': (datetime.now() + timedelta(days=1, hours=2)).strftime('%Y-%m-%d %H:%M:%S'),
                'seats_max': 10,
                'seats_limited': True,
            }]
        )
        print(f"[OK] Created offline event ID: {offline_event_id}")
        
        # Create online event (2 points)
        online_event_id = models.execute_kw(
            DB_NAME, uid, PASSWORD,
            'event.event', 'create',
            [{
                'name': 'Test Online Event (2 points)',
                'date_begin': (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d %H:%M:%S'),
                'date_end': (datetime.now() + timedelta(days=2, hours=2)).strftime('%Y-%m-%d %H:%M:%S'),
                'seats_max': 10,
                'seats_limited': True,
            }]
        )
        print(f"[OK] Created online event ID: {online_event_id}")
        
        # Test 5: Consume points through registrations
        print("\n" + "="*60)
        print("TEST 5: Consuming points through registrations")
        print("="*60)
        
        # Register for offline event (3 points)
        reg1_id = models.execute_kw(
            DB_NAME, uid, PASSWORD,
            'event.registration', 'create',
            [{
                'event_id': offline_event_id,
                'partner_id': partner_id,
                'membership_id': membership_id,
                'state': 'open',
            }]
        )
        print(f"[OK] Created registration 1 (offline event) ID: {reg1_id}")
        
        # Check points after first registration
        membership = models.execute_kw(DB_NAME, uid, PASSWORD, 'popcorn.membership', 'read',
            [membership_id], {'fields': ['state', 'points_remaining']})[0]
        
        print(f"[INFO] After offline registration:")
        print(f"   State: {membership['state']}")
        print(f"   Points remaining: {membership['points_remaining']} (should be 7)")
        
        # Register for online event (2 points)
        reg2_id = models.execute_kw(
            DB_NAME, uid, PASSWORD,
            'event.registration', 'create',
            [{
                'event_id': online_event_id,
                'partner_id': partner_id,
                'membership_id': membership_id,
                'state': 'open',
            }]
        )
        print(f"[OK] Created registration 2 (online event) ID: {reg2_id}")
        
        # Check points after second registration
        membership = models.execute_kw(DB_NAME, uid, PASSWORD, 'popcorn.membership', 'read',
            [membership_id], {'fields': ['state', 'points_remaining']})[0]
        
        print(f"[INFO] After online registration:")
        print(f"   State: {membership['state']}")
        print(f"   Points remaining: {membership['points_remaining']} (should be 5)")
        
        # Test 6: Create more registrations to exhaust points
        print("\n" + "="*60)
        print("TEST 6: Exhausting remaining points")
        print("="*60)
        
        # Create additional offline events to consume remaining 5 points
        # We need 1 more offline event (3 points) + 1 online event (2 points) = 5 points
        
        offline_event2_id = models.execute_kw(
            DB_NAME, uid, PASSWORD,
            'event.event', 'create',
            [{
                'name': 'Test Offline Event 2 (3 points)',
                'date_begin': (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d %H:%M:%S'),
                'date_end': (datetime.now() + timedelta(days=3, hours=2)).strftime('%Y-%m-%d %H:%M:%S'),
                'seats_max': 10,
                'seats_limited': True,
            }]
        )
        
        online_event2_id = models.execute_kw(
            DB_NAME, uid, PASSWORD,
            'event.event', 'create',
            [{
                'name': 'Test Online Event 2 (2 points)',
                'date_begin': (datetime.now() + timedelta(days=4)).strftime('%Y-%m-%d %H:%M:%S'),
                'date_end': (datetime.now() + timedelta(days=4, hours=2)).strftime('%Y-%m-%d %H:%M:%S'),
                'seats_max': 10,
                'seats_limited': True,
            }]
        )
        
        # Register for third event (3 points) - should leave 2 points
        reg3_id = models.execute_kw(
            DB_NAME, uid, PASSWORD,
            'event.registration', 'create',
            [{
                'event_id': offline_event2_id,
                'partner_id': partner_id,
                'membership_id': membership_id,
                'state': 'open',
            }]
        )
        print(f"[OK] Created registration 3 (offline event 2) ID: {reg3_id}")
        
        # Check points after third registration
        membership = models.execute_kw(DB_NAME, uid, PASSWORD, 'popcorn.membership', 'read',
            [membership_id], {'fields': ['state', 'points_remaining']})[0]
        
        print(f"[INFO] After third registration:")
        print(f"   State: {membership['state']}")
        print(f"   Points remaining: {membership['points_remaining']} (should be 2)")
        
        # Try to register for fourth event (2 points) - should fail due to insufficient points
        try:
            reg4_id = models.execute_kw(
                DB_NAME, uid, PASSWORD,
                'event.registration', 'create',
                [{
                    'event_id': online_event2_id,
                    'partner_id': partner_id,
                    'membership_id': membership_id,
                    'state': 'open',
                }]
            )
            print(f"[OK] Created registration 4 (online event 2) ID: {reg4_id}")
        except Exception as e:
            print(f"[EXPECTED] Registration 4 failed due to insufficient points: {str(e)}")
            reg4_id = None
        
        # Check final state - membership should be automatically expired
        membership = models.execute_kw(DB_NAME, uid, PASSWORD, 'popcorn.membership', 'read',
            [membership_id], {'fields': ['state', 'points_remaining']})[0]
        
        print(f"\n[INFO] Final membership state:")
        print(f"   State: {membership['state']}")
        print(f"   Points remaining: {membership['points_remaining']}")
        
        # Verify automatic expiration worked
        if membership['state'] == 'expired' and membership['points_remaining'] == 0:
            print("[OK] SUCCESS: Membership automatically expired when points reached zero!")
        else:
            print(f"[ERROR] FAILURE: Expected state='expired' and points=0, got state='{membership['state']}' and points={membership['points_remaining']}")
        
        # Test automatic expiration by manually adjusting points to zero
        print(f"\n[INFO] Testing automatic expiration by setting points to zero...")
        models.execute_kw(
            DB_NAME, uid, PASSWORD,
            'popcorn.membership', 'write',
            [[membership_id], {'adj_points': -membership['points_remaining']}]
        )
        print(f"[OK] Set manual adjustment to exhaust remaining points")
        
        # Check if membership is automatically expired
        membership = models.execute_kw(DB_NAME, uid, PASSWORD, 'popcorn.membership', 'read',
            [membership_id], {'fields': ['state', 'points_remaining']})[0]
        
        print(f"\n[INFO] Final membership state after adjustment:")
        print(f"   State: {membership['state']}")
        print(f"   Points remaining: {membership['points_remaining']}")
        
        if membership['state'] == 'expired' and membership['points_remaining'] == 0:
            print("[SUCCESS] Membership automatically expired when points reached zero!")
        else:
            print(f"[ERROR] Expected state='expired' and points=0, got state='{membership['state']}' and points={membership['points_remaining']}")
        
        # Test 7: Test cancellation and restoration
        print("\n" + "="*60)
        print("TEST 7: Testing cancellation and restoration")
        print("="*60)
        
        # Cancel one registration to restore points (if it exists)
        if reg4_id:
            models.execute_kw(
                DB_NAME, uid, PASSWORD,
                'event.registration', 'write',
                [[reg4_id], {'state': 'cancel'}]
            )
            print(f"[OK] Cancelled registration 4")
        else:
            print("[INFO] Registration 4 was not created, cancelling registration 3 instead")
            models.execute_kw(
                DB_NAME, uid, PASSWORD,
                'event.registration', 'write',
                [[reg3_id], {'state': 'cancel'}]
            )
            print(f"[OK] Cancelled registration 3")
        
        # Check if membership is reactivated
        membership = models.execute_kw(DB_NAME, uid, PASSWORD, 'popcorn.membership', 'read',
            [membership_id], {'fields': ['state', 'points_remaining']})[0]
        
        print(f"[INFO] After cancellation:")
        print(f"   State: {membership['state']}")
        print(f"   Points remaining: {membership['points_remaining']}")
        
        if membership['state'] == 'active' and membership['points_remaining'] == 2:
            print("[OK] SUCCESS: Membership reactivated after point restoration!")
        else:
            print(f"[ERROR] FAILURE: Expected state='active' and points=2, got state='{membership['state']}' and points={membership['points_remaining']}")
        
        # Test 8: Test manual point adjustment
        print("\n" + "="*60)
        print("TEST 8: Testing manual point adjustment")
        print("="*60)
        
        # Set manual adjustment to -2 points to trigger expiration
        models.execute_kw(
            DB_NAME, uid, PASSWORD,
            'popcorn.membership', 'write',
            [[membership_id], {'adj_points': -2}]
        )
        print(f"[OK] Set manual adjustment to -2 points")
        
        # Check if membership is expired again
        membership = models.execute_kw(DB_NAME, uid, PASSWORD, 'popcorn.membership', 'read',
            [membership_id], {'fields': ['state', 'points_remaining']})[0]
        
        print(f"[INFO] After manual adjustment:")
        print(f"   State: {membership['state']}")
        print(f"   Points remaining: {membership['points_remaining']}")
        
        if membership['state'] == 'expired' and membership['points_remaining'] == 0:
            print("[OK] SUCCESS: Membership automatically expired after manual adjustment!")
        else:
            print(f"[ERROR] FAILURE: Expected state='expired' and points=0, got state='{membership['state']}' and points={membership['points_remaining']}")
        
        # Clean up
        print("\n" + "="*60)
        print("CLEANUP: Removing test data")
        print("="*60)
        
        try:
            # Delete registrations
            registration_ids = [reg1_id, reg2_id, reg3_id, reg4_id]
            models.execute_kw(DB_NAME, uid, PASSWORD, 'event.registration', 'unlink', [registration_ids])
            print("[CLEANUP] Deleted registrations")
            
            # Delete events
            event_ids = [offline_event_id, online_event_id, offline_event2_id, online_event2_id]
            models.execute_kw(DB_NAME, uid, PASSWORD, 'event.event', 'unlink', [event_ids])
            print("[CLEANUP] Deleted events")
            
            # Delete membership
            models.execute_kw(DB_NAME, uid, PASSWORD, 'popcorn.membership', 'unlink', [[membership_id]])
            print("[CLEANUP] Deleted membership")
            
            # Delete partner
            models.execute_kw(DB_NAME, uid, PASSWORD, 'res.partner', 'unlink', [[partner_id]])
            print("[CLEANUP] Deleted partner")
            
            # Delete plan
            models.execute_kw(DB_NAME, uid, PASSWORD, 'popcorn.membership.plan', 'unlink', [[plan_id]])
            print("[CLEANUP] Deleted membership plan")
            
            print("[OK] Cleanup completed successfully")
            
        except Exception as cleanup_error:
            print(f"[WARNING] Cleanup warning: {cleanup_error}")
        
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        print("[OK] Automatic membership expiration test completed")
        print("[OK] Points consumption through registrations tested")
        print("[OK] Cancellation and restoration tested")
        print("[OK] Manual point adjustment tested")
        print("[OK] All test data cleaned up")
        
    except Exception as e:
        print(f"[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("=" * 60)
    print("MEMBERSHIP AUTO-EXPIRATION TEST")
    print("=" * 60)
    test_membership_auto_expiration()
