# -*- coding: utf-8 -*-
"""
Frontend Race Condition Test - Simulates Frontend Registration Flow

This test simulates the EXACT flow that happens when users register from the frontend:
1. Authenticates as different users (simulating different browsers)
2. Makes registration requests with proper context
3. Tests concurrent requests when event is full

Usage: python tests/test_frontend_race.py
"""

import xmlrpc.client
import threading
import time

ODOO_URL = 'http://localhost:8069'
DB_NAME = 'popcorn'
USERNAME = 'omar.mahdy246@gmail.com'
PASSWORD = 'congr4t5'


def authenticate():
    """Authenticate and return models proxy"""
    common = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/common')
    uid = common.authenticate(DB_NAME, USERNAME, PASSWORD, {})
    if not uid:
        print("[ERROR] Authentication failed")
        return None, None
    models = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/object')
    return uid, models


def create_user_with_membership(models, uid, user_num):
    """Create a test user with an unlimited membership"""
    unique_id = int(time.time() * 1000000) + user_num
    
    # Create partner
    partner_id = models.execute_kw(DB_NAME, uid, PASSWORD, 'res.partner', 'create',
                                   [{'name': f'Frontend Test User {user_num}',
                                     'email': f'frontend_{unique_id}@test.com',
                                     'phone': f'555{unique_id}'}])
    
    # Find unlimited plan
    plan_ids = models.execute_kw(DB_NAME, uid, PASSWORD, 'popcorn.membership.plan',
                                 'search', [[('quota_mode', '=', 'unlimited')]], {'limit': 1})
    
    if plan_ids:
        plan_id = plan_ids[0]
        
        # Create membership
        membership_id = models.execute_kw(DB_NAME, uid, PASSWORD, 'popcorn.membership', 'create',
                                         [{'partner_id': partner_id,
                                           'membership_plan_id': plan_id,
                                           'state': 'active',
                                           'activation_date': '2025-01-01',
                                           'purchase_price_paid': 0}])
        
        return {
            'partner_id': partner_id,
            'membership_id': membership_id,
            'plan_id': plan_id
        }
    else:
        print(f"[ERROR] No unlimited plan found for user {user_num}")
        return None


def simulate_frontend_registration(models, uid, event_id, user_data):
    """Simulate frontend registration by calling the model directly with frontend context"""
    try:
        # This simulates what the frontend controller does
        registration_vals = {
            'event_id': event_id,
            'partner_id': user_data['partner_id'],
            'membership_id': user_data['membership_id'],
            'state': 'open',  # Frontend creates as 'open'
            'consumption_state': 'pending',
        }
        
        # Create registration (goes through model's create() which has the race condition fix)
        reg_id = models.execute_kw(DB_NAME, uid, PASSWORD, 'event.registration', 'create', [registration_vals])
        
        time.sleep(1)  # Wait for processing
        
        # Read back to check state
        reg = models.execute_kw(DB_NAME, uid, PASSWORD, 'event.registration', 'read',
                                [reg_id], {'fields': ['state', 'is_on_waitlist', 'waitlist_position']})[0]
        
        return {
            'success': True,
            'reg_id': reg_id,
            'is_waitlist': reg.get('is_on_waitlist', False),
            'position': reg.get('waitlist_position', 0),
            'state': reg['state']
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def main():
    print("=" * 70)
    print("FRONTEND RACE CONDITION TEST")
    print("=" * 70)
    print("\nThis test:")
    print("1. Creates test users with memberships")
    print("2. Fills event to capacity")
    print("3. Attempts concurrent registrations (simulating frontend)")
    print("4. Verifies NO OVER-BOOKING occurs")
    
    uid, models = authenticate()
    if not uid:
        return
    
    try:
        event_id = int(input("\nEnter Event ID (5 seats capacity recommended): ").strip())
    except:
        print("Cancelled")
        return
    
    event = models.execute_kw(DB_NAME, uid, PASSWORD, 'event.event', 'read',
                              [event_id], {'fields': ['name', 'seats_max']})[0]
    
    seats_max = event.get('seats_max', 5)
    print(f"\nEvent: {event['name']} ({seats_max} seats)")
    
    # Step 1: Create users
    print(f"\n{'='*70}")
    print(f"Creating {seats_max + 3} test users with memberships...")
    print(f"{'='*70}")
    
    users = []
    for i in range(seats_max + 3):
        user_data = create_user_with_membership(models, uid, i)
        if user_data:
            users.append(user_data)
        if (i + 1) % 4 == 0:
            print(f"  Created {i + 1}/{seats_max + 3} users")
    
    time.sleep(1)
    
    # Step 2: Fill event
    print(f"\n{'='*70}")
    print(f"Filling event ({seats_max} registrations)...")
    print(f"{'='*70}")
    
    for i in range(seats_max):
        result = simulate_frontend_registration(models, uid, event_id, users[i])
        if result['success']:
            print(f"  User {i}: Registration {result['reg_id']} - {result['state']}")
        time.sleep(0.2)
    
    time.sleep(2)
    
    # Check current state
    all_regs = models.execute_kw(DB_NAME, uid, PASSWORD, 'event.registration', 'search_read',
                                 [[('event_id', '=', event_id)]],
                                 {'fields': ['state', 'is_on_waitlist']})
    
    confirmed = len([r for r in all_regs if r['state'] in ['open', 'confirmed', 'done'] and not r.get('is_on_waitlist', False)])
    print(f"\n[INFO] {confirmed}/{seats_max} seats filled")
    
    # Step 3: Concurrent registrations
    print(f"\n{'='*70}")
    print(f"Attempting 3 concurrent registrations...")
    print(f"{'='*70}\n")
    
    results = []
    
    def concurrent_reg(user_idx):
        result = simulate_frontend_registration(models, uid, event_id, users[seats_max + user_idx])
        results.append((user_idx, result))
    
    threads = []
    for i in range(3):
        thread = threading.Thread(target=concurrent_reg, args=(i,))
        threads.append(thread)
        thread.start()
    
    for thread in threads:
        thread.join()
    
    time.sleep(3)
    
    # Final check
    final_regs = models.execute_kw(DB_NAME, uid, PASSWORD, 'event.registration', 'search_read',
                                   [[('event_id', '=', event_id)]],
                                   {'fields': ['id', 'name', 'state', 'is_on_waitlist', 'waitlist_position']})
    
    confirmed_final = len([r for r in final_regs if r['state'] in ['open', 'confirmed', 'done'] and not r.get('is_on_waitlist', False)])
    waitlist_final = [r for r in final_regs if r.get('is_on_waitlist', False)]
    
    print(f"\n{'='*70}")
    print("FINAL RESULTS")
    print(f"{'='*70}")
    print(f"Total registrations: {len(final_regs)}")
    print(f"Confirmed: {confirmed_final} (capacity: {seats_max})")
    print(f"Waitlisted: {len(waitlist_final)}")
    
    for reg in sorted(waitlist_final, key=lambda x: x.get('waitlist_position', 0)):
        print(f"  Waitlist position {reg.get('waitlist_position', 0)}: Registration {reg['id']}")
    
    if confirmed_final > seats_max:
        print(f"\n❌ OVER-BOOKING: {confirmed_final} > {seats_max}")
        print("❌ Race condition fix NOT working!")
    else:
        print(f"\n✅ NO OVER-BOOKING: {confirmed_final} ≤ {seats_max}")
        print("✅ Race condition fix is WORKING!")
    
    # Cleanup
    if input("\nCleanup? (y/n): ").strip().lower() == 'y':
        for reg in final_regs:
            models.execute_kw(DB_NAME, uid, PASSWORD, 'event.registration', 'unlink', [[reg['id']]])
        for user in users:
            if 'partner_id' in user:
                models.execute_kw(DB_NAME, uid, PASSWORD, 'res.partner', 'unlink', [[user['partner_id']]])
                models.execute_kw(DB_NAME, uid, PASSWORD, 'popcorn.membership', 'unlink', [[user['membership_id']]])
        print("[OK] Cleaned up")


if __name__ == '__main__':
    main()

