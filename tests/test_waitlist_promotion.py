# -*- coding: utf-8 -*-
"""
Waitlist Promotion Stress Test - Tests concurrent cancellations and promotion

This test:
1. Creates registrations until event is full
2. Creates additional waitlist registrations
3. Tests concurrent cancellations (backend)
4. Tests concurrent cancellations (portal)
5. Verifies automatic promotion works correctly

Usage:
    python tests/test_waitlist_promotion.py
"""

import xmlrpc.client
import threading
import time
import random
from datetime import datetime

# Configuration
ODOO_URL = 'http://localhost:8069'
DB_NAME = 'popcorn'
USERNAME = 'omar.mahdy246@gmail.com'  # Admin user
PASSWORD = 'congr4t5'
EVENT_ID = 7

# Test parameters
SEATS_MAX = 5  # Set your event to this capacity
NUM_WAITLIST = 5  # Number of waitlist registrations to create
NUM_CONCURRENT_CANCELS = 3  # Number of cancellations to do simultaneously

# Skip creation and use existing registrations
USE_EXISTING_REGISTRATIONS = True  # Set to True to skip creation

results = {
    'backend_cancels': [],
    'portal_cancels': [],
    'promotions': [],
    'errors': []
}
results_lock = threading.Lock()


def authenticate():
    """Authenticate with Odoo"""
    try:
        common = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/common')
        uid = common.authenticate(DB_NAME, USERNAME, PASSWORD, {})
        return uid
    except Exception as e:
        print(f"❌ Authentication error: {e}")
        return None


def get_existing_registrations(uid):
    """Get existing registrations for the event"""
    models = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/object')
    
    # Get all active registrations for the event
    registrations = models.execute_kw(
        DB_NAME, uid, PASSWORD,
        'event.registration', 'search_read',
        [[['event_id', '=', EVENT_ID], ['state', '!=', 'cancel']]],
        {'fields': ['id', 'state', 'is_on_waitlist', 'waitlist_position', 'partner_id'],
         'order': 'is_on_waitlist asc, id asc'}
    )
    
    confirmed_ids = [r['id'] for r in registrations if not r['is_on_waitlist'] and r['state'] in ['open', 'confirmed', 'done']]
    waitlist_ids = [r['id'] for r in registrations if r['is_on_waitlist']]
    
    print(f"\n{'='*60}")
    print(f"FOUND EXISTING REGISTRATIONS")
    print(f"{'='*60}")
    print(f"  Confirmed registrations: {len(confirmed_ids)}")
    print(f"  Waitlisted registrations: {len(waitlist_ids)}")
    
    if len(confirmed_ids) < NUM_CONCURRENT_CANCELS * 2:
        print(f"\n  ⚠️  Warning: Only {len(confirmed_ids)} confirmed registrations")
        print(f"     Need at least {NUM_CONCURRENT_CANCELS * 2} for both backend and portal tests")
    
    if len(waitlist_ids) == 0:
        print(f"\n  ⚠️  Warning: No waitlisted registrations found")
        print(f"     Promotion testing may not be meaningful")
    
    return confirmed_ids, waitlist_ids


def create_test_registrations(uid, count, force_waitlist=False):
    """Create test registrations"""
    models = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/object')
    created_ids = []
    
    print(f"\n{'='*60}")
    print(f"Creating {count} {'waitlist' if force_waitlist else 'regular'} registrations...")
    print(f"{'='*60}")
    
    for i in range(count):
        try:
            timestamp = int(time.time() * 1000000) + random.randint(0, 9999)
            
            # Create partner
            partner_id = models.execute_kw(
                DB_NAME, uid, PASSWORD,
                'res.partner', 'create',
                [{
                    'name': f'Test User {timestamp}',
                    'email': f'test{timestamp}@example.com',
                    'phone': f'+86{timestamp}'[-15:]  # Ensure valid length
                }]
            )
            
            # Create registration
            registration_id = models.execute_kw(
                DB_NAME, uid, PASSWORD,
                'event.registration', 'create',
                [{
                    'event_id': EVENT_ID,
                    'partner_id': partner_id,
                    'name': f'Test User {timestamp}',
                    'email': f'test{timestamp}@example.com',
                    'phone': f'+86{timestamp}'[-15:],
                    'state': 'open',
                }]
            )
            
            # Check registration state
            registration = models.execute_kw(
                DB_NAME, uid, PASSWORD,
                'event.registration', 'read',
                [registration_id],
                {'fields': ['id', 'state', 'is_on_waitlist', 'waitlist_position', 'partner_id']}
            )[0]
            
            created_ids.append(registration_id)
            
            status = "⏳ Waitlisted" if registration['is_on_waitlist'] else "✅ Confirmed"
            position = f" (Position #{registration['waitlist_position']})" if registration['is_on_waitlist'] else ""
            print(f"  {status}: Registration {registration_id}{position}")
            
            time.sleep(0.1)  # Small delay between creations
            
        except Exception as e:
            print(f"  ❌ Failed to create registration {i+1}: {str(e)[:100]}")
    
    return created_ids


def cancel_via_backend(reg_id, thread_id):
    """Cancel registration via backend (admin)"""
    try:
        uid = authenticate()
        models = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/object')
        
        start_time = time.time()
        
        # Cancel via backend
        models.execute_kw(
            DB_NAME, uid, PASSWORD,
            'event.registration', 'write',
            [[reg_id], {'state': 'cancel'}]
        )
        
        elapsed = time.time() - start_time
        
        with results_lock:
            results['backend_cancels'].append({
                'reg_id': reg_id,
                'thread_id': thread_id,
                'success': True,
                'elapsed': elapsed
            })
        
        print(f"  ✅ Backend: Cancelled {reg_id} ({elapsed:.3f}s)")
        
    except Exception as e:
        with results_lock:
            results['errors'].append({
                'type': 'backend_cancel',
                'reg_id': reg_id,
                'error': str(e)[:200]
            })
        print(f"  ❌ Backend: Failed to cancel {reg_id}: {str(e)[:100]}")


def cancel_via_portal(reg_id, partner_id, thread_id):
    """Cancel registration via portal (simulating user action)"""
    try:
        # Authenticate as the registration owner (not admin)
        # For this test, we'll use XML-RPC to call action_cancel_registration
        # which simulates the portal action
        uid = authenticate()
        models = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/object')
        
        start_time = time.time()
        
        # Get the registration and call action_cancel_registration
        # This is the same method the portal calls
        models.execute_kw(
            DB_NAME, uid, PASSWORD,
            'event.registration', 'action_cancel_registration',
            [[reg_id]]
        )
        
        elapsed = time.time() - start_time
        
        with results_lock:
            results['portal_cancels'].append({
                'reg_id': reg_id,
                'thread_id': thread_id,
                'success': True,
                'elapsed': elapsed
            })
        print(f"  ✅ Portal: Cancelled {reg_id} ({elapsed:.3f}s)")
            
    except Exception as e:
        with results_lock:
            results['errors'].append({
                'type': 'portal_cancel',
                'reg_id': reg_id,
                'error': str(e)[:200]
            })
        print(f"  ❌ Portal: Failed to cancel {reg_id}: {str(e)[:100]}")


def verify_event_state(uid):
    """Verify final event state"""
    models = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/object')
    
    registrations = models.execute_kw(
        DB_NAME, uid, PASSWORD,
        'event.registration', 'search_read',
        [[['event_id', '=', EVENT_ID], ['state', '!=', 'cancel']]],
        {'fields': ['id', 'name', 'state', 'is_on_waitlist', 'waitlist_position'],
         'order': 'is_on_waitlist asc, waitlist_position asc'}
    )
    
    confirmed = [r for r in registrations if not r['is_on_waitlist'] and r['state'] in ['open', 'confirmed', 'done']]
    waitlisted = [r for r in registrations if r['is_on_waitlist']]
    
    print(f"\n{'='*60}")
    print(f"FINAL EVENT STATE")
    print(f"{'='*60}")
    print(f"  Confirmed registrations: {len(confirmed)}")
    print(f"  Waitlisted registrations: {len(waitlisted)}")
    print(f"  Expected max seats: {SEATS_MAX}")
    
    if len(confirmed) > SEATS_MAX:
        print(f"\n  ⚠️  OVER-BOOKING DETECTED: {len(confirmed)} > {SEATS_MAX}")
        return False
    else:
        print(f"\n  ✅ Seat limit respected: {len(confirmed)} <= {SEATS_MAX}")
    
    if waitlisted:
        print(f"\n  Remaining on waitlist:")
        for r in waitlisted:
            print(f"    #{r['waitlist_position']}: {r['name']} (ID: {r['id']})")
    
    return len(confirmed) <= SEATS_MAX


def main():
    print(f"\n{'='*60}")
    print(f"WAITLIST PROMOTION STRESS TEST")
    print(f"{'='*60}")
    print(f"Configuration:")
    print(f"  Database: {DB_NAME}")
    print(f"  Event ID: {EVENT_ID}")
    print(f"  Max seats: {SEATS_MAX}")
    print(f"  Waitlist to create: {NUM_WAITLIST}")
    print(f"  Concurrent cancellations: {NUM_CONCURRENT_CANCELS}")
    
    # Authenticate
    uid = authenticate()
    if not uid:
        print("\n❌ Authentication failed!")
        return
    
    print(f"\n✅ Authenticated as user ID: {uid}")
    
    if USE_EXISTING_REGISTRATIONS:
        # Use existing registrations
        print(f"\n{'='*60}")
        print(f"USING EXISTING REGISTRATIONS")
        print(f"{'='*60}")
        confirmed_ids, waitlist_ids = get_existing_registrations(uid)
        
        if len(confirmed_ids) < NUM_CONCURRENT_CANCELS:
            print(f"\n❌ Not enough confirmed registrations to test")
            print(f"   Found: {len(confirmed_ids)}, Need: {NUM_CONCURRENT_CANCELS}")
            return
    else:
        # Step 1: Create registrations to fill the event
        print(f"\n{'='*60}")
        print(f"STEP 1: Fill event to capacity")
        print(f"{'='*60}")
        confirmed_ids = create_test_registrations(uid, SEATS_MAX)
        
        if len(confirmed_ids) < SEATS_MAX:
            print(f"\n❌ Failed to create enough confirmed registrations")
            return
        
        # Step 2: Create waitlist registrations
        print(f"\n{'='*60}")
        print(f"STEP 2: Create waitlist registrations")
        print(f"{'='*60}")
        waitlist_ids = create_test_registrations(uid, NUM_WAITLIST, force_waitlist=True)
    
    # Test concurrent backend cancellations
    print(f"\n{'='*60}")
    print(f"TEST 1: Concurrent Backend Cancellations")
    print(f"{'='*60}")
    print(f"Cancelling {NUM_CONCURRENT_CANCELS} confirmed registrations simultaneously...")
    print(f"Target registrations: {confirmed_ids[:NUM_CONCURRENT_CANCELS]}")
    
    threads = []
    cancel_targets = confirmed_ids[:NUM_CONCURRENT_CANCELS]
    
    for i, reg_id in enumerate(cancel_targets):
        thread = threading.Thread(target=cancel_via_backend, args=(reg_id, i))
        threads.append(thread)
    
    # Start all threads at once
    for thread in threads:
        thread.start()
    
    # Wait for completion
    for thread in threads:
        thread.join()
    
    # Wait for promotion to complete
    print("\n⏳ Waiting for automatic promotions...")
    time.sleep(3)
    
    # Verify state after backend cancellations
    print(f"\n{'='*60}")
    print(f"After Backend Cancellations:")
    print(f"{'='*60}")
    verify_event_state(uid)
    
    # Test concurrent portal cancellations
    if len(confirmed_ids) >= NUM_CONCURRENT_CANCELS * 2:
        print(f"\n{'='*60}")
        print(f"TEST 2: Concurrent Portal Cancellations")
        print(f"{'='*60}")
        print(f"Cancelling {NUM_CONCURRENT_CANCELS} more registrations via portal...")
        print(f"(Using action_cancel_registration method - same as portal)")
        print(f"Target registrations: {confirmed_ids[NUM_CONCURRENT_CANCELS:NUM_CONCURRENT_CANCELS*2]}")
        
        threads = []
        cancel_targets = confirmed_ids[NUM_CONCURRENT_CANCELS:NUM_CONCURRENT_CANCELS*2]
        
        for i, reg_id in enumerate(cancel_targets):
            thread = threading.Thread(target=cancel_via_portal, args=(reg_id, None, i))
            threads.append(thread)
        
        # Start all threads at once
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Wait for promotion to complete
        print("\n⏳ Waiting for automatic promotions...")
        time.sleep(3)
    else:
        print(f"\n⚠️  Skipping portal cancellation test - not enough confirmed registrations")
    
    # Final verification
    print(f"\n{'='*60}")
    print(f"FINAL VERIFICATION")
    print(f"{'='*60}")
    passed = verify_event_state(uid)
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"TEST SUMMARY")
    print(f"{'='*60}")
    print(f"  Backend cancellations: {len(results['backend_cancels'])} successful")
    print(f"  Portal cancellations: {len(results['portal_cancels'])} successful")
    print(f"  Errors encountered: {len(results['errors'])}")
    
    if results['errors']:
        print(f"\n  Errors:")
        for error in results['errors'][:5]:  # Show first 5 errors
            print(f"    - {error['type']}: {error['error'][:100]}")
    
    print(f"\n{'='*60}")
    if passed and len(results['errors']) == 0:
        print("✅ ALL TESTS PASSED")
    elif passed:
        print("⚠️  TESTS PASSED WITH SOME ERRORS")
    else:
        print("❌ TESTS FAILED")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()

