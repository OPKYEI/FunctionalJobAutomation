"""
AI-First Email-based job application status tracker.

This module scans emails for updates on job applications and updates the status in the tracking system.
Uses AI as the primary method for email analysis and classification.
"""

import imaplib
import email
import re
import os
import csv
import pandas as pd
import json
from datetime import datetime
from email.header import decode_header
from email.utils import parseaddr, parsedate_to_datetime
import time
import logging

# Import OpenAI client if available
try:
    from modules.ai.openaiConnections import ai_create_openai_client, ai_close_openai_client, ai_completion
    AI_AVAILABLE = True
except ImportError:
    try:
        # Alternate import path
        from openai import OpenAI
        AI_AVAILABLE = True
        # Define a dummy ai_completion for fallback
        def ai_completion(client, messages, response_format=None, temperature=0, stream=False):
            return None
    except ImportError:
        AI_AVAILABLE = False
        # Define a dummy ai_completion for fallback
        def ai_completion(client, messages, response_format=None, temperature=0, stream=False):
            return None

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    filename='email_scanner.log'
)
logger = logging.getLogger(__name__)

# Try to import credentials in different formats
try:
    # Try to import the multi-account configuration
    from config.secrets import EMAIL_ACCOUNTS
    print("Using multi-account configuration")
    # Set up single account variables for backward compatibility
    EMAIL_USERNAME = EMAIL_ACCOUNTS[0]["username"]
    EMAIL_PASSWORD = EMAIL_ACCOUNTS[0]["password"]
    IMAP_SERVER = EMAIL_ACCOUNTS[0].get("server", "imap.gmail.com")
    IMAP_PORT = EMAIL_ACCOUNTS[0].get("port", 993)
except ImportError:
    try:
        # Try to import the single account configuration
        from config.secrets import EMAIL_USERNAME, EMAIL_PASSWORD
        print("Using single-account configuration")
        # Default server settings
        IMAP_SERVER = "imap.gmail.com"
        IMAP_PORT = 993
        # Create a multi-account configuration for backward compatibility
        EMAIL_ACCOUNTS = [
            {
                "username": EMAIL_USERNAME,
                "password": EMAIL_PASSWORD,
                "server": IMAP_SERVER,
                "port": IMAP_PORT
            }
        ]
    except ImportError:
        # No valid configuration found
        print("Error: No valid email configuration found in config/secrets.py")
        print("Please add either EMAIL_USERNAME and EMAIL_PASSWORD or EMAIL_ACCOUNTS to your secrets.py file")
        EMAIL_USERNAME = "no-email@example.com"
        EMAIL_PASSWORD = "no-password"
        IMAP_SERVER = "imap.gmail.com"
        IMAP_PORT = 993
        EMAIL_ACCOUNTS = []

# Try to import OpenAI key if available
try:
    from config.secrets import OPENAI_API_KEY
    USE_AI = True
except ImportError:
    OPENAI_API_KEY = None
    USE_AI = False

# Path to the applied jobs CSV
APPLIED_JOBS_CSV = "all excels/all_applied_applications_history.csv"

def clean_text(text):
    """Clean text for better pattern matching."""
    if isinstance(text, bytes):
        text = text.decode('utf-8', errors='ignore')
    # Convert to lowercase and remove extra whitespace
    text = re.sub(r'\s+', ' ', text.lower().strip())
    # Remove email formatting elements
    text = re.sub(r'<[^>]+>', ' ', text)  # Remove HTML tags
    return text

def get_email_content(msg):
    """Extract the text content from an email message."""
    content = ""
    if msg.is_multipart():
        # If the message has multiple parts, extract text from each part
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))
            
            # Skip attachments
            if "attachment" in content_disposition:
                continue
                
            # Extract text content
            if content_type == "text/plain" or content_type == "text/html":
                try:
                    part_content = part.get_payload(decode=True)
                    charset = part.get_content_charset()
                    if charset:
                        part_content = part_content.decode(charset, errors='replace')
                    else:
                        part_content = part_content.decode('utf-8', errors='replace')
                    content += part_content
                except Exception as e:
                    logger.error(f"Error decoding email part: {e}")
    else:
        # If the message is not multipart, extract content directly
        try:
            content = msg.get_payload(decode=True).decode('utf-8', errors='replace')
        except:
            try:
                content = msg.get_payload(decode=True).decode('latin-1', errors='replace')
            except Exception as e:
                logger.error(f"Error decoding email: {e}")
    
    return clean_text(content)

def get_email_subject(msg):
    """Extract and decode the email subject."""
    subject = msg.get("Subject", "")
    decoded_subject = ""
    
    if subject:
        # Decode the subject
        decoded_chunks = decode_header(subject)
        for chunk, encoding in decoded_chunks:
            if isinstance(chunk, bytes):
                if encoding:
                    try:
                        decoded_subject += chunk.decode(encoding, errors='replace')
                    except:
                        decoded_subject += chunk.decode('utf-8', errors='replace')
                else:
                    decoded_subject += chunk.decode('utf-8', errors='replace')
            else:
                decoded_subject += chunk
    
    return clean_text(decoded_subject)

def get_sender_info(msg):
    """Extract the sender's name and email."""
    from_header = msg.get("From", "")
    name, address = parseaddr(from_header)
    
    if name:
        # Decode the name if needed
        decoded_chunks = decode_header(name)
        name = ""
        for chunk, encoding in decoded_chunks:
            if isinstance(chunk, bytes):
                if encoding:
                    try:
                        name += chunk.decode(encoding, errors='replace')
                    except:
                        name += chunk.decode('utf-8', errors='replace')
                else:
                    name += chunk.decode('utf-8', errors='replace')
            else:
                name += chunk
    
    return name.strip(), address.strip().lower()

def get_email_date(msg):
    """
    Get the date from the email header and convert to timezone-naive datetime.
    """
    date_str = msg.get('Date')
    if date_str:
        try:
            # Parse to datetime and convert to timezone-naive by replacing tzinfo
            date = parsedate_to_datetime(date_str)
            # Convert to timezone-naive datetime
            return date.replace(tzinfo=None)
        except:
            pass
    # Default to current time (timezone-naive)
    return datetime.now()

def fuzzy_company_match(email_company, csv_companies, debug=False):
    """
    Enhanced fuzzy matching with better normalization.
    """
    if not email_company:
        return None, 0.0
    
    # Normalize the email company name
    def normalize_company(name):
        # Convert to lowercase
        name = name.lower().strip()
        # Remove all spaces, dots, hyphens
        name_compact = re.sub(r'[\s\-\.]', '', name)
        # Remove common suffixes
        name_base = re.sub(r'\s*(inc|llc|corp|corporation|ltd|limited|company|co|group|services|solutions|technologies|technology|tech|systems|international|global)\.?$', '', name)
        name_base_compact = re.sub(r'[\s\-\.]', '', name_base)
        return name, name_compact, name_base, name_base_compact
    
    email_normalized = normalize_company(email_company)
    best_match = None
    best_score = 0.0
    
    if debug:
        print(f"    Trying to match: '{email_company}' (normalized: {email_normalized[1]})")
    
    for csv_company in csv_companies:
        csv_normalized = normalize_company(str(csv_company))
        
        # Check all variations
        for email_variant in email_normalized:
            for csv_variant in csv_normalized:
                if email_variant and csv_variant:
                    # Exact match of any variant
                    if email_variant == csv_variant:
                        if debug:
                            print(f"        EXACT MATCH with '{csv_company}'!")
                        return csv_company, 1.0
                    
                    # One contains the other
                    if email_variant in csv_variant or csv_variant in email_variant:
                        score = min(len(email_variant), len(csv_variant)) / max(len(email_variant), len(csv_variant))
                        if score > best_score and score > 0.6:
                            best_match = csv_company
                            best_score = score
                            if debug:
                                print(f"        CONTAINS MATCH: '{csv_company}' score={score}")
    
    # Special case for acronyms (M3USA vs M3 USA)
    if not best_match:
        # Check if email_company might be an acronym or compressed version
        email_letters = re.sub(r'[^a-zA-Z0-9]', '', email_company.lower())
        for csv_company in csv_companies:
            csv_letters = re.sub(r'[^a-zA-Z0-9]', '', str(csv_company).lower())
            if email_letters == csv_letters and len(email_letters) > 2:
                if debug:
                    print(f"        ACRONYM/COMPRESSED MATCH: '{csv_company}'")
                return csv_company, 0.85
    
    if debug and best_match:
        print(f"    Best match: '{best_match}' with score {best_score}")
    
    return best_match, best_score

def ai_analyze_job_email(subject, content, sender_name, applications_df):
    """
    Use AI as PRIMARY method to analyze emails and extract all information.
    """
    if not USE_AI or not AI_AVAILABLE:
        return None
        
    try:
        # Get ALL companies for comprehensive matching
        company_list = applications_df['Company'].dropna().unique().tolist()
        
        # Prepare enhanced prompt with VERY CLEAR instructions
        prompt = f"""
        Analyze this email about a job application. Be logical and consistent.

        Email Details:
        From: {sender_name}
        Subject: {subject}
        Content: {content[:2000]}

        My Applications Companies:
        {', '.join(company_list[:100])}
        ... and {len(company_list)-100} more companies

        CRITICAL RULES:

        1. **Job-Related Classification**:
        If an email mentions ANY of these, it IS job-related:
        - "thank you for your interest in [Company]" → IT'S ABOUT YOUR APPLICATION
        - "unable to employ" → IT'S A REJECTION OF YOUR APPLICATION
        - "unable to sponsor visas" → IT'S A REJECTION OF YOUR APPLICATION
        - "pursuing other candidates" → IT'S A REJECTION
        - Any reference to YOUR application, interest, or candidacy
        
        2. **Status Determination**:
        - If it says "unable to employ", "unable to sponsor", "cannot hire" → Status = "Rejected"
        - If it says "pursuing other candidates", "not moving forward" → Status = "Rejected"
        - If it says "unfortunately" + any employment-related statement → Status = "Rejected"
        - DO NOT use "Other" for clear rejections!
        
        3. **Company Matching**:
        - Extract company name (e.g., "uShip" from the email)
        - Match flexibly: "uShip" = "UShip" = "uship"
        
        4. **Confidence**:
        - Clear rejection language = confidence 0.8-0.9
        - Ambiguous = confidence 0.5-0.7
        - Very unclear = confidence 0.3-0.4

        EXAMPLE: If email says "Thank you for your interest in uShip. Unfortunately, we are unable to employ candidates..."
        - is_job_related: TRUE (it's about YOUR interest/application)
        - company_extracted: "uShip"  
        - status: "Rejected" (NOT "Other"!)
        - confidence: 0.8+ (it's clearly a rejection)
        IMPORTANT: For company matching, be very flexible:
            - Ignore spaces, hyphens, dots (M3 USA = M3USA = M-3-USA)
            - Ignore suffixes (Inc, LLC, Corp, Corporation, Ltd)
            - Try partial matches (if email says "m3usa", match with "M3 USA Corporation")
            - Common variations: 
              - "Company" vs "Company Inc" vs "Company LLC"
              - "CompanyName" vs "Company Name" 
              - Acronyms vs full names

            If you find a company that seems like a match but with different formatting, 
            return it as company_match anyway. For example:
            - Email says "m3usa" → match with "M3 USA" in the list
            - Email says "Google" → match with "Google LLC" in the list
        Respond in JSON:
        {{
          "is_job_related": true/false,
          "company_extracted": "company name from email",
          "company_match": "match from list or null",
          "status": "Rejected|Interview Scheduled|Offered|Assessment|Applied|Other",
          "confidence": 0.1-1.0,
          "job_id": null,
          "interview_date": null,
          "reasoning": "explanation"
        }}
        """
        
        # Create AI client and get response
        client = ai_create_openai_client()
        if not client:
            print("    ❌ Failed to create AI client")
            return None
            
        messages = [{"role": "user", "content": prompt}]
        
        # Get AI response
        result = ai_completion(
            client, 
            messages, 
            response_format={"type": "json_object"},
            temperature=0.1,
            stream=False
        )
        
        # Debug: print what we got
        print(f"    🔍 AI raw result type: {type(result)}")
        
        # Handle MockChatCompletion object
        parsed_result = None
        
        if result is None:
            print("    ❌ AI returned None")
            return None
        
        # Check if it's a MockChatCompletion object
        if hasattr(result, 'choices') and result.choices:
            # Extract content from the MockChatCompletion object
            try:
                message_content = result.choices[0].message.content
                print(f"    🔍 Extracted content from MockChatCompletion")
                
                # Parse the content
                if isinstance(message_content, str):
                    try:
                        parsed_result = json.loads(message_content)
                    except json.JSONDecodeError as e:
                        print(f"    ❌ JSON decode error: {e}")
                        # If JSON parsing failed, return None - don't create fake data
                        return None
                elif isinstance(message_content, dict):
                    parsed_result = message_content
                else:
                    print(f"    ❌ Unexpected message content type: {type(message_content)}")
                    return None
                    
            except Exception as e:
                print(f"    ❌ Failed to extract from MockChatCompletion: {e}")
                return None
                
        elif isinstance(result, dict):
            # Check if it's an error response FIRST
            if result.get('action') == 'error' or result.get('status') == 418:
                print(f"    ❌ AI service error: {result.get('type', 'Unknown error')}")
                return None  # Don't process error responses as valid results!
                
            # Check if it has the expected fields
            if 'is_job_related' in result:
                parsed_result = result
            else:
                print(f"    ❌ AI returned dict but missing expected fields: {list(result.keys())}")
                return None
                
        elif isinstance(result, str):
            try:
                parsed = json.loads(result)
                if isinstance(parsed, dict):
                    # Check for error responses
                    if parsed.get('action') == 'error' or parsed.get('status') == 418:
                        print(f"    ❌ AI service error in string response")
                        return None
                    if 'is_job_related' in parsed:
                        parsed_result = parsed
                    else:
                        print("    ❌ Parsed JSON but missing expected fields")
                        return None
                else:
                    print("    ❌ Parsed JSON is not a dictionary")
                    return None
            except json.JSONDecodeError:
                print("    ❌ Failed to parse string as JSON")
                return None
        else:
            print(f"    ❌ Unexpected result type: {type(result)}")
            return None
        
        # Don't process results that indicate JSON parsing failed
        if parsed_result and parsed_result.get('reasoning') == 'JSON parsing failed':
            print("    ❌ AI indicated JSON parsing failed")
            return None
        
        # Validate and clean the parsed result
        if parsed_result:
            # Ensure all required fields exist
            required_fields = ['is_job_related', 'company_extracted', 'company_match', 
                             'status', 'confidence', 'reasoning']
            
            # Check if we have a valid response structure
            if not all(field in parsed_result for field in ['is_job_related', 'status']):
                print("    ❌ Missing critical fields in parsed result")
                return None
            
            # Don't process if status is an error code
            if isinstance(parsed_result.get('status'), int):
                print(f"    ❌ Status is error code: {parsed_result.get('status')}")
                return None
            
            # Fill in missing optional fields
            for field in required_fields:
                if field not in parsed_result:
                    if field == 'confidence':
                        parsed_result['confidence'] = 0.5
                    elif field == 'reasoning':
                        parsed_result['reasoning'] = 'No reasoning provided'
                    else:
                        parsed_result[field] = None
            
            # If company_extracted is 'None' string, convert to None
            if parsed_result.get('company_extracted') == 'None':
                parsed_result['company_extracted'] = None
            
            # Try to extract company from email if AI missed it
            if not parsed_result.get('company_extracted'):
                # Extract from subject
                if ' - ' in subject:
                    parts = subject.split(' - ')
                    if len(parts) >= 2:
                        company = parts[-1].strip()
                        parsed_result['company_extracted'] = company
                        print(f"    🔧 Extracted company from subject: '{company}'")
                # Extract from sender
                elif 'applytojob.com' in sender_name.lower():
                    # For emails like "uShip <recruiting+...@applytojob.com>"
                    if '<' in sender_name:
                        company = sender_name.split('<')[0].strip()
                        if company and company.lower() not in ['recruiting', 'noreply', 'no-reply']:
                            parsed_result['company_extracted'] = company
                            print(f"    🔧 Extracted company from sender: '{company}'")
            
            # Fix inconsistent classifications
            reasoning_lower = parsed_result.get('reasoning', '').lower()
            content_lower = content.lower()
            
            # Check for obvious rejections that AI misclassified
            rejection_phrases = [
                'unable to employ',
                'unable to sponsor',
                'cannot sponsor',
                'unable to transfer',
                'pursuing other candidates',
                'not moving forward',
                'decided to move forward with other',
                'unfortunately.*unable',
                'regret to inform',
                'not selected'
            ]
            
            is_rejection = any(
                re.search(phrase, reasoning_lower) or re.search(phrase, content_lower) 
                for phrase in rejection_phrases
            )
            
            # Fix misclassifications
            if is_rejection:
                if not parsed_result.get('is_job_related'):
                    print(f"    🔧 Fixed classification: job_related=False → True (clear rejection)")
                    parsed_result['is_job_related'] = True
                
                if parsed_result.get('status') == 'Other':
                    print(f"    🔧 Fixed status: Other → Rejected")
                    parsed_result['status'] = 'Rejected'
                
                if parsed_result.get('confidence', 0) < 0.7:
                    print(f"    🔧 Fixed confidence: {parsed_result.get('confidence')} → 0.8")
                    parsed_result['confidence'] = 0.8
            
            # Special handling for "thank you for your interest" emails
            if 'thank you for your interest' in content_lower or 'thank you for your interest' in subject.lower():
                if not parsed_result.get('is_job_related'):
                    print(f"    🔧 Fixed: 'Thank you for your interest' emails are job-related")
                    parsed_result['is_job_related'] = True
                    parsed_result['confidence'] = max(parsed_result.get('confidence', 0.6), 0.7)
            
            # Debug successful parse
            print(f"    ✅ AI parsed successfully: job_related={parsed_result.get('is_job_related')}, "
                  f"company='{parsed_result.get('company_extracted')}', status={parsed_result.get('status')}, "
                  f"confidence={parsed_result.get('confidence')}")
            
            return parsed_result
        
        print("    ❌ Failed to get valid parsed result")
        return None
            
    except Exception as e:
        logger.error(f"Error using AI for email analysis: {e}")
        print(f"    ❌ AI Error: {str(e)[:200]}")
        return None
    finally:
        if 'ai_close_openai_client' in globals() and 'client' in locals():
            try:
                ai_close_openai_client(client)
            except:
                pass
def scan_for_status_updates():
    """AI-First scan of emails for job application status updates from multiple accounts."""
    try:
        # Load email accounts from secrets
        from config.secrets import EMAIL_ACCOUNTS
        
        total_updates = 0
        accounts_scanned = 0
        results = {}
        
        # Load existing applications data once
        applications_df = pd.read_csv(APPLIED_JOBS_CSV)
        applications_df['Company'] = applications_df['Company'].fillna('').astype(str)

        # Also convert other string columns that might be used with string methods
        string_columns = ['Title', 'HR Name', 'Work Location', 'Status']
        for col in string_columns:
            if col in applications_df.columns:
                applications_df[col] = applications_df[col].fillna('').astype(str)
                
        # Add Status column if it doesn't exist
        if 'Status' not in applications_df.columns:
            applications_df['Status'] = 'Applied'
            
        # Add Interview Date column if it doesn't exist
        if 'Interview Date' not in applications_df.columns:
            applications_df['Interview Date'] = None
        
        print(f"Loaded {len(applications_df)} applications from CSV")
        print(f"🤖 AI-First Mode: {'ENABLED' if USE_AI and AI_AVAILABLE else 'DISABLED'}")
        
        # Process each email account
        for account in EMAIL_ACCOUNTS:
            username = account["username"]
            password = account["password"]
            server = account.get("server", "imap.gmail.com")
            port = account.get("port", 993)
            
            print(f"\n{'='*60}")
            print(f"📧 Scanning emails for: {username}")
            print(f"{'='*60}")
            
            account_updates = 0
            
            try:
                # Connect to the email server
                mail = imaplib.IMAP4_SSL(server, port)
                mail.login(username, password)
                mail.select("inbox")
                
                # Search for recent emails
                search_days = 3
                date = (datetime.now() - pd.Timedelta(days=search_days)).strftime("%d-%b-%Y")
                status, messages = mail.search(None, f'(SINCE {date})')
                
                if status != 'OK':
                    logger.error(f"No messages found in {username}!")
                    results[username] = {"status": "error", "message": "No messages found"}
                    continue
                
                message_ids = messages[0].split()
                total_emails = len(message_ids)
                processed = 0
                job_related_count = 0
                ai_successes = 0
                ai_failures = 0
                
                print(f"📬 Found {total_emails} messages to scan")
                print(f"🔍 Using AI to analyze ALL emails")
                
                # Process messages with AI-first approach
                for message_id in reversed(message_ids):
                    try:
                        # Fetch the message
                        status, msg_data = mail.fetch(message_id, '(RFC822)')
                        if status != 'OK':
                            processed += 1
                            continue
                            
                        raw_email = msg_data[0][1]
                        msg = email.message_from_bytes(raw_email)
                        
                        # Extract email components
                        sender_name, sender_email = get_sender_info(msg)
                        subject = get_email_subject(msg)
                        content = get_email_content(msg)
                        email_date = get_email_date(msg)
                        
                        # Increment processed counter here
                        processed += 1
                        
                        # AI-FIRST: Analyze email with AI
                        ai_result = ai_analyze_job_email(subject, content, sender_name, applications_df)
                        
                        # Check if AI actually returned a result
                        if ai_result is None:
                            ai_failures += 1
                            print(f"    ⚠️ Email #{processed}: AI returned no result")
                            if processed % 10 == 0:
                                print(f"📊 Progress: {processed}/{total_emails} emails | {job_related_count} job-related | {account_updates} updates | {ai_failures} AI failures")
                            continue
                        
                        # AI succeeded
                        ai_successes += 1
                        
                        # Check if job-related
                        if not ai_result.get('is_job_related'):
                            # Not job related - skip silently
                            if processed % 10 == 0:
                                print(f"📊 Progress: {processed}/{total_emails} emails | {job_related_count} job-related | {account_updates} updates | {ai_failures} AI failures")
                            continue
                        
                        # Check for AI consistency
                        reasoning = ai_result.get('reasoning', '')
                        if 'unrelated to any job application' in reasoning.lower() and ai_result.get('is_job_related'):
                            print(f"\n⚠️ Email #{processed}: AI marked as job-related but reasoning says otherwise. Skipping.")
                            continue
                            
                        # Now we have a job-related email
                        job_related_count += 1
                        print(f"\n📧 Job-related email #{job_related_count} (from email #{processed}):")
                        print(f"   From: {sender_name} <{sender_email}>")
                        print(f"   Subject: {subject[:80]}...")
                        print(f"   AI Analysis: {reasoning[:150]}...")
                        
                        # Extract AI results
                        company_match = ai_result.get('company_match')
                        extracted_company = ai_result.get('company_extracted')
                        new_status = ai_result.get('status')
                        status_confidence = ai_result.get('confidence', 0.8)
                        
                        print(f"   Extracted company: '{extracted_company}'")
                        print(f"   Matched company: '{company_match}'")
                        print(f"   Detected status: {new_status} (confidence: {status_confidence})")
                        
                        # If AI didn't find exact match but extracted a company, try fuzzy matching
                        if not company_match and extracted_company:
                            print(f"   🔍 No direct match, attempting fuzzy match for '{extracted_company}'...")
                            
                            # Try normalized matching first
                            extracted_normalized = re.sub(r'[\s\-\.]', '', extracted_company.lower())
                            
                            for csv_company in applications_df['Company'].unique():
                                csv_normalized = re.sub(r'[\s\-\.]', '', str(csv_company).lower())
                                
                                if extracted_normalized == csv_normalized:
                                    company_match = csv_company
                                    print(f"   ✅ Normalized match: '{extracted_company}' → '{csv_company}'")
                                    break
                            
                            # If still no match, try fuzzy matching
                            if not company_match:
                                fuzzy_match, fuzzy_score = fuzzy_company_match(
                                    extracted_company, applications_df['Company'].unique(), debug=False
                                )
                                if fuzzy_match and fuzzy_score > 0.6:
                                    company_match = fuzzy_match
                                    print(f"   ✅ Fuzzy match: '{extracted_company}' → '{fuzzy_match}' (score: {fuzzy_score:.2f})")
                        
                        # Process the match if we have company and valid status
                        if company_match and new_status and new_status != "Other" and status_confidence >= 0.6:
                            # Find ALL applications for this company (try exact match first)
                            matching_apps = applications_df[applications_df['Company'] == company_match]
                            
                            # If no exact match, try case-insensitive match
                            if matching_apps.empty:
                                print(f"   🔍 No exact match for '{company_match}', trying case-insensitive search...")
                                matching_apps = applications_df[
                                    applications_df['Company'].str.lower() == company_match.lower()
                                ]
                                if not matching_apps.empty:
                                    print(f"   ✅ Found {len(matching_apps)} application(s) with case-insensitive match")
                            
                            # If still no match, try partial/fuzzy match
                            if matching_apps.empty:
                                print(f"   🔍 No case match for '{company_match}', trying fuzzy search...")
                                # Try to find companies containing the main part of the name
                                company_words = company_match.lower().split()
                                main_word = max(company_words, key=len) if company_words else company_match.lower()
                                
                                matching_apps = applications_df[
                                    applications_df['Company'].str.contains(main_word, case=False, na=False)
                                ]
                                if not matching_apps.empty:
                                    # Show what was found
                                    found_companies = matching_apps['Company'].unique()
                                    print(f"   🔍 Found similar companies: {list(found_companies)}")
                                    
                                    # Try to find exact match among similar
                                    for found_company in found_companies:
                                        if found_company.lower().replace(' ', '') == company_match.lower().replace(' ', ''):
                                            matching_apps = applications_df[applications_df['Company'] == found_company]
                                            print(f"   ✅ Matched '{company_match}' to '{found_company}'")
                                            break
                            
                            if not matching_apps.empty:
                                print(f"   📋 Found {len(matching_apps)} application(s) for {company_match}")
                                
                                # Handle multiple applications to same company
                                if len(matching_apps) > 1:
                                    print(f"   ⚠️  Multiple applications found - determining which to update...")
                                    
                                    # Try to match specific job based on email content
                                    email_text = f"{subject} {content}".lower()
                                    specific_match_idx = None
                                    
                                    # Look for job title mentions
                                    for idx in matching_apps.index:
                                        job_title = str(applications_df.at[idx, 'Title']).lower() if 'Title' in applications_df.columns else ''
                                        job_location = str(applications_df.at[idx, 'Location']).lower() if 'Location' in applications_df.columns else ''
                                        
                                        # Check if job title is mentioned in email
                                        if job_title and len(job_title) > 3:  # Avoid false matches on short titles
                                            # Check for exact phrase or key words
                                            if job_title in email_text or all(word in email_text for word in job_title.split()[:3]):
                                                specific_match_idx = idx
                                                print(f"   ✅ Matched specific job by title: '{applications_df.at[idx, 'Title']}'")
                                                break
                                        
                                        # Check if location is specifically mentioned
                                        if job_location and len(job_location) > 3:
                                            if job_location in email_text:
                                                specific_match_idx = idx
                                                print(f"   ✅ Matched specific job by location: '{applications_df.at[idx, 'Location']}'")
                                                break
                                    
                                    # If we found a specific match, update only that one
                                    if specific_match_idx is not None:
                                        matching_apps = applications_df.loc[[specific_match_idx]]
                                        print(f"   ➡️  Updating only the matched position")
                                    else:
                                        # No specific match - use conservative approach
                                        print(f"   ⚠️  Cannot determine specific position from email")
                                        
                                        # Check if this seems like a company-wide rejection
                                        bulk_rejection_phrases = [
                                            'all positions', 'any of our openings', 'all current openings',
                                            'future opportunities', 'all applications'
                                        ]
                                        is_bulk_rejection = any(phrase in email_text for phrase in bulk_rejection_phrases)
                                        
                                        if is_bulk_rejection:
                                            print(f"   📢 Detected company-wide rejection - will update all applications")
                                        else:
                                            # Conservative: update only the most recent application
                                            print(f"   🎯 Using conservative approach - updating most recent application only")
                                            
                                            # Find most recent application
                                            dates = pd.to_datetime(matching_apps['Date Applied'], errors='coerce')
                                            if not dates.isna().all():
                                                most_recent_idx = dates.idxmax()
                                                matching_apps = applications_df.loc[[most_recent_idx]]
                                                recent_job = applications_df.at[most_recent_idx, 'Title']
                                                recent_date = applications_df.at[most_recent_idx, 'Date Applied']
                                                print(f"   📅 Selected: '{recent_job}' (applied: {recent_date})")
                                            else:
                                                # If no valid dates, just take the first one
                                                matching_apps = applications_df.loc[[matching_apps.index[0]]]
                                                print(f"   📌 Selected first application (no valid dates found)")
                                
                                # Now process the selected applications
                                updated_any = False
                                for app_idx in matching_apps.index:
                                    current_status = applications_df.at[app_idx, 'Status']
                                    job_title = applications_df.at[app_idx, 'Title'] if 'Title' in applications_df.columns else 'Unknown'
                                    job_location = applications_df.at[app_idx, 'Location'] if 'Location' in applications_df.columns else 'Unknown'
                                    job_id = applications_df.at[app_idx, 'Job ID'] if 'Job ID' in applications_df.columns else app_idx
                                    
                                    print(f"      - Job: {job_title} ({job_location}) | Current status: {current_status}")
                                    
                                    # Only update if status actually changed
                                    if new_status != current_status:
                                        # Update the status
                                        applications_df.at[app_idx, 'Status'] = new_status
                                        print(f"      🔍 Debug: DataFrame updated - new status is '{applications_df.at[app_idx, 'Status']}'")
                                        
                                        # Add notes about the update
                                        notes_col = 'Notes'
                                        if notes_col not in applications_df.columns:
                                            applications_df[notes_col] = ''
                                            
                                        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
                                        email_snippet = subject[:50] + ('...' if len(subject) > 50 else '')
                                        
                                        # Add note about multiple applications if relevant
                                        multi_app_note = ""
                                        if len(matching_apps.index) < len(applications_df[applications_df['Company'] == company_match]):
                                            multi_app_note = f" | Note: {len(applications_df[applications_df['Company'] == company_match])} total applications to this company, updated only this one"
                                        
                                        new_note = f"[{timestamp}] AI updated: '{current_status}' → '{new_status}' | Email: \"{email_snippet}\" | Confidence: {status_confidence:.2f}{multi_app_note}"
                                        
                                        current_notes = applications_df.at[app_idx, notes_col]
                                        if pd.isna(current_notes) or current_notes == '':
                                            applications_df.at[app_idx, notes_col] = new_note
                                        else:
                                            applications_df.at[app_idx, notes_col] = f"{current_notes}\n{new_note}"
                                        
                                        # Update interview date if provided
                                        if ai_result.get('interview_date') and 'Interview Date' in applications_df.columns:
                                            applications_df.at[app_idx, 'Interview Date'] = ai_result.get('interview_date')
                                        
                                        print(f"      ✅ UPDATED: '{current_status}' → '{new_status}'")
                                        account_updates += 1
                                        updated_any = True
                                    else:
                                        print(f"      ℹ️  No change needed (already '{current_status}')")
                                
                                if not updated_any:
                                    print(f"   ℹ️  All selected applications already have status '{new_status}'")
                            else:
                                print(f"   ❌ No applications found for company '{company_match}'")
                                # Show some similar companies to help debug
                                similar = applications_df[
                                    applications_df['Company'].str.contains(company_match.split()[0], case=False, na=False)
                                ]['Company'].unique()[:5]
                                if len(similar) > 0:
                                    print(f"   💡 Similar companies in your applications: {list(similar)}")
                        else:
                            # Explain why no update
                            reasons = []
                            if not company_match:
                                reasons.append(f"no company match for '{extracted_company}'")
                            if not new_status or new_status == "Other":
                                reasons.append(f"unclear status ('{new_status}')")
                            if status_confidence < 0.6:
                                reasons.append(f"low confidence ({status_confidence:.2f})")
                            print(f"   ⚠️  No update: {', '.join(reasons)}")
                        
                        # Print progress every 10 emails
                        if processed % 10 == 0:
                            print(f"\n📊 Progress: {processed}/{total_emails} emails | {job_related_count} job-related | {account_updates} updates | {ai_failures} AI failures")
                            
                    except imaplib.IMAP4.abort as e:
                        processed += 1
                        if "EOF" in str(e) or "socket" in str(e):
                            print(f"\n⚠️  Connection lost at email {processed}, attempting to reconnect...")
                            try:
                                mail = imaplib.IMAP4_SSL(server, port)
                                mail.login(username, password)
                                mail.select("inbox")
                                print("   ✅ Reconnected successfully")
                                continue
                            except Exception as reconnect_error:
                                print(f"   ❌ Reconnection failed: {reconnect_error}")
                                break
                        else:
                            print(f"   ❌ IMAP error: {e}")
                            break
                    except Exception as e:
                        processed += 1
                        print(f"   ⚠️  Error processing email {processed}: {str(e)[:100]}")
                        continue
                
                # Final progress if not already shown
                if processed % 10 != 0:
                    print(f"\n📊 Final: {processed}/{total_emails} emails | {job_related_count} job-related | {account_updates} updates | {ai_failures} AI failures")
                
                # Account summary
                print(f"\n{'='*60}")
                print(f"📊 Summary for {username}:")
                print(f"{'='*60}")
                print(f"   Total emails in inbox: {total_emails}")
                print(f"   Emails processed: {processed}")
                print(f"   Job-related emails: {job_related_count}")
                print(f"   Status updates made: {account_updates}")
                print(f"   AI analysis results: {ai_successes} successful, {ai_failures} failed")
                
                # Save the updated dataframe after each account
                if account_updates > 0:
                    print(f"   💾 Saving {account_updates} updates to: {APPLIED_JOBS_CSV}")
                    applications_df.to_csv(APPLIED_JOBS_CSV, index=False)
                    print(f"   ✅ Saved {account_updates} updates to CSV")
                    total_updates += account_updates
                    test_df = pd.read_csv(APPLIED_JOBS_CSV)
                    marcom_check = test_df[test_df['Company'].str.contains('MarCom', case=False, na=False)]
                    if not marcom_check.empty:
                        print(f"   🔍 Verified: MarCom Group status is now '{marcom_check.iloc[0]['Status']}'")
                
                results[username] = {
                    "status": "success", 
                    "updates": account_updates, 
                    "job_emails": job_related_count,
                    "total_processed": processed,
                    "ai_successes": ai_successes,
                    "ai_failures": ai_failures
                }
                    
                # Close the connection
                try:
                    mail.close()
                    mail.logout()
                except:
                    pass
                    
                accounts_scanned += 1
                
            except Exception as e:
                logger.error(f"Error scanning emails for {username}: {e}")
                print(f"\n❌ Error scanning {username}: {str(e)[:200]}")
                results[username] = {"status": "error", "message": str(e)[:200]}
        
        # Print final summary
        print("\n" + "="*60)
        print(f"📊 AI-FIRST EMAIL SCAN COMPLETE")
        print("="*60)
        print(f"📬 Accounts scanned: {accounts_scanned}")
        print(f"🔄 Total status updates: {total_updates}")
        print(f"🤖 AI Mode: {'Enabled' if USE_AI and AI_AVAILABLE else 'Disabled'}")
        
        # Detailed results per account
        print("\n📈 Per-account results:")
        for username, result in results.items():
            if result['status'] == 'success':
                print(f"  ✅ {username}:")
                print(f"     - Processed: {result.get('total_processed', 0)} emails")
                print(f"     - Job-related: {result.get('job_emails', 0)} emails") 
                print(f"     - Updates: {result['updates']} status changes")
                print(f"     - AI results: {result.get('ai_successes', 0)} successful, {result.get('ai_failures', 0)} failed")
            else:
                print(f"  ❌ {username}: {result['message']}")
        
        print("="*60)
        
        return total_updates
                
    except Exception as e:
        logger.error(f"Error in email scanning process: {e}")
        print(f"\n❌ Critical error in email scanning process: {e}")
        import traceback
        traceback.print_exc()
        raise
if __name__ == "__main__":
    logger.info("Starting AI-first email scan for application status updates")
    print(f"🤖 AI-First email scanning: {'Enabled' if USE_AI and AI_AVAILABLE else 'Disabled'}")
    scan_for_status_updates()
    logger.info("Email scan complete")