import re
import os
import json
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from openai import OpenAI
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from dateutil import parser as date_parser
from dateutil.tz import gettz

# Playwright for JavaScript-rendered content
try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("⚠️  Playwright not installed. JavaScript-rendered content may not be captured. Install with: pip install playwright && playwright install chromium")

load_dotenv()

# OpenAI configuration
openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY')) if os.getenv('OPENAI_API_KEY') else None

# Mobile Text Alerts configuration
MTA_API_BASE_URL = 'https://api.mobile-text-alerts.com/v3'
MTA_API_KEY = os.getenv('MTA_API_KEY')
MTA_PHONE_NUMBER = '+18776647380'
MTA_LONGCODE_ID = 8337441549
MTA_AUTO_REPLY_TEMPLATE_ID = os.getenv('MTA_AUTO_REPLY_TEMPLATE_ID')
if MTA_AUTO_REPLY_TEMPLATE_ID:
    try:
        MTA_AUTO_REPLY_TEMPLATE_ID = int(MTA_AUTO_REPLY_TEMPLATE_ID)
    except:
        MTA_AUTO_REPLY_TEMPLATE_ID = None


async def detect_and_extract_url(message: str) -> Optional[str]:
    """
    Step 1: Use GPT-4o to detect if there's a link in the message and extract it.
    Returns the URL if found, None otherwise.
    """
    if not openai_client:
        # Fallback to regex if OpenAI is not configured
        url_regex = r'(https?://[^\s]+)'
        urls = re.findall(url_regex, message)
        return urls[0] if urls else None
    
    try:
        detection_prompt = f"""Analyze this message and determine if it contains any URLs or links. 
If a URL is found, return ONLY the complete URL. If no URL is found, return null.

Message: {message}

Return ONLY a JSON object in this format:
{{
  "hasUrl": true or false,
  "url": "complete URL string or null"
}}"""
        
        completion = openai_client.chat.completions.create(
            model='gpt-4o',
            messages=[
                {'role': 'system', 'content': 'You are a URL detection assistant. Analyze messages and extract URLs if present. Return only valid JSON.'},
                {'role': 'user', 'content': detection_prompt}
            ],
            temperature=0.1,
            response_format={'type': 'json_object'}
        )
        
        response_text = completion.choices[0].message.content.strip()
        if not response_text:
            return None
        
        data = json.loads(response_text)
        
        if data.get('hasUrl') and data.get('url'):
            url = data.get('url')
            print(f"🔗 GPT-4o detected URL in message: {url}")
            return url
        
        print("ℹ️  GPT-4o found no URL in message")
        return None
    except Exception as error:
        print(f"⚠️  Error detecting URL with GPT-4o, falling back to regex: {error}")
        # Fallback to regex
        url_regex = r'(https?://[^\s]+)'
        urls = re.findall(url_regex, message)
        return urls[0] if urls else None


async def scrape_and_extract_car_data(url: str) -> Dict[str, Any]:
    """
    Steps 2 & 3: Fetch HTML from URL and extract car data using GPT-4o
    Step 2: Fetch and parse HTML
    Step 3: Send HTML to GPT-4o for data extraction
    """
    if not openai_client:
        raise ValueError('OPENAI_API_KEY is not configured')
    
    try:
        print(f'🌐 Step 2: Fetching HTML from URL: {url}')
        
        html_content = None
        
        # Try using Playwright for JavaScript-rendered content first
        if PLAYWRIGHT_AVAILABLE:
            try:
                print("   Using Playwright to render JavaScript content...")
                async with async_playwright() as p:
                    # Launch browser with more realistic settings to avoid bot detection
                    browser = await p.chromium.launch(
                        headless=True,
                        args=[
                            '--disable-blink-features=AutomationControlled',
                            '--disable-dev-shm-usage',
                            '--no-sandbox'
                        ]
                    )
                    
                    # Create a new context with realistic viewport and user agent
                    context = await browser.new_context(
                        viewport={'width': 1920, 'height': 1080},
                        user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        locale='en-US',
                        timezone_id='America/New_York'
                    )
                    
                    page = await context.new_page()
                    
                    # Add extra headers to look more like a real browser
                    await page.set_extra_http_headers({
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.9',
                        'Accept-Encoding': 'gzip, deflate, br',
                        'Connection': 'keep-alive',
                        'Upgrade-Insecure-Requests': '1',
                        'Sec-Fetch-Dest': 'document',
                        'Sec-Fetch-Mode': 'navigate',
                        'Sec-Fetch-Site': 'none',
                        'Cache-Control': 'max-age=0'
                    })
                    
                    # Navigate to the page with multiple wait strategies
                    print("   Navigating to page and waiting for content...")
                    await page.goto(url, wait_until='domcontentloaded', timeout=30000)
                    
                    # Wait for network to be idle
                    try:
                        await page.wait_for_load_state('networkidle', timeout=10000)
                    except:
                        print("   Network didn't become idle, continuing anyway...")
                    
                    # Wait additional time for JavaScript to render
                    await asyncio.sleep(3)
                    
                    # Try to wait for common car listing elements
                    try:
                        # Wait for any of these common elements that indicate page loaded
                        await page.wait_for_selector('h1, [class*="price"], [class*="Price"], [data-testid*="price"]', timeout=5000)
                    except:
                        print("   Couldn't find expected elements, but continuing...")
                    
                    # Scroll down to trigger lazy loading
                    await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                    await asyncio.sleep(1)
                    await page.evaluate('window.scrollTo(0, 0)')
                    await asyncio.sleep(1)
                    
                    # Check if we got an error page
                    page_text_preview = await page.inner_text('body')
                    page_title = await page.title()
                    
                    if 'unavailable' in page_text_preview.lower() or 'error' in page_text_preview.lower() or len(page_text_preview) < 500:
                        print(f"   ⚠️  Page may be showing an error or is blocked.")
                        print(f"   Page title: {page_title}")
                        print(f"   Content preview: {page_text_preview[:200]}...")
                        print(f"   ⚠️  Autotrader may be blocking automated access. Will try to extract what we can.")
                    
                    # Get the fully rendered HTML (even if it's an error page, might have some data)
                    html_content = await page.content()
                    await browser.close()
                    
                    print(f"✅ Step 2 complete: Fetched {len(html_content)} characters of HTML")
            except Exception as playwright_error:
                print(f"⚠️  Playwright failed ({playwright_error}), falling back to requests...")
                html_content = None
        
        # Fallback to requests if Playwright not available or failed
        if not html_content:
            print("   Using requests (may miss JavaScript-rendered content)...")
            response = requests.get(
                url,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                },
                timeout=10
            )
            html_content = response.text
            print(f"✅ Step 2 complete: Fetched {len(html_content)} characters of HTML")
        
        # Parse HTML with BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Try to find JSON-LD structured data first (many sites use this)
        json_ld_data = None
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                json_ld_data = json.loads(script.string)
                print(f"📋 Found JSON-LD structured data")
                break
            except:
                continue
        
        # Remove script and style elements first
        for script in soup(["script", "style", "noscript"]):
            script.decompose()
        
        # Extract text from key elements that typically contain car info
        relevant_text_parts = []
        
        # Get title/heading text (important for car listings)
        for tag in soup.find_all(['h1', 'h2', 'h3', 'h4', 'title']):
            text = tag.get_text(strip=True)
            if text and len(text) > 0:
                relevant_text_parts.append(text)
        
        # Get all text that contains numbers (likely prices, miles, years)
        # Look for patterns like $XX,XXX or XX,XXX miles
        for tag in soup.find_all(['span', 'div', 'p', 'td', 'li']):
            text = tag.get_text(strip=True)
            # Include if it has price indicators, numbers, or car-related keywords
            if any(indicator in text.lower() for indicator in ['$', 'price', 'miles', 'mileage', 'year', 'make', 'model', 'vin', 'odometer']):
                if text and len(text) > 0 and len(text) < 200:  # Avoid huge blocks
                    relevant_text_parts.append(text)
        
        # Get main content areas
        for tag in soup.find_all(['main', 'article', 'section']):
            text = tag.get_text(strip=True)
            if text and len(text) > 100:  # Only substantial content
                relevant_text_parts.append(text[:1000])  # Limit each section
        
        # Also extract from data attributes and meta tags
        for meta in soup.find_all('meta'):
            content = meta.get('content', '')
            property_attr = meta.get('property', '')
            if content and ('price' in property_attr.lower() or 'vehicle' in property_attr.lower()):
                relevant_text_parts.append(content)
        
        # Get all visible text as comprehensive fallback
        all_text = soup.get_text(separator=' ', strip=True)
        
        # Combine all text sources, prioritizing structured data
        if relevant_text_parts:
            page_text = ' '.join(relevant_text_parts)
            # Add a sample of all text to catch anything we missed
            if len(all_text) > len(page_text):
                page_text += ' ' + all_text[:2000]
            print(f"📄 Extracted {len(page_text)} characters from relevant HTML elements")
        else:
            # Fallback to general text extraction
            page_text = all_text
            print(f"📄 Using general text extraction: {len(page_text)} characters")
        
        # Include JSON-LD data if found
        if json_ld_data:
            page_text = f"Structured Data: {json.dumps(json_ld_data, indent=2)}\n\nPage Content: {page_text}"
        
        # Limit text length to avoid token limits (keep first 12000 characters for better extraction)
        limited_text = page_text[:12000]
        print(f"📄 Sending {len(limited_text)} characters to GPT-4o for extraction")
        
        # Log a sample of what we're sending (first 500 chars)
        print(f"📝 Sample content (first 500 chars): {limited_text[:500]}...")
        
        # Step 3: Use GPT-4o to extract car information
        print(f'🤖 Step 3: Sending HTML content to GPT-4o for data extraction...')
        extraction_prompt = f"""Extract car listing information from this web page content. Return ONLY a JSON object with the extracted data. If information is not available, use null. Make sure numbers are actual numbers, not strings.

Required fields:
- make: string (car make, e.g., "Toyota", "Honda")
- model: string (car model, e.g., "Camry", "Civic")
- year: number (car year, e.g., 2020)
- miles: number (number of miles, e.g., 50000)
- listingPrice: number (listing price in dollars, e.g., 15000)
- tireLifeLeft: boolean (whether tires have life left - true for yes, false for no, null if not mentioned)
- titleStatus: string ("clean", "rebuilt", "check_carfax", or null) - "clean" or "rebuilt" if mentioned, "check_carfax" if dealer provided a carfax link, null if not mentioned
- carfaxDamageIncidents: string ("yes", "no", "unsure", "check_carfax", or null) - "yes" if carfax shows prior damage incidents, "no" if it doesn't, "check_carfax" if dealer provided a link but you haven't reviewed it, null if not mentioned
- docFeeQuoted: number (doc fee amount quoted in dollars) - if not mentioned, use null
- docFeeNegotiable: boolean (whether doc fee is negotiable - true for yes, false for no, null if not mentioned)
- docFeeAgreed: number (doc fee agreed upon after negotiation in dollars) - if not mentioned, use null
- lowestPrice: number (lowest price dealer will accept in dollars) - if not mentioned, use null

Web page content:
{limited_text}

Return ONLY valid JSON in this exact format (no markdown, no code blocks):
{{
  "make": "string or null",
  "model": "string or null",
  "year": number or null,
  "miles": number or null,
  "listingPrice": number or null,
  "tireLifeLeft": boolean or null,
  "titleStatus": "string ('clean', 'rebuilt', 'check_carfax') or null",
  "carfaxDamageIncidents": "string ('yes', 'no', 'unsure', 'check_carfax') or null",
  "docFeeQuoted": number or null,
  "docFeeNegotiable": boolean or null,
  "docFeeAgreed": number or null,
  "lowestPrice": number or null
}}"""
        
        completion = openai_client.chat.completions.create(
            model='gpt-4o',
            messages=[
                {'role': 'system', 'content': 'You are a data extraction assistant. Extract structured car listing data from web pages and return only valid JSON.'},
                {'role': 'user', 'content': extraction_prompt}
            ],
            temperature=0.3,
            response_format={'type': 'json_object'}
        )
        
        response_text = completion.choices[0].message.content.strip()
        
        if not response_text:
            raise ValueError('No response from OpenAI')
        
        # Parse JSON response
        data = json.loads(response_text)
        
        # Ensure numbers are actually numbers
        extracted_data = {
            'make': data.get('make') or None,
            'model': data.get('model') or None,
            'year': int(data['year']) if data.get('year') is not None else None,
            'miles': int(data['miles']) if data.get('miles') is not None else None,
            'listingPrice': float(data['listingPrice']) if data.get('listingPrice') is not None else None,
            'tireLifeLeft': bool(data['tireLifeLeft']) if data.get('tireLifeLeft') is not None else None,
            'titleStatus': data.get('titleStatus', '').lower() if data.get('titleStatus') and data.get('titleStatus').lower() in ['clean', 'rebuilt', 'check_carfax'] else None,
            'carfaxDamageIncidents': _normalize_carfax_value(data.get('carfaxDamageIncidents')),
            'docFeeQuoted': float(data['docFeeQuoted']) if data.get('docFeeQuoted') is not None else None,
            'docFeeNegotiable': bool(data['docFeeNegotiable']) if data.get('docFeeNegotiable') is not None else None,
            'docFeeAgreed': float(data['docFeeAgreed']) if data.get('docFeeAgreed') is not None else None,
            'lowestPrice': float(data['lowestPrice']) if data.get('lowestPrice') is not None else None,
            'url': url,
            'extractedAt': datetime.now()
        }
        
        print(f'✅ Step 3 complete: GPT-4o extracted {len([k for k, v in extracted_data.items() if v is not None])} fields from HTML')
        print(f'   Extracted data: {extracted_data}')
        return extracted_data
    except Exception as error:
        print(f'❌ Error in steps 2 or 3 (fetching/scraping URL): {error}')
        raise


def _normalize_carfax_value(value: Any) -> Optional[str]:
    """Normalize carfax damage incidents value"""
    if value is None:
        return None
    if isinstance(value, bool):
        return 'yes' if value else 'no'
    if isinstance(value, str):
        lower = value.lower()
        if lower in ['yes', 'no', 'unsure', 'check_carfax']:
            return lower
    return None


async def build_conversation_transcript(thread_id: str, Message) -> str:
    """Build conversation transcript from messages"""
    from bson import ObjectId
    messages = Message.find({'threadId': ObjectId(thread_id)}, sort=[('timestamp', 1)])
    
    transcript_lines = []
    for msg in messages:
        sender = 'Dealer' if msg['direction'] == 'inbound' else 'You'
        transcript_lines.append(f"{sender}: {msg['body']}")
    
    return '\n'.join(transcript_lines)


async def extract_car_listing_data(conversation_transcript: str) -> Dict[str, Any]:
    """Extract car listing data from conversation using GPT-4o"""
    if not openai_client:
        raise ValueError('OPENAI_API_KEY is not configured')
    
    extraction_prompt = f"""Extract the following information from this conversation between a car buyer and dealer. Return ONLY a JSON object with the extracted data. If information is not available, use null. Make sure numbers are actual numbers, not strings.

Required fields:
- make: string (car make, e.g., "Toyota", "Honda")
- model: string (car model, e.g., "Camry", "Civic")
- year: number (car year, e.g., 2020)
- miles: number (number of miles, e.g., 50000)
- listingPrice: number (listing price in dollars, e.g., 15000)
- tireLifeLeft: boolean (whether tires have life left - true for yes, false for no)
- titleStatus: string ("clean", "rebuilt", "check_carfax", or null) - "clean" or "rebuilt" if mentioned, "check_carfax" if dealer provided a carfax link, null if not mentioned
- carfaxDamageIncidents: string ("yes", "no", "unsure", "check_carfax", or null) - "yes" if carfax shows prior damage incidents, "no" if it doesn't, "check_carfax" if dealer provided a link but you haven't reviewed it, null if not mentioned
- docFeeQuoted: number (doc fee amount quoted in dollars, e.g., 500)
- docFeeNegotiable: boolean (whether doc fee is negotiable - true for yes, false for no)
- docFeeAgreed: number (doc fee agreed upon after negotiation in dollars, e.g., 400)
- lowestPrice: number (lowest price dealer will accept in dollars, e.g., 14000)

Conversation transcript:
{conversation_transcript}

Return ONLY valid JSON in this exact format (no markdown, no code blocks):
{{
  "make": "string or null",
  "model": "string or null",
  "year": number or null,
  "miles": number or null,
  "listingPrice": number or null,
  "tireLifeLeft": boolean or null,
  "titleStatus": "string ('clean', 'rebuilt', 'check_carfax') or null",
  "carfaxDamageIncidents": "string ('yes', 'no', 'unsure', 'check_carfax') or null",
  "docFeeQuoted": number or null,
  "docFeeNegotiable": boolean or null,
  "docFeeAgreed": number or null,
  "lowestPrice": number or null
}}"""
    
    try:
        completion = openai_client.chat.completions.create(
            model='gpt-4o',
            messages=[
                {'role': 'system', 'content': 'You are a data extraction assistant. Extract structured data from conversations and return only valid JSON.'},
                {'role': 'user', 'content': extraction_prompt}
            ],
            temperature=0.3,
            response_format={'type': 'json_object'}
        )
        
        response_text = completion.choices[0].message.content.strip()
        
        if not response_text:
            raise ValueError('No response from OpenAI')
        
        data = json.loads(response_text)
        
        # Ensure numbers are actually numbers
        extracted_data = {
            'make': data.get('make') or None,
            'model': data.get('model') or None,
            'year': int(data['year']) if data.get('year') is not None else None,
            'miles': int(data['miles']) if data.get('miles') is not None else None,
            'listingPrice': float(data['listingPrice']) if data.get('listingPrice') is not None else None,
            'tireLifeLeft': bool(data['tireLifeLeft']) if data.get('tireLifeLeft') is not None else None,
            'titleStatus': data.get('titleStatus', '').lower() if data.get('titleStatus') and data.get('titleStatus').lower() in ['clean', 'rebuilt', 'check_carfax'] else None,
            'carfaxDamageIncidents': _normalize_carfax_value(data.get('carfaxDamageIncidents')),
            'docFeeQuoted': float(data['docFeeQuoted']) if data.get('docFeeQuoted') is not None else None,
            'docFeeNegotiable': bool(data['docFeeNegotiable']) if data.get('docFeeNegotiable') is not None else None,
            'docFeeAgreed': float(data['docFeeAgreed']) if data.get('docFeeAgreed') is not None else None,
            'lowestPrice': float(data['lowestPrice']) if data.get('lowestPrice') is not None else None
        }
        
        return extracted_data
    except Exception as error:
        print(f'Error extracting car listing data: {error}')
        raise


def dealer_says_will_get_back(message: str) -> bool:
    """Detect if dealer says they'll get back to the agent"""
    patterns = [
        r'will get back',
        r'get back to you',
        r'will update you',
        r'update you as soon',
        r'will reach out',
        r'reach out as soon',
        r'will be in touch',
        r'be in touch as soon',
        r'working to get',
        r'gathering.*information',
        r'collecting.*information',
        r'looking into',
        r'will provide',
        r'provide.*as soon'
    ]
    
    message_lower = message.lower()
    return any(re.search(pattern, message_lower) for pattern in patterns)


async def message_contains_new_information(message: str, known_data: Optional[Dict[str, Any]] = None) -> bool:
    """Check if message contains new information vs just acknowledgment"""
    if not openai_client:
        # Fallback: if no API key, assume it might have info
        return True
    
    # Check for common acknowledgment phrases
    acknowledgment_patterns = [
        r'sounds good',
        r'will get back',
        r'get back to you',
        r'will update you',
        r'update you as soon',
        r'will reach out',
        r'reach out as soon',
        r'will be in touch',
        r'be in touch as soon',
        r'working to get',
        r'gathering.*information',
        r'collecting.*information',
        r'looking into',
        r'will provide',
        r'provide.*as soon',
        r'thank you for your patience',
        r'thank you for checking in',
        r'still working',
        r'still gathering',
        r'still collecting'
    ]
    
    message_lower = message.lower()
    is_just_acknowledgment = (
        any(re.search(pattern, message_lower) for pattern in acknowledgment_patterns) and
        not re.search(r'\d+', message) and  # No numbers
        '$' not in message  # No dollar signs
    )
    
    if is_just_acknowledgment:
        return False
    
    # Use GPT to check if message contains new information
    try:
        known_info_section = ''
        if known_data:
            known_fields = []
            if known_data.get('make'):
                known_fields.append(f"- Car make: {known_data['make']}")
            if known_data.get('model'):
                known_fields.append(f"- Car model: {known_data['model']}")
            if known_data.get('year'):
                known_fields.append(f"- Car year: {known_data['year']}")
            if known_data.get('miles') is not None:
                known_fields.append(f"- Number of miles: {known_data['miles']:,}")
            if known_data.get('listingPrice') is not None:
                known_fields.append(f"- Listing price: ${known_data['listingPrice']:,}")
            if known_data.get('tireLifeLeft') is not None:
                known_fields.append(f"- Tires have life left: {'Yes' if known_data['tireLifeLeft'] else 'No'}")
            if known_data.get('titleStatus'):
                title_display = 'Check Carfax (link provided)' if known_data['titleStatus'] == 'check_carfax' else known_data['titleStatus']
                known_fields.append(f"- Title status: {title_display}")
            if known_data.get('carfaxDamageIncidents') is not None:
                carfax_display = {
                    'yes': 'Yes',
                    'no': 'No',
                    'unsure': 'Unsure',
                    'check_carfax': 'Check Carfax (link provided)'
                }.get(known_data['carfaxDamageIncidents'], 'Unknown')
                known_fields.append(f"- Carfax damage incidents: {carfax_display}")
            if known_data.get('docFeeQuoted') is not None:
                known_fields.append(f"- Doc fee quoted: ${known_data['docFeeQuoted']:,}")
            if known_data.get('docFeeNegotiable') is not None:
                known_fields.append(f"- Doc fee negotiable: {'Yes' if known_data['docFeeNegotiable'] else 'No'}")
            if known_data.get('docFeeAgreed') is not None:
                known_fields.append(f"- Doc fee agreed: ${known_data['docFeeAgreed']:,}")
            if known_data.get('lowestPrice') is not None:
                known_fields.append(f"- Lowest price: ${known_data['lowestPrice']:,}")
            
            if known_fields:
                known_info_section = f"\n\nKnown information:\n" + '\n'.join(known_fields)
        
        prompt = f"""Does this dealer message contain NEW information about the car (make, model, year, miles, price, tire condition, title status, carfax, doc fee, etc.) that is not already known?{known_info_section}

Dealer message: "{message}"

Respond with ONLY "YES" if the message contains new information (like specific numbers, prices, details about the car, etc.), or "NO" if it's just an acknowledgment, confirmation, or promise to get back later."""
        
        completion = openai_client.chat.completions.create(
            model='gpt-4o',
            messages=[
                {'role': 'system', 'content': 'You are a helpful assistant that determines if a message contains new information.'},
                {'role': 'user', 'content': prompt}
            ],
            temperature=0.3,
            max_tokens=10
        )
        
        response = completion.choices[0].message.content.strip().upper()
        return response == 'YES'
    except Exception as error:
        print(f'Error checking for new information: {error}')
        # On error, assume it might have info to be safe
        return True


async def get_ai_response(conversation_transcript: str, known_data: Optional[Dict[str, Any]] = None, is_waiting_for_response: bool = False) -> str:
    """Get AI agent response using GPT-4o"""
    if not openai_client:
        raise ValueError('OPENAI_API_KEY is not configured')
    
    # Build known information section
    known_info_section = ''
    if known_data:
        known_fields = []
        if known_data.get('make'):
            known_fields.append(f"- Car make: {known_data['make']}")
        if known_data.get('model'):
            known_fields.append(f"- Car model: {known_data['model']}")
        if known_data.get('year'):
            known_fields.append(f"- Car year: {known_data['year']}")
        if known_data.get('miles') is not None:
            known_fields.append(f"- Number of miles: {known_data['miles']:,}")
        if known_data.get('listingPrice') is not None:
            known_fields.append(f"- Listing price: ${known_data['listingPrice']:,}")
        if known_data.get('tireLifeLeft') is not None:
            known_fields.append(f"- Tires have life left: {'Yes' if known_data['tireLifeLeft'] else 'No'}")
        if known_data.get('titleStatus'):
            title_display = 'Check Carfax (link provided)' if known_data['titleStatus'] == 'check_carfax' else known_data['titleStatus']
            known_fields.append(f"- Title status: {title_display}")
        if known_data.get('carfaxDamageIncidents') is not None:
            carfax_display = {
                'yes': 'Yes',
                'no': 'No',
                'unsure': 'Unsure',
                'check_carfax': 'Check Carfax (link provided)'
            }.get(known_data['carfaxDamageIncidents'], 'Unknown')
            known_fields.append(f"- Carfax damage incidents: {carfax_display}")
        if known_data.get('docFeeQuoted') is not None:
            known_fields.append(f"- Doc fee quoted: ${known_data['docFeeQuoted']:,}")
        if known_data.get('docFeeNegotiable') is not None:
            known_fields.append(f"- Doc fee negotiable: {'Yes' if known_data['docFeeNegotiable'] else 'No'}")
        if known_data.get('docFeeAgreed') is not None:
            known_fields.append(f"- Doc fee agreed: ${known_data['docFeeAgreed']:,}")
        if known_data.get('lowestPrice') is not None:
            known_fields.append(f"- Lowest price: ${known_data['lowestPrice']:,}")
        
        if known_fields:
            known_info_section = f"\n\nIMPORTANT: You already have the following information (do NOT ask for these again):\n" + '\n'.join(known_fields) + "\n\nOnly ask for information you don't already have."
    
    system_prompt = f"""You are an expert used car buyer. You are in a conversation with a used car dealer, who is selling a car that you indicated interest in online.

Your task is to get the following pieces of information from the dealer:
1. Car make
2. Car model
3. Car year
4. Number of miles on the car
5. Listing price
6. Whether the tires have life left (yes or no)
7. Is it a clean title or rebuilt title (clean or rebuilt)
8. Does the carfax show any prior damage incidents (yes or no)
9. Doc fee amount (the amount they quote)
10. Whether the doc fee is negotiable (yes or no)
11. Doc fee agreed upon (after negotiation, if applicable)
12. Lowest price dealer will accept{known_info_section}

Guidelines:
1. Maintain a professional, but not overly friendly tone. Do not sound too robotic - you are impersonating a human who is a savvy used car buyer. Do not use perfect punctuation (e.g., 'Can you remind me the car make/model and year? Appreciate it').
2. Try to obtain the pieces of information above in order (e.g., don't ask for the age of the tires before you know the car's make)
3. Where it makes sense, I would ask for the car make, model, year and number of miles in one message
4. Once you have all information from items 1-9 (make, model, year, miles, listing price, tire life status, title status, carfax damage incidents, and doc fee quoted), ask about item 10 (whether the doc fee is negotiable). If the doc fee is negotiable and greater than $150, try to negotiate a lower doc fee. Then negotiate the listing price. If the tires do not have life left, if it's a rebuilt title, or if there are carfax damage incidents, mention those as reasons why you are trying to negotiate. Do not attempt an unreasonable amount of negotiation - if the dealer is not willing to negotiate, move on to the next question. If they lower the price more than 15% from the listing price, accept the deal. After negotiation, record the final agreed-upon doc fee in item 11.
5. DO NOT ask for information you already have. If you already know the make, model, year, miles, or listing price, skip asking for those and move on to information you don't have.
6. CRITICAL: If the dealer says that they will work on getting information for you, will get back to you, will update you, or similar phrases indicating they need time to gather information, you should acknowledge this. However, if the dealer ALSO asks a question in the same message, you must answer their question first, then acknowledge that you'll wait. For example, if they say "I'll discuss with my GM. Do you have a trade?", respond with something like "No trade, and I'll be financing. Thanks!" and then return '# WAITING #'. If they only say they'll get back without asking a question, respond with ONLY a simple "Thank you" or "Thanks" and then return '# WAITING #'. This tells the system to stop responding until the dealer provides actual new information.
7. If the dealer indicates that they have sent a link to the carfax (whether in the thread or in a separate message), do not continue asking for the carfax, and just make the values for 7 and 8 'check_carfax'.
8. CRITICAL: If the dealer asks you to come in and see the car, or suggests scheduling a visit, BEFORE you have all the information you need (items 1-12), you must deflect politely. Say something like "I'd like to ask a few more questions first" or "Let me get a bit more info before we schedule a visit" and then continue asking for the missing information. Only agree to schedule a visit AFTER you have all the information and are ready to return '#SCHEDULE#'.

Return nothing but the message you would like to send the dealer (e.g., do not pre-pend "You: " or something similar to message). If the dealer says they'll get back to you, return '# WAITING #' after saying thank you. Once you have captured ALL of the information above (items 1-12), return '#SCHEDULE#' to indicate you're ready to schedule a visit. Do not return '#SCHEDULE#' unless you are absolutely certain you have all of the information required."""
    
    user_prompt = f"""Here is the transcript of the conversation so far:

{conversation_transcript or '(No conversation yet)'}

Please output what you think your next message to the dealer should be."""
    
    try:
        completion = openai_client.chat.completions.create(
            model='gpt-4o',
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt}
            ],
            temperature=0.7,
            max_tokens=200
        )
        
        response = completion.choices[0].message.content.strip()
        
        if not response:
            raise ValueError('No response from OpenAI')
        
        return response
    except Exception as error:
        print(f'Error calling OpenAI: {error}')
        raise


async def send_sms(to: str, message: str, retries: int = 3) -> Dict[str, Any]:
    """Send SMS via Mobile Text Alerts with retry logic"""
    if not MTA_API_KEY:
        raise ValueError('MTA_API_KEY is not configured')
    
    payload = {
        'subscribers': [to],
        'message': message,
        'longcodeId': MTA_LONGCODE_ID
    }
    
    for attempt in range(1, retries + 1):
        try:
            print(f'Sending message (attempt {attempt}/{retries}): {message}')
            
            if attempt > 1:
                print(f'Sending payload: {payload}')
            
            response = requests.post(
                f'{MTA_API_BASE_URL}/send',
                json=payload,
                headers={
                    'Authorization': f'Bearer {MTA_API_KEY}',
                    'Content-Type': 'application/json'
                },
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as error:
            is_network_error = (
                isinstance(error, requests.exceptions.ConnectionError) or
                isinstance(error, requests.exceptions.Timeout)
            )
            
            if is_network_error and attempt < retries:
                delay = min(1000 * (2 ** (attempt - 1)), 5000)  # Exponential backoff, max 5 seconds
                print(f'Network error on attempt {attempt}, retrying in {delay}ms... {error}')
                await asyncio.sleep(delay / 1000)
                continue
            
            # If it's the last attempt or not a network error, raise
            print(f'Error sending SMS via Mobile Text Alerts: {error}')
            if attempt == 1:
                print(f'Request payload was: {payload}')
            raise


# ==================== VISIT SCHEDULING AGENT ====================

def check_if_message_about_visit_scheduling(message: str) -> bool:
    """Check if dealer message is about scheduling, modifying, or canceling a visit"""
    if not openai_client:
        # Fallback to keyword matching
        visit_keywords = [
            'visit', 'appointment', 'schedule', 'come in', 'come by', 'stop by',
            'when can you', 'what time', 'available', 'availability', 'cancel',
            'reschedule', 'change time', 'change date', 'meet', 'see the car',
            'test drive', 'view', 'inspect'
        ]
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in visit_keywords)
    
    try:
        prompt = f"""Does this dealer message ask about scheduling a visit, appointment, or meeting to see the car? This includes:
- Asking when the buyer can come in/visit
- Suggesting a time to meet
- Asking about availability
- Requesting to schedule an appointment
- Asking to reschedule or cancel a visit
- Asking about test driving or viewing the car

Message: "{message}"

Respond with ONLY "YES" if it's about visit scheduling, or "NO" if it's not."""
        
        completion = openai_client.chat.completions.create(
            model='gpt-4o',
            messages=[
                {'role': 'system', 'content': 'You are a helpful assistant that determines if a message is about scheduling visits or appointments.'},
                {'role': 'user', 'content': prompt}
            ],
            temperature=0.3,
            max_tokens=10
        )
        
        response = completion.choices[0].message.content.strip().upper()
        return response == 'YES'
    except Exception as error:
        print(f'Error checking if message is about visit scheduling: {error}')
        # On error, use keyword fallback
        visit_keywords = [
            'visit', 'appointment', 'schedule', 'come in', 'come by', 'stop by',
            'when can you', 'what time', 'available', 'availability', 'cancel',
            'reschedule', 'change time', 'change date', 'meet', 'see the car',
            'test drive', 'view', 'inspect'
        ]
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in visit_keywords)


def get_visit_availability(start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
    """Get available time slots for visits between start_date and end_date"""
    from models import Visit
    from bson import ObjectId
    
    # Find all visits in the date range
    visits = Visit.find({
        "scheduledTime": {
            "$gte": start_date,
            "$lte": end_date
        },
        "status": {"$ne": "cancelled"}
    })
    
    # Return existing visits (for context)
    return [
        {
            "visitId": str(v["_id"]),
            "scheduledTime": v["scheduledTime"].isoformat() if isinstance(v["scheduledTime"], datetime) else v["scheduledTime"],
            "dealerPhoneNumber": v.get("dealerPhoneNumber"),
            "status": v.get("status", "scheduled")
        }
        for v in visits
    ]


def create_visit(thread_id: str, scheduled_time: datetime, dealer_phone_number: str, car_listing_id: Optional[str] = None, notes: Optional[str] = None) -> str:
    """Create a new visit"""
    from models import Visit
    from bson import ObjectId
    
    visit_data = {
        "threadId": ObjectId(thread_id) if isinstance(thread_id, str) else thread_id,
        "scheduledTime": scheduled_time,
        "dealerPhoneNumber": dealer_phone_number,
        "status": "scheduled",
        "createdAt": datetime.now(),
        "updatedAt": datetime.now()
    }
    
    if car_listing_id:
        visit_data["carListingId"] = ObjectId(car_listing_id) if isinstance(car_listing_id, str) else car_listing_id
    
    if notes:
        visit_data["notes"] = notes
    
    visit_id = Visit.create(visit_data)
    print(f"✅ Created visit {visit_id} for thread {thread_id} at {scheduled_time}")
    return visit_id


def modify_visit(visit_id: str, scheduled_time: Optional[datetime] = None, notes: Optional[str] = None, status: Optional[str] = None) -> bool:
    """Modify an existing visit"""
    from models import Visit
    
    update_data = {"updatedAt": datetime.now()}
    
    if scheduled_time:
        update_data["scheduledTime"] = scheduled_time
    
    if notes is not None:
        update_data["notes"] = notes
    
    if status:
        update_data["status"] = status
    
    result = Visit.update_one({"_id": ObjectId(visit_id)}, update_data)
    print(f"✅ Modified visit {visit_id}")
    return result.modified_count > 0


def delete_visit(visit_id: str) -> bool:
    """Delete a visit"""
    from models import Visit
    
    result = Visit.delete_one({"_id": ObjectId(visit_id)})
    print(f"✅ Deleted visit {visit_id}")
    return result.deleted_count > 0


async def get_scheduling_agent_response(conversation_transcript: str, thread_id: str, dealer_phone_number: str) -> Optional[str]:
    """Get scheduling agent response for visit-related messages"""
    if not openai_client:
        return None
    
    from models import Visit, CarListing, Thread
    from bson import ObjectId
    
    # Get existing visits for this thread
    existing_visits = Visit.find({"threadId": ObjectId(thread_id)})
    visits_info = []
    for visit in existing_visits:
        visits_info.append({
            "visitId": str(visit["_id"]),
            "scheduledTime": visit["scheduledTime"].isoformat() if isinstance(visit["scheduledTime"], datetime) else str(visit["scheduledTime"]),
            "status": visit.get("status", "scheduled"),
            "notes": visit.get("notes", "")
        })
    
    # Get car listing info if available
    car_listing = CarListing.find_one({"threadId": ObjectId(thread_id)})
    car_info = ""
    if car_listing:
        car_info = f"Car: {car_listing.get('year', '')} {car_listing.get('make', '')} {car_listing.get('model', '')}"
    
    # Get thread info
    thread = Thread.find_by_id(thread_id)
    
    system_prompt = f"""You are a scheduling assistant for car dealership visits. Your job is to help schedule, modify, or cancel visits to see cars at dealerships.

You have access to the following tools:
1. get_visit_availability(start_date, end_date) - Get existing visits in a date range
2. create_visit(thread_id, scheduled_time, dealer_phone_number, car_listing_id, notes) - Create a new visit
3. modify_visit(visit_id, scheduled_time, notes, status) - Modify an existing visit
4. delete_visit(visit_id) - Delete/cancel a visit

Current context:
- Thread ID: {thread_id}
- Dealer Phone: {dealer_phone_number}
- {car_info}
- Existing visits: {json.dumps(visits_info, indent=2) if visits_info else 'None'}

IMPORTANT RULES:
1. All times should be in Central Time (CT)
2. Only create/modify visits when you have ALL necessary information:
   - For creating: You need a specific date AND time
   - For modifying: You need the visit ID and the new information
3. If the dealer asks about availability but doesn't suggest a specific time, ask them what times work for them
4. If the dealer suggests a time, confirm it and create the visit
5. If the dealer wants to reschedule, use modify_visit
6. If the dealer wants to cancel, use delete_visit or set status to "cancelled"
7. Be friendly and professional
8. Always confirm the date and time before creating a visit
9. If you don't have enough information, ask for it before taking action

When you want to use a tool, respond with:
TOOL_CALL: tool_name(arg1=value1, arg2=value2)

After using a tool, you'll get the result. Then provide a natural response to the dealer.

If you need to ask for more information, just respond naturally without using tools."""
    
    user_prompt = f"""Here is the conversation transcript:

{conversation_transcript}

What should you do? If you need to use a tool, use the TOOL_CALL format. Otherwise, respond naturally to the dealer."""
    
    try:
        completion = openai_client.chat.completions.create(
            model='gpt-4o',
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt}
            ],
            temperature=0.7,
            max_tokens=300
        )
        
        response = completion.choices[0].message.content.strip()
        
        # Check if response contains a tool call
        if "TOOL_CALL:" in response:
            # Extract tool call
            tool_call_line = [line for line in response.split('\n') if 'TOOL_CALL:' in line][0]
            tool_call = tool_call_line.replace('TOOL_CALL:', '').strip()
            
            # Parse and execute tool call
            try:
                # Simple parsing - extract function name and arguments
                if 'get_visit_availability' in tool_call:
                    # This would need date parsing - for now, skip
                    pass
                elif 'create_visit' in tool_call:
                    # Extract scheduled_time from tool_call
                    # This is simplified - in production, you'd want better parsing
                    import re
                    from dateutil import parser as date_parser
                    
                    # Try to extract datetime from the response or conversation
                    # For now, we'll need to parse the conversation for date/time
                    time_match = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', conversation_transcript)
                    if time_match:
                        # This is a simplified version - you'd want better date parsing
                        pass
                elif 'modify_visit' in tool_call:
                    # Extract visit_id and new info
                    pass
                elif 'delete_visit' in tool_call:
                    # Extract visit_id
                    pass
            except Exception as tool_error:
                print(f"Error executing tool call: {tool_error}")
        
        # For now, return the response (the agent will handle tool calls in a more sophisticated way)
        # We'll implement a simpler version that extracts date/time from the conversation
        return response
    except Exception as error:
        print(f'Error getting scheduling agent response: {error}')
        return None


async def process_visit_scheduling(conversation_transcript: str, thread_id: str, dealer_phone_number: str, latest_message: str) -> Optional[Dict[str, Any]]:
    """Process visit scheduling - check availability and schedule visits"""
    if not openai_client:
        return None
    
    from models import Visit, CarListing
    from bson import ObjectId
    import re
    
    # Central Time timezone
    ct_tz = gettz('America/Chicago')
    
    # Get today's date in Central Time for reference
    now_ct = datetime.now(ct_tz)
    today_str = now_ct.strftime('%Y-%m-%d')
    today_day_name = now_ct.strftime('%A')
    
    # Get availability for next 2 days
    end_date = now_ct + timedelta(days=2)
    existing_visits = get_visit_availability(now_ct, end_date)
    
    # Convert existing visits to a more readable format for GPT
    availability_info = []
    for visit in existing_visits:
        visit_time = datetime.fromisoformat(visit['scheduledTime']) if isinstance(visit['scheduledTime'], str) else visit['scheduledTime']
        if visit_time.tzinfo is None:
            visit_time = visit_time.replace(tzinfo=ct_tz)
        else:
            visit_time = visit_time.astimezone(ct_tz)
        availability_info.append({
            "time": visit_time.strftime('%A, %B %d at %I:%M %p CT'),
            "datetime": visit_time.isoformat()
        })
    
    availability_text = json.dumps(availability_info, indent=2) if availability_info else "No visits scheduled in the next 2 days"
    
    try:
        # Use GPT to extract visit scheduling information and determine response
        extraction_prompt = f"""You are a scheduling assistant. Analyze the conversation to determine if the dealer has proposed a specific date and time for a visit.

IMPORTANT: Today is {today_day_name}, {today_str} (Central Time). When the dealer mentions a day name like "Saturday" or "Monday", interpret it relative to today's date.

Latest dealer message: "{latest_message}"

Full conversation:
{conversation_transcript}

Your existing scheduled visits in the next 2 days:
{availability_text}

If the dealer has proposed a specific date and time, extract:
- dealer_proposed_date: The date (format: YYYY-MM-DD). For relative dates like "Sunday" or "tomorrow", calculate the actual date based on today ({today_str}).
- dealer_proposed_time: The time (format: HH:MM in 24-hour format, Central Time)
- dealer_proposed_datetime: Combined datetime in ISO format (YYYY-MM-DDTHH:MM:SS)

If the dealer has NOT proposed a specific time (just asked to schedule or come in), set dealer_proposed_date and dealer_proposed_time to null.

Return ONLY valid JSON:
{{
  "dealer_proposed_date": "YYYY-MM-DD or null",
  "dealer_proposed_time": "HH:MM or null",
  "dealer_proposed_datetime": "YYYY-MM-DDTHH:MM:SS or null"
}}"""
        
        completion = openai_client.chat.completions.create(
            model='gpt-4o',
            messages=[
                {'role': 'system', 'content': 'You are a data extraction assistant. Extract visit scheduling information from conversations.'},
                {'role': 'user', 'content': extraction_prompt}
            ],
            temperature=0.3,
            response_format={'type': 'json_object'}
        )
        
        response_text = completion.choices[0].message.content.strip()
        data = json.loads(response_text)
        
        dealer_date = data.get('dealer_proposed_date')
        dealer_time = data.get('dealer_proposed_time')
        dealer_datetime_str = data.get('dealer_proposed_datetime')
        
        # Get car listing if available
        car_listing = CarListing.find_one({"threadId": ObjectId(thread_id)})
        car_listing_id = str(car_listing["_id"]) if car_listing else None
        
        # If dealer proposed a specific time, check availability
        if dealer_date and dealer_time:
            try:
                # Parse the proposed datetime
                if dealer_datetime_str:
                    proposed_time = datetime.fromisoformat(dealer_datetime_str.replace('Z', '+00:00'))
                else:
                    datetime_str = f"{dealer_date} {dealer_time}"
                    proposed_time = date_parser.parse(datetime_str, default=now_ct)
                
                # Ensure timezone
                if proposed_time.tzinfo is None:
                    proposed_time = proposed_time.replace(tzinfo=ct_tz)
                else:
                    proposed_time = proposed_time.astimezone(ct_tz)
                
                # Validate it's not in the past
                if proposed_time < now_ct:
                    # Propose a time instead
                    result = await propose_available_time(now_ct, end_date, existing_visits, ct_tz, thread_id, dealer_phone_number, car_listing_id)
                    return result if isinstance(result, dict) else {"message": result, "visit_scheduled": False}
                
                # Check if the proposed time conflicts with existing visits
                # Allow visits within 1 hour of each other (buffer time)
                conflict = False
                for visit in existing_visits:
                    visit_time = datetime.fromisoformat(visit['scheduledTime']) if isinstance(visit['scheduledTime'], str) else visit['scheduledTime']
                    if visit_time.tzinfo is None:
                        visit_time = visit_time.replace(tzinfo=ct_tz)
                    else:
                        visit_time = visit_time.astimezone(ct_tz)
                    
                    time_diff = abs((proposed_time - visit_time).total_seconds())
                    if time_diff < 3600:  # Less than 1 hour apart
                        conflict = True
                        break
                
                if conflict:
                    # Propose an alternative time
                    alternative_time = await find_next_available_time(proposed_time, existing_visits, ct_tz, end_date)
                    if alternative_time:
                        visit_id = create_visit(thread_id, alternative_time, dealer_phone_number, car_listing_id)
                        return {
                            "message": f"I'm not available at that exact time, but how about {alternative_time.strftime('%A, %B %d at %I:%M %p')} Central Time? I've scheduled it for then.",
                            "visit_scheduled": True
                        }
                    else:
                        result = await propose_available_time(now_ct, end_date, existing_visits, ct_tz, thread_id, dealer_phone_number, car_listing_id)
                        return result if isinstance(result, dict) else {"message": result, "visit_scheduled": False}
                else:
                    # Time is available, create the visit
                    visit_id = create_visit(thread_id, proposed_time, dealer_phone_number, car_listing_id)
                    return {
                        "message": f"Perfect! I've scheduled a visit for {proposed_time.strftime('%A, %B %d at %I:%M %p')} Central Time. Looking forward to seeing you then!",
                        "visit_scheduled": True
                    }
            except Exception as e:
                print(f"Error processing proposed time: {e}")
                # Fall through to propose a time
                result = await propose_available_time(now_ct, end_date, existing_visits, ct_tz, thread_id, dealer_phone_number, car_listing_id)
                return result if isinstance(result, dict) else {"message": result, "visit_scheduled": False}
        else:
            # Dealer didn't propose a specific time, propose one
            result = await propose_available_time(now_ct, end_date, existing_visits, ct_tz, thread_id, dealer_phone_number, car_listing_id)
            return result if isinstance(result, dict) else {"message": result, "visit_scheduled": False}
    except Exception as error:
        print(f'Error processing visit scheduling: {error}')
        return {
            "message": "I'm ready to schedule a visit. What date and time works for you?",
            "visit_scheduled": False
        }


async def find_next_available_time(proposed_time: datetime, existing_visits: List[Dict[str, Any]], ct_tz, end_date: datetime) -> Optional[datetime]:
    """Find the next available time slot near the proposed time"""
    # Try times around the proposed time (before and after)
    time_slots = []
    
    # Try 30 minutes before and after
    for offset_minutes in [-30, 30, -60, 60, -90, 90]:
        candidate_time = proposed_time + timedelta(minutes=offset_minutes)
        if candidate_time < datetime.now(ct_tz) or candidate_time > end_date:
            continue
        
        # Check if this time conflicts
        conflict = False
        for visit in existing_visits:
            visit_time = datetime.fromisoformat(visit['scheduledTime']) if isinstance(visit['scheduledTime'], str) else visit['scheduledTime']
            if visit_time.tzinfo is None:
                visit_time = visit_time.replace(tzinfo=ct_tz)
            else:
                visit_time = visit_time.astimezone(ct_tz)
            
            time_diff = abs((candidate_time - visit_time).total_seconds())
            if time_diff < 3600:  # Less than 1 hour apart
                conflict = True
                break
        
        if not conflict:
            time_slots.append(candidate_time)
    
    if time_slots:
        # Return the closest one to the proposed time
        time_slots.sort(key=lambda t: abs((t - proposed_time).total_seconds()))
        return time_slots[0]
    
    return None


async def propose_available_time(now_ct: datetime, end_date: datetime, existing_visits: List[Dict[str, Any]], ct_tz, thread_id: str, dealer_phone_number: str, car_listing_id: Optional[str]) -> Dict[str, Any]:
    """Propose an available time within the next 2 days"""
    # Preferred times: 10am, 2pm, 4pm
    preferred_hours = [10, 14, 16]
    
    # Start from tomorrow (or today if it's early enough)
    start_date = now_ct + timedelta(days=1)
    if now_ct.hour < 10:
        start_date = now_ct.replace(hour=10, minute=0, second=0, microsecond=0)
    
    # Try to find an available slot
    current_date = start_date.date()
    end_date_only = end_date.date()
    
    while current_date <= end_date_only:
        for hour in preferred_hours:
            candidate_time = datetime.combine(current_date, datetime.min.time().replace(hour=hour, minute=0))
            if candidate_time.tzinfo is None:
                candidate_time = candidate_time.replace(tzinfo=ct_tz)
            else:
                candidate_time = candidate_time.astimezone(ct_tz)
            
            if candidate_time < now_ct or candidate_time > end_date:
                continue
            
            # Check if this time conflicts
            conflict = False
            for visit in existing_visits:
                visit_time = datetime.fromisoformat(visit['scheduledTime']) if isinstance(visit['scheduledTime'], str) else visit['scheduledTime']
                if visit_time.tzinfo is None:
                    visit_time = visit_time.replace(tzinfo=ct_tz)
                else:
                    visit_time = visit_time.astimezone(ct_tz)
                
                time_diff = abs((candidate_time - visit_time).total_seconds())
                if time_diff < 3600:  # Less than 1 hour apart
                    conflict = True
                    break
            
            if not conflict:
                # Found an available time, create the visit
                visit_id = create_visit(thread_id, candidate_time, dealer_phone_number, car_listing_id)
                return {
                    "message": f"I'll come by at {candidate_time.strftime('%A, %B %d at %I:%M %p')} Central Time - thank you.",
                    "visit_scheduled": True
                }
        
        # Move to next day
        current_date += timedelta(days=1)
    
    # If no preferred time found, try any available time
    current_date = start_date.date()
    while current_date <= end_date_only:
        for hour in range(9, 18):  # 9am to 5pm
            candidate_time = datetime.combine(current_date, datetime.min.time().replace(hour=hour, minute=0))
            if candidate_time.tzinfo is None:
                candidate_time = candidate_time.replace(tzinfo=ct_tz)
            else:
                candidate_time = candidate_time.astimezone(ct_tz)
            
            if candidate_time < now_ct or candidate_time > end_date:
                continue
            
            # Check if this time conflicts
            conflict = False
            for visit in existing_visits:
                visit_time = datetime.fromisoformat(visit['scheduledTime']) if isinstance(visit['scheduledTime'], str) else visit['scheduledTime']
                if visit_time.tzinfo is None:
                    visit_time = visit_time.replace(tzinfo=ct_tz)
                else:
                    visit_time = visit_time.astimezone(ct_tz)
                
                time_diff = abs((candidate_time - visit_time).total_seconds())
                if time_diff < 3600:
                    conflict = True
                    break
            
            if not conflict:
                visit_id = create_visit(thread_id, candidate_time, dealer_phone_number, car_listing_id)
                return {
                    "message": f"How about {candidate_time.strftime('%A, %B %d at %I:%M %p')} Central Time? I've scheduled it for then.",
                    "visit_scheduled": True
                }
        
        current_date += timedelta(days=1)
    
    # If still no time found, suggest they propose a time
    return {
        "message": "I'm pretty booked up over the next couple days. What times work best for you?",
        "visit_scheduled": False
    }

