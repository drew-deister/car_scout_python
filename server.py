from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import os
import asyncio
import random
import re
import json
from datetime import datetime
from bson import ObjectId
from dotenv import load_dotenv

from models import Thread, Message, CarListing, Visit
from utils import (
    build_conversation_transcript,
    extract_car_listing_data, message_contains_new_information, get_ai_response,
    send_sms, MTA_PHONE_NUMBER, MTA_API_KEY, openai_client,
    check_if_message_about_visit_scheduling, process_visit_scheduling
)

load_dotenv()

app = FastAPI()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    if request.url.path == "/api/webhook/sms":
        print(f"\n🌐 INCOMING REQUEST: {request.method} {request.url.path}")
        print(f"   Client: {request.client.host if request.client else 'unknown'}")
        print(f"   Headers: {dict(request.headers)}")
        try:
            body_bytes = await request.body()
            if body_bytes:
                body_str = body_bytes.decode('utf-8')
                print(f"   Body: {body_str}")
                # Recreate the request body for downstream processing
                async def receive():
                    return {"type": "http.request", "body": body_bytes}
                request._receive = receive
        except Exception as e:
            print(f"   Error reading body: {e}")
    
    response = await call_next(request)
    return response

# Track pending responses by thread ID
pending_responses = {}

# Mobile Text Alerts webhook payload model
class SMSWebhook(BaseModel):
    fromNumber: str
    toNumber: Optional[str] = None
    message: str
    replyId: Optional[str] = None
    timestamp: Optional[str] = None
    tags: Optional[Dict[str, Any]] = None


@app.get("/api")
async def root():
    return {"message": "Car Scout API is running"}


@app.get("/api/webhook/test")
async def webhook_test():
    """Test endpoint to verify webhook URL is reachable"""
    print("\n🔔 WEBHOOK TEST ENDPOINT HIT - Webhook URL is reachable!")
    return {"message": "Webhook endpoint is reachable", "status": "ok"}


@app.get("/api/test-db")
async def test_db():
    from models import client
    try:
        # Test connection
        client.admin.command('ping')
        return {
            "connected": True,
            "state": "connected",
            "message": "MongoDB connection is active!"
        }
    except Exception as e:
        return {
            "connected": False,
            "state": "disconnected",
            "message": f"MongoDB connection error: {str(e)}"
        }


@app.get("/api/templates")
async def get_templates():
    import requests
    from utils import MTA_API_BASE_URL, MTA_API_KEY
    
    if not MTA_API_KEY:
        raise HTTPException(status_code=500, detail="MTA_API_KEY is not configured in environment variables")
    
    try:
        response = requests.get(
            f"{MTA_API_BASE_URL}/templates",
            headers={
                "Authorization": f"Bearer {MTA_API_KEY}",
                "Content-Type": "application/json"
            }
        )
        response.raise_for_status()
        return {
            "success": True,
            "templates": response.json()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch templates: {str(e)}")


@app.post("/api/register-webhook")
async def register_webhook(webhook_data: Dict[str, Any]):
    import requests
    from utils import MTA_API_BASE_URL, MTA_API_KEY
    
    if not MTA_API_KEY:
        raise HTTPException(status_code=500, detail="MTA_API_KEY is not configured in environment variables")
    
    webhook_url = webhook_data.get("webhookUrl")
    if not webhook_url:
        raise HTTPException(status_code=400, detail="webhookUrl is required")
    
    try:
        response = requests.post(
            f"{MTA_API_BASE_URL}/webhooks",
            json={
                "event": "message-reply",
                "url": webhook_url,
                "secret": webhook_data.get("secret") or os.getenv("MTA_WEBHOOK_SECRET", "your-secret-key"),
                "alertEmail": webhook_data.get("alertEmail") or os.getenv("MTA_ALERT_EMAIL", "")
            },
            headers={
                "Authorization": f"Bearer {MTA_API_KEY}",
                "Content-Type": "application/json"
            }
        )
        response.raise_for_status()
        return {
            "success": True,
            "message": "Webhook registered successfully",
            "data": response.json()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to register webhook: {str(e)}")


@app.post("/api/webhook/sms")
async def sms_webhook(webhook: SMSWebhook):
    try:
        print(f"\n{'='*60}")
        print(f"📨 INCOMING WEBHOOK RECEIVED")
        print(f"{'='*60}")
        print(f"From: {webhook.fromNumber}")
        print(f"To: {webhook.toNumber}")
        print(f"Message: {webhook.message}")
        print(f"Timestamp: {webhook.timestamp}")
        print(f"Reply ID: {webhook.replyId}")
        print(f"Tags: {webhook.tags}")
        print(f"{'='*60}\n")
        
        sender_phone = webhook.fromNumber
        recipient_phone = webhook.toNumber or "unknown"
        message_body = webhook.message
        
        if not sender_phone or not message_body:
            print("❌ ERROR: Missing required fields (sender_phone or message_body)")
            raise HTTPException(status_code=400, detail="Missing required fields")
        
        # Filter out Mobile Text Alerts automatic opt-in messages
        opt_in_pattern = re.compile(r'Thanks for opting in to receive messages from us!', re.IGNORECASE)
        if opt_in_pattern.search(message_body):
            print("⚠️  Ignoring Mobile Text Alerts automatic opt-in message")
            return {"success": True, "message": "Opt-in message ignored"}
        
        # Find or create thread
        thread = Thread.find_one({"phoneNumber": sender_phone})
        
        if not thread:
            timestamp = datetime.now()
            if webhook.timestamp:
                try:
                    timestamp = datetime.fromisoformat(webhook.timestamp.replace('Z', '+00:00'))
                except:
                    timestamp = datetime.now()
            
            thread_data = {
                "phoneNumber": sender_phone,
                "lastMessage": message_body,
                "lastMessageTime": timestamp,
                "unreadCount": 1,
                "conversationComplete": False,
                "waitingForDealerResponse": False
            }
            thread_id = Thread.create(thread_data)
            thread = Thread.find_by_id(thread_id)
        else:
            timestamp = datetime.now()
            if webhook.timestamp:
                try:
                    timestamp = datetime.fromisoformat(webhook.timestamp.replace('Z', '+00:00'))
                except:
                    timestamp = datetime.now()
            
            Thread.update_one(
                {"_id": thread["_id"]},
                {
                    "lastMessage": message_body,
                    "lastMessageTime": timestamp,
                    "unreadCount": thread.get("unreadCount", 0) + 1
                }
            )
            thread = Thread.find_by_id(str(thread["_id"]))
        
        # Save incoming message
        message_timestamp = datetime.now()
        if webhook.timestamp:
            try:
                message_timestamp = datetime.fromisoformat(webhook.timestamp.replace('Z', '+00:00'))
            except:
                message_timestamp = datetime.now()
        
        message_data = {
            "threadId": thread["_id"],
            "from": sender_phone,
            "to": recipient_phone,
            "body": message_body,
            "direction": "inbound",
            "timestamp": message_timestamp,
            "externalMessageId": webhook.replyId or (webhook.tags.get("messageId") if webhook.tags else None)
        }
        Message.create(message_data)
        
        # Check if conversation is already complete
        if thread.get("conversationComplete"):
            print("ℹ️  Conversation already complete, not generating response")
            return {"success": True, "message": "Conversation complete, no response sent"}
        
        # If waiting for dealer response, check if message has new information
        if thread.get("waitingForDealerResponse"):
            print("ℹ️  Currently waiting for dealer response, checking if message contains new information...")
            known_data = None  # No URL extraction data available
            has_new_info = await message_contains_new_information(message_body, known_data)
            
            if not has_new_info:
                print("ℹ️  Message is just an acknowledgment, not responding")
                return {"success": True, "message": "Waiting for dealer response, no new information in message"}
            else:
                print("✅ Message contains new information, clearing waiting state and responding")
                Thread.update_one(
                    {"_id": thread["_id"]},
                    {"waitingForDealerResponse": False}
                )
        
        # Cancel any pending response for this thread
        thread_id_string = str(thread["_id"])
        if thread_id_string in pending_responses:
            pending_timeout = pending_responses[thread_id_string]
            pending_timeout["task"].cancel()
            del pending_responses[thread_id_string]
            print("⚠️  Cancelled pending response due to new message")
        
        # Generate AI agent response
        try:
            transcript = await build_conversation_transcript(thread_id_string, Message)
            print(f"Conversation transcript: {transcript}")
            
            # Always call main AI agent first
            known_data = None  # No URL extraction data available
            ai_response = await get_ai_response(transcript, known_data, thread.get("waitingForDealerResponse", False))
            print(f"AI agent response: {ai_response}")
            
            # Check if we should enter waiting state
            if "# WAITING #" in ai_response:
                print("✅ Agent entering waiting state - dealer said they will get back")
                thank_you_message = ai_response.replace("# WAITING #", "").strip() or "Thank you"
                
                try:
                    await send_sms(sender_phone, thank_you_message)
                    
                    # Save thank you message
                    Message.create({
                        "threadId": thread["_id"],
                        "from": MTA_PHONE_NUMBER,
                        "to": sender_phone,
                        "body": thank_you_message,
                        "direction": "outbound",
                        "timestamp": datetime.now()
                    })
                    
                    # Mark thread as waiting
                    Thread.update_one(
                        {"_id": thread["_id"]},
                        {
                            "waitingForDealerResponse": True,
                            "lastMessage": thank_you_message,
                            "lastMessageTime": datetime.now()
                        }
                    )
                    print("✅ Thank you message sent, now waiting for dealer response")
                except Exception as send_error:
                    print(f"Error sending thank you message: {send_error}")
                
                return {"success": True, "message": "Entered waiting state, no further responses until dealer provides new info"}
            
            # Check if agent is ready to schedule
            # The AI may return just "#SCHEDULE#" or a message with "#SCHEDULE#" appended
            if "#SCHEDULE#" in ai_response:
                print("📅 Agent has all information, calling scheduling agent...")
                print(f"   AI response contained #SCHEDULE#: {ai_response}")
                
                # Strip #SCHEDULE# from the response if it's there (we'll use scheduling agent's response instead)
                ai_response = ai_response.replace("#SCHEDULE#", "").strip()
                
                # Call scheduling agent with the latest message
                scheduling_result = await process_visit_scheduling(transcript, thread_id_string, sender_phone, message_body)
                
                if scheduling_result and isinstance(scheduling_result, dict):
                    scheduling_message = scheduling_result.get("message", "")
                    visit_scheduled = scheduling_result.get("visit_scheduled", False)
                    
                    if visit_scheduled:
                        print(f"✅ Visit scheduled! Scheduling agent response: {scheduling_message}")
                        ai_response = scheduling_message
                        
                        # Send the scheduling confirmation message
                        try:
                            await send_sms(sender_phone, ai_response)
                            
                            Message.create({
                                "threadId": thread["_id"],
                                "from": MTA_PHONE_NUMBER,
                                "to": sender_phone,
                                "body": ai_response,
                                "direction": "outbound",
                                "timestamp": datetime.now()
                            })
                            print("✅ Scheduling confirmation sent to dealer")
                        except Exception as send_error:
                            print(f"Error sending scheduling message: {send_error}")
                        
                        # Mark thread as complete
                        Thread.update_one(
                            {"_id": thread["_id"]},
                            {
                                "conversationComplete": True,
                                "lastMessage": ai_response,
                                "lastMessageTime": datetime.now()
                            }
                        )
                        
                        # Extract and save car listing data
                        try:
                            extracted_data = await extract_car_listing_data(transcript)
                            print(f"Extracted car listing data: {extracted_data}")
                            
                            car_listing = CarListing.find_one({"threadId": thread["_id"]})
                            if car_listing:
                                CarListing.update_one(
                                    {"threadId": thread["_id"]},
                                    {**extracted_data, "conversationComplete": True}
                                )
                                print("✅ Updated existing car listing")
                            else:
                                CarListing.create({
                                    "threadId": thread["_id"],
                                    "phoneNumber": sender_phone,
                                    **extracted_data,
                                    "conversationComplete": True,
                                    "extractedAt": datetime.now()
                                })
                                print("✅ Saved car listing data to MongoDB")
                        except Exception as extract_error:
                            print(f"Error extracting/saving car listing data: {extract_error}")
                        
                        return {"success": True, "message": "Visit scheduled, conversation complete"}
                    else:
                        # Scheduling agent returned a message but visit not scheduled yet
                        print(f"📅 Scheduling agent response (visit not yet scheduled): {scheduling_message}")
                        ai_response = scheduling_message
                        # Continue with normal delayed response flow below - agent will keep returning #SCHEDULE# until visit is scheduled
                elif scheduling_result:
                    # Scheduling agent returned a string (backward compatibility)
                    print(f"📅 Scheduling agent response (legacy format): {scheduling_result}")
                    ai_response = scheduling_result
                    # Continue with normal delayed response flow below
                else:
                    # Scheduling agent failed
                    print("⚠️  Scheduling agent failed")
                    ai_response = "I'm ready to schedule a visit. What date and time works for you?"
                    # Continue with normal delayed response flow below
            elif check_if_message_about_visit_scheduling(message_body):
                # Dealer is asking about scheduling, but AI didn't return #SCHEDULE#
                # Check if we have a car listing - if so, we might have all the info and should try scheduling
                car_listing = CarListing.find_one({"threadId": thread["_id"]})
                
                # If we have a car listing with key fields, try calling scheduling agent
                if car_listing and car_listing.get('make') and car_listing.get('model') and car_listing.get('year'):
                    print("📅 Dealer asked about scheduling - checking if we should call scheduling agent...")
                    print(f"   Car listing exists: {car_listing.get('make')} {car_listing.get('model')} {car_listing.get('year')}")
                    
                    # Try calling scheduling agent
                    scheduling_result = await process_visit_scheduling(transcript, thread_id_string, sender_phone, message_body)
                    
                    if scheduling_result and isinstance(scheduling_result, dict):
                        scheduling_message = scheduling_result.get("message", "")
                        visit_scheduled = scheduling_result.get("visit_scheduled", False)
                        
                        if visit_scheduled:
                            print(f"✅ Visit scheduled via fallback! Scheduling agent response: {scheduling_message}")
                            ai_response = scheduling_message
                            
                            # Send the scheduling confirmation message
                            try:
                                await send_sms(sender_phone, ai_response)
                                
                                Message.create({
                                    "threadId": thread["_id"],
                                    "from": MTA_PHONE_NUMBER,
                                    "to": sender_phone,
                                    "body": ai_response,
                                    "direction": "outbound",
                                    "timestamp": datetime.now()
                                })
                                print("✅ Scheduling confirmation sent to dealer")
                            except Exception as send_error:
                                print(f"Error sending scheduling message: {send_error}")
                            
                            # Mark thread as complete
                            Thread.update_one(
                                {"_id": thread["_id"]},
                                {
                                    "conversationComplete": True,
                                    "lastMessage": ai_response,
                                    "lastMessageTime": datetime.now()
                                }
                            )
                            
                            # Extract and save car listing data if not already complete
                            try:
                                if not car_listing.get("conversationComplete"):
                                    extracted_data = await extract_car_listing_data(transcript)
                                    print(f"Extracted car listing data: {extracted_data}")
                                    
                                    CarListing.update_one(
                                        {"threadId": thread["_id"]},
                                        {**extracted_data, "conversationComplete": True}
                                    )
                                    print("✅ Updated car listing data")
                            except Exception as extract_error:
                                print(f"Error extracting/saving car listing data: {extract_error}")
                            
                            return {"success": True, "message": "Visit scheduled, conversation complete"}
                        else:
                            # Scheduling agent returned a message but visit not scheduled yet
                            print(f"📅 Scheduling agent response (visit not yet scheduled): {scheduling_message}")
                            ai_response = scheduling_message
                            # Continue with normal delayed response flow below
                    elif scheduling_result:
                        # Scheduling agent returned a string (backward compatibility)
                        print(f"📅 Scheduling agent response (legacy format): {scheduling_result}")
                        ai_response = scheduling_result
                        # Continue with normal delayed response flow below
                    else:
                        # Scheduling agent failed, use AI's original response
                        print("⚠️  Scheduling agent failed in fallback, using AI response")
                        # Continue with AI's original response
                else:
                    # No car listing or missing key fields, use AI's response
                    print("ℹ️  Dealer asked about scheduling but no complete car listing found, using AI response")
                    # Continue with AI's original response
            else:
                # Schedule delayed response
                delay_ms = 3000 # random.randint(30000, 60000)  
                print(f"⏱️  Scheduling response to be sent in {delay_ms // 1000} seconds")
                
                async def send_delayed_response():
                    try:
                        await asyncio.sleep(delay_ms / 1000)
                        
                        # Check if this response was cancelled
                        if thread_id_string not in pending_responses:
                            print("⚠️  Response cancelled, not sending")
                            return
                        
                        # Send AI-generated response
                        await send_sms(sender_phone, ai_response)
                        
                        # Save outbound message
                        Message.create({
                            "threadId": thread["_id"],
                            "from": MTA_PHONE_NUMBER,
                            "to": sender_phone,
                            "body": ai_response,
                            "direction": "outbound",
                            "timestamp": datetime.now()
                        })
                        
                        # Update thread
                        Thread.update_one(
                            {"_id": thread["_id"]},
                            {
                                "lastMessage": ai_response,
                                "lastMessageTime": datetime.now()
                            }
                        )
                        
                        # Remove from pending responses
                        if thread_id_string in pending_responses:
                            del pending_responses[thread_id_string]
                        
                        print("✅ AI agent response sent successfully")
                    except Exception as send_error:
                        if thread_id_string in pending_responses:
                            del pending_responses[thread_id_string]
                        print(f"Error sending AI agent response: {send_error}")
                
                task = asyncio.create_task(send_delayed_response())
                pending_responses[thread_id_string] = {"task": task, "aiResponse": ai_response}
        except Exception as reply_error:
            print(f"Error generating AI agent response: {reply_error}")
        
        return {"success": True, "message": "Message processed"}
    except Exception as error:
        import traceback
        print(f"\n❌ ERROR processing incoming SMS:")
        print(f"   Error: {error}")
        print(f"   Type: {type(error).__name__}")
        print(f"   Traceback:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Error processing message")


def serialize_document(doc):
    """Convert MongoDB document to JSON-serializable format"""
    if doc is None:
        return None
    if isinstance(doc, dict):
        result = {}
        for key, value in doc.items():
            if isinstance(value, ObjectId):
                result[key] = str(value)
            elif isinstance(value, datetime):
                result[key] = value.isoformat()
            elif isinstance(value, dict):
                result[key] = serialize_document(value)
            elif isinstance(value, list):
                result[key] = [serialize_document(item) for item in value]
            else:
                result[key] = value
        return result
    return doc


@app.get("/api/threads")
async def get_threads():
    try:
        threads = Thread.find(sort=[("lastMessageTime", -1)])
        # Convert ObjectId to string for JSON serialization
        return [serialize_document(thread) for thread in threads]
    except Exception as error:
        print(f"Error fetching threads: {error}")
        raise HTTPException(status_code=500, detail="Failed to fetch threads")


@app.get("/api/threads/{thread_id}/messages")
async def get_messages(thread_id: str):
    try:
        # Verify thread exists
        thread = Thread.find_by_id(thread_id)
        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found")
        
        # Get all messages for this thread
        messages = Message.find({"threadId": ObjectId(thread_id)}, sort=[("timestamp", 1)])
        
        # Mark thread as read
        Thread.update_one(
            {"_id": ObjectId(thread_id)},
            {"unreadCount": 0}
        )
        
        # Convert ObjectId to string and serialize
        return [serialize_document(message) for message in messages]
    except HTTPException:
        raise
    except Exception as error:
        print(f"Error fetching messages: {error}")
        raise HTTPException(status_code=500, detail="Failed to fetch messages")


@app.get("/api/car-listings")
async def get_car_listings():
    try:
        from models import client
        # Check if MongoDB is connected
        try:
            client.admin.command('ping')
        except:
            raise HTTPException(
                status_code=503,
                detail="Database unavailable - MongoDB connection is not active. Please check your connection string and network connectivity."
            )
        
        listings = CarListing.find(sort=[("extractedAt", -1)])
        
        # Convert ObjectId to string and populate thread info
        result = []
        for listing in listings:
            listing_serialized = serialize_document(listing)
            thread_id = listing.get("threadId")
            if thread_id:
                thread = Thread.find_by_id(str(thread_id))
                if thread:
                    listing_serialized["thread"] = serialize_document(thread)
            result.append(listing_serialized)
        
        return result
    except HTTPException:
        raise
    except Exception as error:
        print(f"Error fetching car listings: {error}")
        raise HTTPException(status_code=500, detail="Failed to fetch car listings")


@app.get("/api/threads/{thread_id}/car-listing")
async def get_thread_car_listing(thread_id: str):
    try:
        car_listing = CarListing.find_one({"threadId": ObjectId(thread_id)})
        
        if not car_listing:
            raise HTTPException(status_code=404, detail="Car listing not found for this thread")
        
        # Serialize car listing
        car_listing_serialized = serialize_document(car_listing)
        
        # Populate thread info
        thread = Thread.find_by_id(thread_id)
        if thread:
            car_listing_serialized["thread"] = serialize_document(thread)
        
        return car_listing_serialized
    except HTTPException:
        raise
    except Exception as error:
        print(f"Error fetching car listing: {error}")
        raise HTTPException(status_code=500, detail="Failed to fetch car listing")


@app.get("/api/visits")
async def get_visits(start_date: Optional[str] = None, end_date: Optional[str] = None):
    """Get visits, optionally filtered by date range"""
    try:
        query = {}
        
        if start_date or end_date:
            from dateutil import parser as date_parser
            from dateutil.tz import gettz
            ct_tz = gettz('America/Chicago')
            
            date_range = {}
            if start_date:
                start = date_parser.parse(start_date)
                if start.tzinfo is None:
                    start = start.replace(tzinfo=ct_tz)
                date_range["$gte"] = start
            if end_date:
                end = date_parser.parse(end_date)
                if end.tzinfo is None:
                    end = end.replace(tzinfo=ct_tz)
                date_range["$lte"] = end
            
            if date_range:
                query["scheduledTime"] = date_range
        
        # Exclude cancelled visits by default
        query["status"] = {"$ne": "cancelled"}
        
        visits = Visit.find(query, sort=[("scheduledTime", 1)])
        
        # Serialize and populate related data
        result = []
        for visit in visits:
            visit_serialized = serialize_document(visit)
            
            # Populate car listing if available
            if visit.get("carListingId"):
                car_listing = CarListing.find_by_id(str(visit["carListingId"]))
                if car_listing:
                    visit_serialized["carListing"] = serialize_document(car_listing)
            
            # Populate thread if available
            if visit.get("threadId"):
                thread = Thread.find_by_id(str(visit["threadId"]))
                if thread:
                    visit_serialized["thread"] = serialize_document(thread)
            
            result.append(visit_serialized)
        
        return result
    except Exception as error:
        print(f"Error fetching visits: {error}")
        raise HTTPException(status_code=500, detail="Failed to fetch visits")


@app.get("/api/visits/{visit_id}")
async def get_visit(visit_id: str):
    """Get a specific visit by ID"""
    try:
        visit = Visit.find_by_id(visit_id)
        
        if not visit:
            raise HTTPException(status_code=404, detail="Visit not found")
        
        visit_serialized = serialize_document(visit)
        
        # Populate car listing if available
        if visit.get("carListingId"):
            car_listing = CarListing.find_by_id(str(visit["carListingId"]))
            if car_listing:
                visit_serialized["carListing"] = serialize_document(car_listing)
        
        # Populate thread if available
        if visit.get("threadId"):
            thread = Thread.find_by_id(str(visit["threadId"]))
            if thread:
                visit_serialized["thread"] = serialize_document(thread)
        
        return visit_serialized
    except HTTPException:
        raise
    except Exception as error:
        print(f"Error fetching visit: {error}")
        raise HTTPException(status_code=500, detail="Failed to fetch visit")


if __name__ == "__main__":
    import uvicorn
    import logging
    
    # Reduce uvicorn access log verbosity
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    
    port = int(os.getenv("PORT", 5001))
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=port,
        log_level="warning"  # Only show warnings and errors, not INFO
    )

