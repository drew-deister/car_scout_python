#!/usr/bin/env python3
"""
Script to create sample visit events in the database.
Creates 2 visits on Saturday and 1 visit on Sunday of the current week.
"""

import os
from datetime import datetime, timedelta
from dateutil.tz import gettz
from dotenv import load_dotenv
from models import Visit, Thread, CarListing
from bson import ObjectId

load_dotenv()

def get_next_saturday_sunday():
    """Get the next Saturday and Sunday dates"""
    today = datetime.now()
    days_until_saturday = (5 - today.weekday()) % 7
    if days_until_saturday == 0:
        days_until_saturday = 7  # If today is Saturday, get next Saturday
    
    saturday = today + timedelta(days=days_until_saturday)
    sunday = saturday + timedelta(days=1)
    
    return saturday, sunday

def create_sample_visits():
    """Create sample visits in the database"""
    # Get Saturday and Sunday dates
    saturday, sunday = get_next_saturday_sunday()
    
    # Set Central Time timezone
    ct_tz = gettz('America/Chicago')
    
    # Get existing threads to link visits to
    all_threads = Thread.find(sort=[("lastMessageTime", -1)])
    threads = all_threads[:3] if all_threads else []
    
    if not threads:
        print("⚠️  No threads found. Creating visits without thread association.")
        # Create dummy thread IDs (these won't exist but visits will still work)
        thread_ids = [ObjectId() for _ in range(3)]
        dealer_phones = ["+15551234567", "+15551234568", "+15551234569"]
    else:
        thread_ids = [thread["_id"] for thread in threads]
        dealer_phones = [thread.get("phoneNumber", "+15551234567") for thread in threads]
        # Extend if needed
        while len(thread_ids) < 3:
            thread_ids.append(thread_ids[-1] if thread_ids else ObjectId())
            dealer_phones.append(dealer_phones[-1] if dealer_phones else "+15551234567")
    
    # Get car listings if available
    all_car_listings = CarListing.find(sort=[("extractedAt", -1)])
    car_listings = all_car_listings[:3] if all_car_listings else []
    car_listing_ids = [listing["_id"] for listing in car_listings] if car_listings else [None, None, None]
    # Extend if needed
    while len(car_listing_ids) < 3:
        car_listing_ids.append(car_listing_ids[-1] if car_listing_ids and car_listing_ids[-1] else None)
    
    # Create visits
    visits_created = []
    
    # Visit 1: Saturday at 10:00 AM
    saturday_10am = saturday.replace(hour=10, minute=0, second=0, microsecond=0)
    saturday_10am = saturday_10am.replace(tzinfo=ct_tz)
    
    visit1_data = {
        "threadId": thread_ids[0],
        "scheduledTime": saturday_10am,
        "dealerPhoneNumber": dealer_phones[0],
        "status": "scheduled",
        "createdAt": datetime.now(),
        "updatedAt": datetime.now()
    }
    if car_listing_ids[0]:
        visit1_data["carListingId"] = car_listing_ids[0]
    visit1_data["notes"] = "First visit - test drive scheduled"
    
    visit1_id = Visit.create(visit1_data)
    visits_created.append(("Saturday 10:00 AM", visit1_id))
    print(f"✅ Created visit 1: Saturday {saturday_10am.strftime('%B %d, %Y at %I:%M %p')} CT")
    
    # Visit 2: Saturday at 2:30 PM
    saturday_230pm = saturday.replace(hour=14, minute=30, second=0, microsecond=0)
    saturday_230pm = saturday_230pm.replace(tzinfo=ct_tz)
    
    visit2_data = {
        "threadId": thread_ids[1] if len(thread_ids) > 1 else thread_ids[0],
        "scheduledTime": saturday_230pm,
        "dealerPhoneNumber": dealer_phones[1] if len(dealer_phones) > 1 else dealer_phones[0],
        "status": "scheduled",
        "createdAt": datetime.now(),
        "updatedAt": datetime.now()
    }
    if car_listing_ids[1]:
        visit2_data["carListingId"] = car_listing_ids[1]
    visit2_data["notes"] = "Second visit - inspection and negotiation"
    
    visit2_id = Visit.create(visit2_data)
    visits_created.append(("Saturday 2:30 PM", visit2_id))
    print(f"✅ Created visit 2: Saturday {saturday_230pm.strftime('%B %d, %Y at %I:%M %p')} CT")
    
    # Visit 3: Sunday at 11:00 AM
    sunday_11am = sunday.replace(hour=11, minute=0, second=0, microsecond=0)
    sunday_11am = sunday_11am.replace(tzinfo=ct_tz)
    
    visit3_data = {
        "threadId": thread_ids[2] if len(thread_ids) > 2 else thread_ids[0],
        "scheduledTime": sunday_11am,
        "dealerPhoneNumber": dealer_phones[2] if len(dealer_phones) > 2 else dealer_phones[0],
        "status": "scheduled",
        "createdAt": datetime.now(),
        "updatedAt": datetime.now()
    }
    if car_listing_ids[2]:
        visit3_data["carListingId"] = car_listing_ids[2]
    visit3_data["notes"] = "Sunday visit - final decision meeting"
    
    visit3_id = Visit.create(visit3_data)
    visits_created.append(("Sunday 11:00 AM", visit3_id))
    print(f"✅ Created visit 3: Sunday {sunday_11am.strftime('%B %d, %Y at %I:%M %p')} CT")
    
    print(f"\n✅ Successfully created {len(visits_created)} sample visits!")
    print("\nVisits created:")
    for time_desc, visit_id in visits_created:
        print(f"  - {time_desc}: {visit_id}")
    
    return visits_created

if __name__ == "__main__":
    try:
        create_sample_visits()
    except Exception as e:
        print(f"❌ Error creating sample visits: {e}")
        import traceback
        traceback.print_exc()

