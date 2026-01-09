#!/usr/bin/env python3
"""
Script to delete all data associated with a phone number:
- Thread
- All messages in the thread
- Car listing (if exists)
- Visits (if exist)
"""

import sys
from bson import ObjectId
from models import Thread, Message, CarListing, Visit

def delete_thread_data(phone_number: str):
    """Delete all data for a given phone number"""
    
    print(f"\n{'='*60}")
    print(f"🗑️  DELETING DATA FOR: {phone_number}")
    print(f"{'='*60}\n")
    
    # Find thread by phone number
    thread = Thread.find_one({"phoneNumber": phone_number})
    
    if not thread:
        print(f"❌ No thread found for phone number: {phone_number}")
        return False
    
    thread_id = thread["_id"]
    thread_id_str = str(thread_id)
    
    print(f"✅ Found thread: {thread_id_str}")
    print(f"   Last message: {thread.get('lastMessage', 'N/A')[:50]}...")
    print(f"   Last message time: {thread.get('lastMessageTime', 'N/A')}")
    
    # Count and delete messages
    messages = Message.find({"threadId": thread_id})
    message_count = len(messages)
    print(f"\n📨 Found {message_count} messages")
    
    if message_count > 0:
        from models import messages_collection
        result = messages_collection.delete_many({"threadId": thread_id})
        print(f"   ✅ Deleted {result.deleted_count} messages")
    
    # Delete car listing if exists
    car_listing = CarListing.find_one({"threadId": thread_id})
    if car_listing:
        from models import car_listings_collection
        result = car_listings_collection.delete_one({"_id": car_listing["_id"]})
        print(f"   ✅ Deleted car listing: {car_listing.get('make', '')} {car_listing.get('model', '')}")
    
    # Delete visits if exist
    visits = Visit.find({"threadId": thread_id})
    visit_count = len(visits)
    if visit_count > 0:
        from models import visits_collection
        result = visits_collection.delete_many({"threadId": thread_id})
        print(f"   ✅ Deleted {result.deleted_count} visits")
    
    # Finally, delete the thread
    from models import threads_collection
    result = threads_collection.delete_one({"_id": thread_id})
    
    if result.deleted_count > 0:
        print(f"\n✅ Successfully deleted thread and all associated data!")
        print(f"   - Thread: {thread_id_str}")
        print(f"   - Messages: {message_count}")
        print(f"   - Car listing: {'Yes' if car_listing else 'No'}")
        print(f"   - Visits: {visit_count}")
        return True
    else:
        print(f"\n❌ Failed to delete thread")
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 delete_thread_data.py <phone_number>")
        print("Example: python3 delete_thread_data.py +15133126863")
        sys.exit(1)
    
    phone_number = sys.argv[1]
    
    # Confirm deletion
    print(f"\n⚠️  WARNING: This will permanently delete ALL data for {phone_number}")
    print("   - Thread")
    print("   - All messages")
    print("   - Car listing (if exists)")
    print("   - Visits (if exist)")
    
    response = input("\nAre you sure you want to continue? (yes/no): ")
    
    if response.lower() not in ['yes', 'y']:
        print("❌ Cancelled")
        sys.exit(0)
    
    success = delete_thread_data(phone_number)
    
    if success:
        print(f"\n{'='*60}")
        print("✅ Deletion complete!")
        print(f"{'='*60}\n")
        sys.exit(0)
    else:
        print(f"\n{'='*60}")
        print("❌ Deletion failed or nothing found")
        print(f"{'='*60}\n")
        sys.exit(1)

