# -*- coding: utf-8 -*-
"""
Stress test for concurrent event registrations and waitlist promotion

Usage:
    python tests/test_concurrent_registrations.py

This will create multiple concurrent registration attempts to test:
1. Seat limit enforcement
2. Waitlist functionality
3. Race condition handling
"""

import xmlrpc.client
import threading
import time
from datetime import datetime

# Configuration
ODOO_URL = 'http://localhost:8069'
DB_NAME = 'popcorn'  # Change to your database name
USERNAME = 'omar.mahdy246@gmail.com'  # Change as needed
PASSWORD = 'congr4t5'  # Change as needed
EVENT_ID = 7  # Change to your test event ID

# Test parameters
NUM_CONCURRENT_REQUESTS = 10  # Number of simultaneous registration attempts
SEATS_MAX = 5  # Set your event to this capacity for testing

results = []
results_lock = threading.Lock()


def authenticate():
    """Authenticate with Odoo"""
    try:
        common = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/common')
        uid = common.authenticate(DB_NAME, USERNAME, PASSWORD, {})
        if not uid:
            print(f"Authentication failed. Please check:")
            print(f"  - Database name: '{DB_NAME}'")
            print(f"  - Username: '{USERNAME}'")
            print(f"  - Password: (check if correct)")
            print(f"  - Odoo URL: '{ODOO_URL}'")
        return uid
    except Exception as e:
        print(f"Error during authentication: {e}")
        return None


def create_registration(thread_id, uid):
    """Create a registration for the event"""
    models = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/object')
    
    start_time = time.time()
    try:
        # Create a partner for this test
        partner_id = models.execute_kw(
            DB_NAME, uid, PASSWORD,
            'res.partner', 'create',
            [{
                'name': f'Test User {thread_id} - {datetime.now().strftime("%H:%M:%S.%f")}',
                'email': f'test{thread_id}_{int(time.time())}@example.com',
                'phone': f'1234567890{thread_id:02d}'
            }]
        )
        
        # Create registration
        registration_id = models.execute_kw(
            DB_NAME, uid, PASSWORD,
            'event.registration', 'create',
            [{
                'event_id': EVENT_ID,
                'partner_id': partner_id,
                'name': f'Test User {thread_id}',
                'email': f'test{thread_id}_{int(time.time())}@example.com',
                'phone': f'1234567890{thread_id:02d}',
                'state': 'open',
            }]
        )
        
        # Read back the registration to check state and waitlist status
        registration = models.execute_kw(
            DB_NAME, uid, PASSWORD,
            'event.registration', 'read',
            [registration_id],
            {'fields': ['id', 'name', 'state', 'is_on_waitlist', 'waitlist_position']}
        )[0]
        
        elapsed = time.time() - start_time
        
        with results_lock:
            results.append({
                'thread_id': thread_id,
                'success': True,
                'registration_id': registration_id,
                'state': registration['state'],
                'is_on_waitlist': registration['is_on_waitlist'],
                'waitlist_position': registration.get('waitlist_position', 0),
                'elapsed': elapsed
            })
            
        print(f"✓ Thread {thread_id}: Registration {registration_id} created - "
              f"State: {registration['state']}, "
              f"Waitlist: {registration['is_on_waitlist']}, "
              f"Position: {registration.get('waitlist_position', 'N/A')} "
              f"({elapsed:.3f}s)")
        
    except Exception as e:
        elapsed = time.time() - start_time
        with results_lock:
            results.append({
                'thread_id': thread_id,
                'success': False,
                'error': str(e),
                'elapsed': elapsed
            })
        print(f"✗ Thread {thread_id}: Failed - {str(e)} ({elapsed:.3f}s)")


def test_concurrent_cancellations(uid, registration_ids):
    """Test concurrent cancellations to trigger waitlist promotion"""
    print(f"\n--- Testing Concurrent Cancellations ---")
    
    models = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/object')
    cancel_results = []
    
    def cancel_registration(reg_id, thread_id):
        try:
            start_time = time.time()
            models.execute_kw(
                DB_NAME, uid, PASSWORD,
                'event.registration', 'write',
                [[reg_id], {'state': 'cancel'}]
            )
            elapsed = time.time() - start_time
            print(f"✓ Cancelled registration {reg_id} ({elapsed:.3f}s)")
            cancel_results.append({'success': True, 'reg_id': reg_id})
        except Exception as e:
            print(f"✗ Failed to cancel {reg_id}: {e}")
            cancel_results.append({'success': False, 'reg_id': reg_id, 'error': str(e)})
    
    # Cancel first N registrations concurrently
    threads = []
    for i, reg_id in enumerate(registration_ids[:3]):  # Cancel 3 at once
        thread = threading.Thread(target=cancel_registration, args=(reg_id, i))
        threads.append(thread)
    
    # Start all cancellation threads at once
    for thread in threads:
        thread.start()
    
    # Wait for all to complete
    for thread in threads:
        thread.join()
    
    return cancel_results


def verify_results(uid):
    """Verify the final state of the event"""
    models = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/object')
    
    # Get all registrations for the event
    registrations = models.execute_kw(
        DB_NAME, uid, PASSWORD,
        'event.registration', 'search_read',
        [[['event_id', '=', EVENT_ID]]],
        {'fields': ['id', 'name', 'state', 'is_on_waitlist', 'waitlist_position']}
    )
    
    confirmed = [r for r in registrations if r['state'] in ['open', 'confirmed', 'done'] and not r['is_on_waitlist']]
    waitlisted = [r for r in registrations if r['is_on_waitlist']]
    cancelled = [r for r in registrations if r['state'] == 'cancel']
    
    print(f"\n=== Final Event State ===")
    print(f"Total registrations: {len(registrations)}")
    print(f"Confirmed (not on waitlist): {len(confirmed)}")
    print(f"On waitlist: {len(waitlisted)}")
    print(f"Cancelled: {len(cancelled)}")
    print(f"\nExpected max confirmed: {SEATS_MAX}")
    
    if len(confirmed) > SEATS_MAX:
        print(f"⚠️  WARNING: Over-booking detected! {len(confirmed)} > {SEATS_MAX}")
        return False
    else:
        print(f"✓ Seat limit respected: {len(confirmed)} <= {SEATS_MAX}")
        return True


def main():
    print("=== Concurrent Registration Stress Test ===\n")
    print(f"Configuration:")
    print(f"  Database: {DB_NAME}")
    print(f"  Event ID: {EVENT_ID}")
    print(f"  Concurrent requests: {NUM_CONCURRENT_REQUESTS}")
    print(f"  Expected seat limit: {SEATS_MAX}")
    print(f"\n--- Starting Test ---\n")
    
    # Authenticate
    uid = authenticate()
    if not uid:
        print("Authentication failed!")
        return
    
    print(f"Authenticated as user ID: {uid}\n")
    
    # Create concurrent registration threads
    threads = []
    start_time = time.time()
    
    for i in range(NUM_CONCURRENT_REQUESTS):
        thread = threading.Thread(target=create_registration, args=(i, uid))
        threads.append(thread)
    
    # Start all threads at once
    print(f"Starting {NUM_CONCURRENT_REQUESTS} concurrent registration attempts...\n")
    for thread in threads:
        thread.start()
    
    # Wait for all threads to complete
    for thread in threads:
        thread.join()
    
    total_time = time.time() - start_time
    
    # Print results
    print(f"\n--- Registration Test Complete ({total_time:.3f}s total) ---\n")
    
    successful = [r for r in results if r['success']]
    failed = [r for r in results if not r['success']]
    
    print(f"Successful: {len(successful)}/{NUM_CONCURRENT_REQUESTS}")
    print(f"Failed: {len(failed)}/{NUM_CONCURRENT_REQUESTS}")
    
    if successful:
        confirmed_regs = [r for r in successful if not r['is_on_waitlist']]
        waitlisted_regs = [r for r in successful if r['is_on_waitlist']]
        
        print(f"  - Confirmed: {len(confirmed_regs)}")
        print(f"  - Waitlisted: {len(waitlisted_regs)}")
    
    # Verify final state
    time.sleep(1)  # Give time for all database operations to complete
    passed = verify_results(uid)
    
    # Test concurrent cancellations if we have confirmed registrations
    if successful:
        confirmed_ids = [r['registration_id'] for r in successful if not r['is_on_waitlist']]
        if len(confirmed_ids) >= 3:
            print("\n--- Testing Waitlist Promotion ---")
            time.sleep(1)
            test_concurrent_cancellations(uid, confirmed_ids)
            time.sleep(2)  # Give time for promotions to process
            verify_results(uid)
    
    print(f"\n{'='*50}")
    if passed:
        print("✓ STRESS TEST PASSED")
    else:
        print("✗ STRESS TEST FAILED")
    print(f"{'='*50}\n")


if __name__ == '__main__':
    main()

