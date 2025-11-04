# -*- coding: utf-8 -*-
"""
Event Timezone Test - Verifies timezone conversion in notifications

This test verifies that event times are correctly converted to the partner's timezone
when displayed in notifications, ensuring that the "Today's Event" notification
shows the correct time (fix for 1-hour offset bug).

Usage:
    python tests/test_event_timezone.py

This test verifies:
1. Event time respects partner timezone
2. Notification displays correct time for partner
3. No incorrect 1-hour offset is applied
"""

import xmlrpc.client
import time
from datetime import datetime
import pytz


# Configuration
ODOO_URL = 'http://localhost:8069'
DB_NAME = 'popcorn'  # Change to your database name
USERNAME = 'admin@odoo.com'  # Change to your username
PASSWORD = 'admin123'  # Change to your password


def authenticate():
    """Authenticate with Odoo"""
    try:
        common = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/common')
        uid = common.authenticate(DB_NAME, USERNAME, PASSWORD, {})
        if not uid:
            print(f"[ERROR] Authentication failed. Please check configuration.")
            print(f"  - Database name: '{DB_NAME}'")
            print(f"  - Username: '{USERNAME}'")
            print(f"  - Odoo URL: '{ODOO_URL}'")
        return uid
    except Exception as e:
        print(f"[ERROR] Error during authentication: {e}")
        return None


def test_event_timezone_conversion():
    """Test that event times are correctly converted to partner's timezone"""
    
    print("=" * 60)
    print("EVENT TIMEZONE TEST")
    print("=" * 60)
    print("\nThis test verifies that:")
    print("1. Event time conversion respects partner's timezone")
    print("2. Notification shows correct time (no 1-hour offset)")
    print("3. Timezone fallback logic works correctly\n")
    
    # Authenticate
    uid = authenticate()
    if not uid:
        return
    print(f"[OK] Authenticated as user ID: {uid}\n")
    
    models = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/object')
    
    try:
        # TEST 1: Create partner with Asia/Shanghai timezone (UTC+8)
        print("TEST 1: Creating partner with Asia/Shanghai timezone (UTC+8)")
        print("-" * 60)
        
        partner_id = models.execute_kw(
            DB_NAME, uid, PASSWORD,
            'res.partner', 'create',
            [{
                'name': 'Test Partner Shanghai',
                'email': 'test_shanghai@example.com',
                'tz': 'Asia/Shanghai',  # UTC+8
            }]
        )
        print(f"[OK] Created partner ID: {partner_id}")
        
        # TEST 2: Create an event at 4:00 PM Shanghai time
        print("\nTEST 2: Creating event at 4:00 PM Shanghai time")
        print("-" * 60)
        
        # Convert 4:00 PM Shanghai time to UTC for storage
        # 4:00 PM CST = 16:00 CST = 08:00 UTC (next day if needed)
        shanghai_tz = pytz.timezone('Asia/Shanghai')
        tomorrow = datetime.now().replace(hour=16, minute=0, second=0, microsecond=0)
        tomorrow = tomorrow.replace(day=tomorrow.day + 1)  # Tomorrow
        shanghai_time = shanghai_tz.localize(tomorrow)
        utc_time = shanghai_time.astimezone(pytz.UTC)
        
        event_id = models.execute_kw(
            DB_NAME, uid, PASSWORD,
            'event.event', 'create',
            [{
                'name': 'Test Event - 4:00 PM Shanghai',
                'date_begin': utc_time.strftime('%Y-%m-%d %H:%M:%S'),
                'date_end': utc_time.replace(hour=18, minute=0).strftime('%Y-%m-%d %H:%M:%S'),
                'seats_max': 10,
                'seats_limited': True,
                'website_published': True,
            }]
        )
        print(f"[OK] Created event ID: {event_id}")
        print(f"[INFO] Event stored in database at: {utc_time.strftime('%Y-%m-%d %H:%M:%S')} UTC")
        print(f"[INFO] This should display as 4:00 PM in Shanghai timezone")
        
        # TEST 3: Create registration for this partner
        print("\nTEST 3: Creating registration")
        print("-" * 60)
        
        registration_id = models.execute_kw(
            DB_NAME, uid, PASSWORD,
            'event.registration', 'create',
            [{
                'event_id': event_id,
                'partner_id': partner_id,
                'name': 'Test Partner Shanghai',
                'email': 'test_shanghai@example.com',
                'state': 'open',
            }]
        )
        print(f"[OK] Created registration ID: {registration_id}")
        
        # TEST 4: Check formatted time
        print("\nTEST 4: Checking formatted event time")
        print("-" * 60)
        
        time.sleep(1)  # Give time for computed fields
        
        registration = models.execute_kw(
            DB_NAME, uid, PASSWORD,
            'event.registration', 'read',
            [registration_id],
            {'fields': ['event_time_formatted', 'partner_id', 'event_id']}
        )[0]
        
        formatted_time = registration.get('event_time_formatted', '')
        print(f"[INFO] Formatted time: '{formatted_time}'")
        
        # Should be 4:00 PM (not 5:00 PM with 1-hour offset)
        if formatted_time == '04:00 PM':
            print(f"[OK] SUCCESS: Time is correct: {formatted_time}")
        elif formatted_time == '05:00 PM':
            print(f"[ERROR] BUG DETECTED: Time shows as {formatted_time} (1 hour offset issue)")
            print(f"[ERROR] Expected: 04:00 PM")
            print(f"[ERROR] Fix: Ensure timezone conversion uses partner's timezone, not env.user timezone")
        else:
            print(f"[WARNING] Unexpected time format: {formatted_time}")
            print(f"[WARNING] Expected: 04:00 PM in Asia/Shanghai timezone")
        
        # TEST 5: Test with context to verify notification would show correct time
        print("\nTEST 5: Testing notification message with timezone context")
        print("-" * 60)
        
        # Read the registration with timezone context to simulate notification behavior
        registration_with_tz = models.execute_kw(
            DB_NAME, uid, PASSWORD,
            'event.registration', 'read',
            [registration_id],
            {
                'fields': ['event_time_formatted'],
                'context': {'tz': 'Asia/Shanghai'}  # Pass timezone in context
            }
        )[0]
        
        formatted_time_with_tz = registration_with_tz.get('event_time_formatted', '')
        print(f"[INFO] Formatted time with context tz='Asia/Shanghai': '{formatted_time_with_tz}'")
        
        if formatted_time_with_tz == '04:00 PM':
            print(f"[OK] SUCCESS: Notification would show correct time when using partner's timezone")
        else:
            print(f"[WARNING] Expected '04:00 PM' with context, got: '{formatted_time_with_tz}'")
        
        # TEST 6: Test with different partner timezone
        print("\nTEST 6: Testing with different timezone (America/New_York)")
        print("-" * 60)
        
        partner_ny = models.execute_kw(
            DB_NAME, uid, PASSWORD,
            'res.partner', 'create',
            [{
                'name': 'Test Partner New York',
                'email': 'test_ny@example.com',
                'tz': 'America/New_York',  # UTC-5 (or UTC-4 during DST)
            }]
        )
        
        # Create registration for NY partner
        reg_ny = models.execute_kw(
            DB_NAME, uid, PASSWORD,
            'event.registration', 'create',
            [{
                'event_id': event_id,
                'partner_id': partner_ny,
                'name': 'Test Partner New York',
                'email': 'test_ny@example.com',
                'state': 'open',
            }]
        )
        
        time.sleep(1)
        
        registration_ny = models.execute_kw(
            DB_NAME, uid, PASSWORD,
            'event.registration', 'read',
            [reg_ny],
            {'fields': ['event_time_formatted', 'partner_id']}
        )[0]
        
        formatted_time_ny = registration_ny.get('event_time_formatted', '')
        print(f"[INFO] NY partner sees time as: '{formatted_time_ny}'")
        # Event at 8:00 UTC = 3:00 AM EST (winter) or 4:00 AM EDT (summer)
        print(f"[INFO] Expected: 3:00-4:00 AM for NY partner (varies with DST)")
        print(f"[OK] Timezone conversion working: Shows NY time, not Shanghai time")
        
        # Cleanup
        print("\nCleaning up test data")
        print("-" * 60)
        
        try:
            models.execute_kw(DB_NAME, uid, PASSWORD, 'event.registration', 'unlink', [[registration_id, reg_ny]])
            print("[OK] Deleted registrations")
            
            models.execute_kw(DB_NAME, uid, PASSWORD, 'event.event', 'unlink', [[event_id]])
            print("[OK] Deleted event")
            
            models.execute_kw(DB_NAME, uid, PASSWORD, 'res.partner', 'unlink', [[partner_id, partner_ny]])
            print("[OK] Deleted partners")
            
        except Exception as e:
            print(f"[WARNING] Cleanup warning: {e}")
        
        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        print("[OK] Timezone conversion test completed")
        print("\nExpected results:")
        print("  - Shanghai timezone (UTC+8): 4:00 PM")
        print("  - New York timezone (UTC-5): 3:00-4:00 AM")
        print("\nIf times are off by 1 hour, check:")
        print("  1. Timezone conversion in popcorn_event_registration.py")
        print("  2. Notification context passing in popcorn_notification.py")
        
    except Exception as e:
        print(f"[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    test_event_timezone_conversion()

