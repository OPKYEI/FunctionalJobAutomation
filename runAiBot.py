'''
Author:     Sai Vignesh Golla
LinkedIn:   https://www.linkedin.com/in/saivigneshgolla/

Copyright (C) 2024 Sai Vignesh Golla

License:    GNU Affero General Public License
            https://www.gnu.org/licenses/agpl-3.0.en.html
            
GitHub:     https://github.com/GodsScion/Auto_job_applier_linkedIn

version:    24.12.29.12.30
'''


# Imports
import os
import csv
import re
import pyautogui
#from notion_sync.sync_csv_to_notion import sync as notion_sync
#notion_sync()
# Add these imports at the top of runAiBot.py
from src.utilities.proxies import ProxyRotator
from src.processor.gpt_processor import EducationalLLM, JobAnalyzer
from random import choice, shuffle, randint
from datetime import datetime

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.select import Select
from selenium.webdriver.remote.webelement import WebElement
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException, NoSuchWindowException, ElementNotInteractableException
from modules.resume.resume_integration import create_custom_resume, get_resume_path_for_job
from config.personals import *
from config.questions import *
from config.search import *
from config.secrets import use_AI, username, password, ai_provider
from config.settings import *

from modules.open_chrome import *
from modules.helpers import *
from modules.clickers_and_finders import *
from modules.validator import validate_config
from modules.ai.openaiConnections import ai_create_openai_client, ai_extract_skills, ai_answer_question, ai_close_openai_client
from modules.ai.deepseekConnections import deepseek_create_client, deepseek_extract_skills, deepseek_answer_question

from typing import Literal


pyautogui.FAILSAFE = False
# if use_resume_generator:    from resume_generator import is_logged_in_GPT, login_GPT, open_resume_chat, create_custom_resume


#< Global Variables and logics

if run_in_background == True:
    pause_at_failed_question = False
    pause_before_submit = False
    run_non_stop = False

first_name = first_name.strip()
middle_name = middle_name.strip()
last_name = last_name.strip()
full_name = first_name + " " + middle_name + " " + last_name if middle_name else first_name + " " + last_name

useNewResume = True
use_resume_customizer = True  # Set to False if you want to use default resume
randomly_answered_questions = set()

tabs_count = 1
easy_applied_count = 0
external_jobs_count = 0
failed_count = 0
skip_count = 0
dailyEasyApplyLimitReached = False

re_experience = re.compile(r'[(]?\s*(\d+)\s*[)]?\s*[-to]*\s*\d*[+]*\s*year[s]?', re.IGNORECASE)

desired_salary_lakhs = str(round(desired_salary / 100000, 2))
desired_salary_monthly = str(round(desired_salary/12, 2))
desired_salary = str(desired_salary)

current_ctc_lakhs = str(round(current_ctc / 100000, 2))
current_ctc_monthly = str(round(current_ctc/12, 2))
current_ctc = str(current_ctc)

notice_period_months = str(notice_period//30)
notice_period_weeks = str(notice_period//7)
notice_period = str(notice_period)

aiClient = None
##> ------ Dheeraj Deshwal : dheeraj9811 Email:dheeraj20194@iiitd.ac.in/dheerajdeshwal9811@gmail.com - Feature ------
about_company_for_ai = None # TODO extract about company for AI
##<

#>


#< Login Functions
def is_logged_in_LN() -> bool:
    '''
    Function to check if user is logged-in in LinkedIn
    * Returns: `True` if user is logged-in or `False` if not
    '''
    if driver.current_url == "https://www.linkedin.com/feed/": return True
    if try_linkText(driver, "Sign in"): return False
    if try_xp(driver, '//button[@type="submit" and contains(text(), "Sign in")]'):  return False
    if try_linkText(driver, "Join now"): return False
    print_lg("Didn't find Sign in link, so assuming user is logged in!")
    return True


def login_LN() -> None:
    '''
    Function to login for LinkedIn
    * Tries to login using given `username` and `password` from `secrets.py`
    * If failed, tries to login using saved LinkedIn profile button if available
    * If both failed, asks user to login manually
    '''
    # Find the username and password fields and fill them with user credentials
    driver.get("https://www.linkedin.com/login")
    try:
        wait.until(EC.presence_of_element_located((By.LINK_TEXT, "Forgot password?")))
        try:
            text_input_by_ID(driver, "username", username, 1)
        except Exception as e:
            print_lg("Couldn't find username field.")
            # print_lg(e)
        try:
            text_input_by_ID(driver, "password", password, 1)
        except Exception as e:
            print_lg("Couldn't find password field.")
            # print_lg(e)
        # Find the login submit button and click it
        driver.find_element(By.XPATH, '//button[@type="submit" and contains(text(), "Sign in")]').click()
    except Exception as e1:
        try:
            profile_button = find_by_class(driver, "profile__details")
            profile_button.click()
        except Exception as e2:
            # print_lg(e1, e2)
            print_lg("Couldn't Login!")

    try:
        # Wait until successful redirect, indicating successful login
        wait.until(EC.url_to_be("https://www.linkedin.com/feed/")) # wait.until(EC.presence_of_element_located((By.XPATH, '//button[normalize-space(.)="Start a post"]')))
        return print_lg("Login successful!")
    except Exception as e:
        print_lg("Seems like login attempt failed! Possibly due to wrong credentials or already logged in! Try logging in manually!")
        # print_lg(e)
        manual_login_retry(is_logged_in_LN, 2)
#>



def get_applied_job_ids() -> set:
    '''
    Function to get a `set` of applied job's Job IDs
    * Returns a set of Job IDs from existing applied jobs history csv file
    '''
    job_ids = set()
    try:
        with open(file_name, 'r', encoding='utf-8') as file:
            reader = csv.reader(file)
            for row in reader:
                job_ids.add(row[0])
    except FileNotFoundError:
        print_lg(f"The CSV file '{file_name}' does not exist.")
    return job_ids



def set_search_location() -> None:
    '''
    Function to set search location
    '''
    if search_location.strip():
        try:
            print_lg(f'Setting search location as: "{search_location.strip()}"')
            search_location_ele = try_xp(driver, ".//input[@aria-label='City, state, or zip code'and not(@disabled)]", False) #  and not(@aria-hidden='true')]")
            text_input(actions, search_location_ele, search_location, "Search Location")
        except ElementNotInteractableException:
            try_xp(driver, ".//label[@class='jobs-search-box__input-icon jobs-search-box__keywords-label']")
            actions.send_keys(Keys.TAB, Keys.TAB).perform()
            actions.key_down(Keys.CONTROL).send_keys("a").key_up(Keys.CONTROL).perform()
            actions.send_keys(search_location.strip()).perform()
            sleep(2)
            actions.send_keys(Keys.ENTER).perform()
            try_xp(driver, ".//button[@aria-label='Cancel']")
        except Exception as e:
            try_xp(driver, ".//button[@aria-label='Cancel']")
            print_lg("Failed to update search location, continuing with default location!", e)


def apply_filters() -> None:
    '''
    Function to apply job search filters
    '''
    set_search_location()

    try:
        recommended_wait = 1 if click_gap < 1 else 0

        wait.until(EC.presence_of_element_located((By.XPATH, '//button[normalize-space()="All filters"]'))).click()
        buffer(recommended_wait)

        wait_span_click(driver, sort_by)
        wait_span_click(driver, date_posted)
        buffer(recommended_wait)

        multi_sel_noWait(driver, experience_level) 
        multi_sel_noWait(driver, companies, actions)
        if experience_level or companies: buffer(recommended_wait)

        multi_sel_noWait(driver, job_type)
        multi_sel_noWait(driver, on_site)
        if job_type or on_site: buffer(recommended_wait)

        if easy_apply_only: boolean_button_click(driver, actions, "Easy Apply")
        
        multi_sel_noWait(driver, location)
        multi_sel_noWait(driver, industry)
        if location or industry: buffer(recommended_wait)

        multi_sel_noWait(driver, job_function)
        multi_sel_noWait(driver, job_titles)
        if job_function or job_titles: buffer(recommended_wait)

        if under_10_applicants: boolean_button_click(driver, actions, "Under 10 applicants")
        if in_your_network: boolean_button_click(driver, actions, "In your network")
        if fair_chance_employer: boolean_button_click(driver, actions, "Fair Chance Employer")

        wait_span_click(driver, salary)
        buffer(recommended_wait)
        
        multi_sel_noWait(driver, benefits)
        multi_sel_noWait(driver, commitments)
        if benefits or commitments: buffer(recommended_wait)

        show_results_button: WebElement = driver.find_element(By.XPATH, '//button[contains(@aria-label, "Apply current filters to show")]')
        show_results_button.click()

        global pause_after_filters
        if pause_after_filters and "Turn off Pause after search" == pyautogui.confirm("These are your configured search results and filter. It is safe to change them while this dialog is open, any changes later could result in errors and skipping this search run.", "Please check your results", ["Turn off Pause after search", "Look's good, Continue"]):
            pause_after_filters = False

    except Exception as e:
        print_lg("Setting the preferences failed!")
        # print_lg(e)



def get_page_info() -> tuple[WebElement | None, int | None]:
    '''
    Function to get pagination element and current page number
    '''
    try:
        pagination_element = try_find_by_classes(driver, ["jobs-search-pagination__pages", "artdeco-pagination", "artdeco-pagination__pages"])
        scroll_to_view(driver, pagination_element)
        current_page = int(pagination_element.find_element(By.XPATH, "//button[contains(@class, 'active')]").text)
    except Exception as e:
        print_lg("Failed to find Pagination element, hence couldn't scroll till end!")
        pagination_element = None
        current_page = None
        print_lg(e)
    return pagination_element, current_page


def get_job_main_details(
    job: WebElement,
    blacklisted_companies: set,
    rejected_jobs: set
) -> tuple[str, str, str, str, str, bool]:
    """
    Scrape a LinkedIn job card.

    Returns
    -------
    (job_id, title, company, work_location, work_style, skip_flag)
    """

    # ---------- helpers ----------------------------------------------------
    STYLE_RX = re.compile(r"\b(remote|hybrid|on[-\s]?site|onsite|in[-\s]?office)\b", re.I)

    def looks_like_style(txt: str) -> bool:
        return bool(STYLE_RX.search(txt))

    def canonical_style(txt: str) -> str:
        txt = txt.lower()
        if "remote" in txt:
            return "Remote"
        if "hybrid" in txt:
            return "Hybrid"
        return "On-site"  # covers on-site, onsite, in-office

    # ---------- main routine ----------------------------------------------
    try:
        # 1️⃣  title & anchor
        anchor  = job.find_element(By.TAG_NAME, "a")
        scroll_to_view(driver, anchor, True)

        job_id  = job.get_dom_attribute("data-occludable-job-id") or "unknown"
        title   = anchor.text.splitlines()[0].strip()

        # 2️⃣  company
        company = "Unknown"
        try:
            subtitle_el = job.find_element(
                By.CSS_SELECTOR,
                ".artdeco-entity-lockup__subtitle, h4.base-search-card__subtitle"
            )
            company = subtitle_el.text.split("·")[0].strip()
        except Exception:
            pass

        work_location = "Not specified"
        work_style    = None                

        # 3️⃣  metadata bullets under the card
        tokens = []
        try:
            ul = job.find_element(By.CSS_SELECTOR,
                                  "ul.job-card-container__metadata-wrapper")
            for li in ul.find_elements(By.CSS_SELECTOR, "li"):
                raw = li.text.replace("\n", " ").strip()
                if not raw:
                    continue
                for part in re.split(r"[·•|–\-]", raw):
                    part = part.strip()
                    if not part:
                        continue
                    if "(" in part and ")" in part:
                        before, inside = part.split("(", 1)
                        tokens += [before.strip(), inside.rstrip(")").strip()]
                    else:
                        tokens.append(part)
        except Exception:
            pass

        #   ▸ classify the tokens
        for tok in tokens:
            if work_style is None and looks_like_style(tok):
                work_style = canonical_style(tok)
                continue
            if work_location == "Not specified" and validate_location(tok):
                work_location = tok

        # 4️⃣  skip filters (unchanged)
        skip = False
        if company in blacklisted_companies:
            print_lg(f'Skipping "{title} | {company}" – black-listed.')
            skip = True
        elif job_id in rejected_jobs:
            print_lg(f'Skipping previously rejected "{title}" ({job_id}).')
            skip = True
        try:
            if job.find_element(By.CLASS_NAME,
                                "job-card-container__footer-job-state").text == "Applied":
                skip = True
        except Exception:
            pass

        # 5️⃣  click card for right-pane details
        if not skip:
            anchor.click()
            buffer(click_gap)

            # 5-a  old badge (works for many users)
            if work_style is None:
                try:
                    wp = driver.find_element(
                        By.CSS_SELECTOR,
                        ".jobs-unified-top-card__workplace-type"
                    ).text.strip()
                    if wp:
                        work_style = canonical_style(wp)
                except Exception:
                    pass

            # 5-b  NEW: preference buttons for work style
            if work_style is None:
                try:
                    prefs = driver.find_elements(
                        By.CSS_SELECTOR,
                        "div.job-details-fit-level-preferences button span"
                    )
                    for span in prefs:
                        txt = span.get_attribute("textContent").strip()
                        if looks_like_style(txt):
                            work_style = canonical_style(txt)
                            break
                except Exception:
                    pass

            # 5-c  fallback bullets in the top card
            try:
                for b in driver.find_elements(By.CLASS_NAME,
                                              "jobs-unified-top-card__bullet"):
                    txt = b.text.strip()
                    if not txt:
                        continue
                    if work_location == "Not specified" and validate_location(txt):
                        work_location = txt
                    if work_style is None and looks_like_style(txt):
                        work_style = canonical_style(txt)
            except Exception:
                pass

        # 6️⃣  finish up
        if work_style is None:           
            work_style = "On-site"
        work_location = clean_location(work_location)

        print_lg(f"DEBUG → Company='{company}', Location='{work_location}', "
                 f"Style='{work_style}'")
        buffer(click_gap)
        return (job_id, title, company, work_location, work_style, skip)

    except Exception as e:
        print_lg(f"Error in get_job_main_details: {e}")
        return ("unknown", "Unknown", "Unknown",
                "Unknown", "On-site", True)
# Replace the existing convert_salary_to_yearly function with this enhanced version
def convert_salary_to_yearly(salary_text):
    """Convert hourly salary to yearly equivalent and standardize format"""
    if not salary_text:
        return "Not specified"
    
    # Clean the input - remove trailing commas and extra spaces
    salary_text = salary_text.strip().rstrip(',')
    
    print_lg(f"Converting salary: '{salary_text}'")
    
    # Handle hourly ranges first (e.g., "$45/hr - $52/hr" or "$45 - $52/hr")
    hourly_range_patterns = [
        r'\$?([\d,]+(?:\.\d{2})?)\s*/\s*hr\s*-\s*\$?([\d,]+(?:\.\d{2})?)\s*/\s*hr',  # $45/hr - $52/hr
        r'\$?([\d,]+(?:\.\d{2})?)\s*-\s*\$?([\d,]+(?:\.\d{2})?)\s*/\s*(?:hr|hour)',  # $45 - $52/hr
        r'\$?([\d,]+(?:\.\d{2})?)\s*to\s*\$?([\d,]+(?:\.\d{2})?)\s*/\s*(?:hr|hour)'  # $45 to $52/hr
    ]
    
    for pattern in hourly_range_patterns:
        match = re.search(pattern, salary_text, re.I)
        if match:
            try:
                min_hourly = float(match.group(1).replace(',', ''))
                max_hourly = float(match.group(2).replace(',', ''))
                
                min_yearly = min_hourly * 2080  # 40 hours/week * 52 weeks
                max_yearly = max_hourly * 2080
                
                # Return in standard format
                converted = f"${min_yearly:,.0f} - ${max_yearly:,.0f}"
                print_lg(f"Converted hourly range: {salary_text} → {converted}")
                return converted
                    
            except (ValueError, AttributeError) as e:
                print_lg(f"Error converting hourly range: {e}")
                continue
    
    # Handle single hourly rates
    hourly_patterns = [
        r'\$?([\d,]+(?:\.\d{2})?)\s*/\s*(?:hr|hour)',  # $45/hr
        r'\$?([\d,]+(?:\.\d{2})?)\s*(?:per\s+)?(?:hr|hour)',  # $45 per hr
        r'\$?([\d,]+(?:\.\d{2})?)\s*hourly'  # $45 hourly
    ]
    
    for pattern in hourly_patterns:
        match = re.search(pattern, salary_text, re.I)
        if match:
            try:
                hourly_rate = float(match.group(1).replace(',', ''))
                yearly_salary = hourly_rate * 2080
                
                # Return in standard format
                converted = f"${yearly_salary:,.0f}"
                print_lg(f"Converted hourly rate: {salary_text} → {converted}")
                return converted
                    
            except (ValueError, AttributeError) as e:
                print_lg(f"Error converting hourly salary: {e}")
                continue
    
    # Handle already formatted yearly salary ranges (e.g., "$120,000-$224,000")
    yearly_range_patterns = [
        r'\$?([\d,]+)\s*-\s*\$?([\d,]+)',  # $120,000 - $224,000
        r'\$?([\d,]+)\s*to\s*\$?([\d,]+)',  # $120,000 to $224,000
    ]
    
    for pattern in yearly_range_patterns:
        match = re.search(pattern, salary_text, re.I)
        if match:
            try:
                min_val = float(match.group(1).replace(',', ''))
                max_val = float(match.group(2).replace(',', ''))
                
                # Check if these are reasonable salary values (not hours)
                if min_val > 1000 and max_val > 1000:
                    # These are already full salary amounts
                    converted = f"${min_val:,.0f} - ${max_val:,.0f}"
                    print_lg(f"Formatted yearly range: {salary_text} → {converted}")
                    return converted
            except (ValueError, AttributeError) as e:
                print_lg(f"Error formatting yearly range: {e}")
                continue
    
    # Handle cases where salary is already yearly but needs standardization
    # Pattern for plain numbers that likely represent thousands (e.g., "$98" meaning $98,000)
    likely_thousands_pattern = r'^\$?(\d{2,3})$'  # $98 or 98
    match = re.search(likely_thousands_pattern, salary_text.strip())
    if match:
        value = float(match.group(1))
        # If it's a 2-3 digit number, it's likely in thousands
        if 10 <= value <= 999:
            converted = f"${value * 1000:,.0f}"
            print_lg(f"Converted abbreviated salary: {salary_text} → {converted}")
            return converted
    
    # Handle "K" notation (e.g., "80K/yr", "$120K")
    k_patterns = [
        r'\$?([\d,]+(?:\.\d+)?)\s*K\s*-\s*\$?([\d,]+(?:\.\d+)?)\s*K(?:/yr|/year)?',  # 80K - 120K
        r'\$?([\d,]+(?:\.\d+)?)\s*K(?:/yr|/year)?',  # 80K/yr or $120K
    ]
    
    for pattern in k_patterns:
        match = re.search(pattern, salary_text, re.I)
        if match:
            try:
                if match.lastindex and match.lastindex >= 2:  # Range
                    min_val = float(match.group(1).replace(',', ''))
                    max_val = float(match.group(2).replace(',', ''))
                    converted = f"${min_val * 1000:,.0f} - ${max_val * 1000:,.0f}"
                    print_lg(f"Converted K range: {salary_text} → {converted}")
                    return converted
                else:  # Single value
                    value = float(match.group(1).replace(',', ''))
                    converted = f"${value * 1000:,.0f}"
                    print_lg(f"Converted K notation: {salary_text} → {converted}")
                    return converted
            except (ValueError, AttributeError) as e:
                print_lg(f"Error converting K notation: {e}")
                continue
    
    # Handle single yearly salaries that just need formatting
    single_salary_pattern = r'^\$?([\d,]+)$'
    match = re.search(single_salary_pattern, salary_text.strip())
    if match:
        try:
            value = float(match.group(1).replace(',', ''))
            if value > 10000:  # Likely a full salary
                converted = f"${value:,.0f}"
                print_lg(f"Formatted single salary: {salary_text} → {converted}")
                return converted
        except:
            pass
    
    # If the text contains dollar signs and numbers, return it as-is
    if '$' in salary_text and any(char.isdigit() for char in salary_text):
        print_lg(f"Returning salary as-is: {salary_text}")
        return salary_text
    
    # If we couldn't parse it but it contains salary-related keywords, return as-is
    salary_keywords = ['salary', 'compensation', 'pay', 'wage', 'rate']
    if any(keyword in salary_text.lower() for keyword in salary_keywords):
        print_lg(f"Contains salary keywords, returning as-is: {salary_text}")
        return salary_text
    
    # Last resort - if nothing matched, return "Not specified"
    print_lg(f"Could not parse salary format, returning 'Not specified' for: {salary_text}")
    return "Not specified"

# Replace the existing extract_salary_from_current_job function with this comprehensive version
def extract_salary_from_current_job():
    """Extract salary from the currently loaded job page using multiple methods."""
    try:
        print_lg("🔍 Starting comprehensive salary extraction...")
        
        # Define comprehensive salary patterns
        salary_patterns = [
            # Hourly rates (will be converted to yearly)
            r'\$?[\d,]+(?:\.\d{2})?\s*(?:-\s*\$?[\d,]+(?:\.\d{2})?)?\s*/?\s*(?:per\s+)?(?:hr|hour)',
            # Full ranges like "$92K/yr - $134K/yr" 
            r'\$[\d,]+K?(?:/yr|/year)?\s*(?:to|-)\s*\$[\d,]+K?(?:/yr|/year)?',
            # Single values with units
            r'\$[\d,]+K?(?:/yr|/year)',
            # Ranges without dollar signs
            r'[\d,]+K\s*(?:to|-)\s*[\d,]+K(?:/yr|/year)?',
            # Basic dollar amounts with commas
            r'\$[\d,]+(?:,\d{3})*(?:\s*(?:to|-)\s*\$[\d,]+(?:,\d{3})*)?',
        ]
        
        # Method 1: Check preference buttons (where salary often appears)
        try:
            print_lg("Method 1: Checking preference buttons...")
            preference_selectors = [
                "div.job-details-fit-level-preferences button",
                ".job-details-preferences-module button",
                ".job-details-preferences button",
                "[data-test-id*='salary']",
                "[data-test-id*='compensation']"
            ]
            
            for selector in preference_selectors:
                try:
                    buttons = driver.find_elements(By.CSS_SELECTOR, selector)
                    for button in buttons:
                        button_text = button.get_attribute("textContent") or ""
                        button_text = button_text.strip()
                        print_lg(f"  Checking button: '{button_text}'")
                        
                        for pattern in salary_patterns:
                            match = re.search(pattern, button_text, re.I)
                            if match:
                                raw_salary = match.group(0).strip()
                                salary_range = convert_salary_to_yearly(raw_salary)
                                print_lg(f"✅ Found salary in preferences: '{salary_range}'")
                                return salary_range
                except:
                    continue
                    
        except Exception as e:
            print_lg(f"Method 1 failed: {e}")
        
        # Method 2: Extract from primary description container
        try:
            print_lg("Method 2: Checking primary description container...")
            primary_container = driver.find_element(
                By.CSS_SELECTOR,
                ".job-details-jobs-unified-top-card__primary-description-container"
            )
            
            # Get all text spans with low emphasis
            salary_elements = primary_container.find_elements(
                By.CSS_SELECTOR, 
                "span.tvm__text.tvm__text--low-emphasis"
            )
            
            print_lg(f"Found {len(salary_elements)} description elements")
            
            for i, element in enumerate(salary_elements):
                text = element.get_attribute('textContent') or ""
                text = text.strip()
                
                # Skip time-related and other non-salary content
                skip_patterns = [
                    r'\d+\s*(hour|day|week|month|year)s?\s*ago',
                    r'^\s*[·•\-\.]\s*$',
                    r'^\s*$',
                    r'\d+\s*(applicant|application)',
                    r'over\s+\d+',
                    r'under\s+\d+'
                ]
                
                should_skip = any(re.search(pattern, text, re.I) for pattern in skip_patterns)
                if should_skip or len(text) < 3:
                    continue
                
                # Check for salary patterns
                for pattern in salary_patterns:
                    match = re.search(pattern, text, re.I)
                    if match:
                        raw_salary = match.group(0).strip()
                        salary_range = convert_salary_to_yearly(raw_salary)
                        print_lg(f"✅ Found salary in primary description: '{salary_range}'")
                        return salary_range
                        
        except Exception as e:
            print_lg(f"Method 2 failed: {e}")
        
        # Method 3: Try all text elements in the top card
        try:
            print_lg("Method 3: Checking all top card elements...")
            top_card_selectors = [
                ".jobs-unified-top-card__bullet",
                ".job-details-jobs-unified-top-card__tertiary-description-container span",
                ".jobs-unified-top-card__primary-description span",
                ".job-details-jobs-unified-top-card span"
            ]
            
            for selector in top_card_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        text = element.get_attribute('textContent') or ""
                        text = text.strip()
                        
                        if re.search(r'\$[\d,]+', text):
                            for pattern in salary_patterns:
                                match = re.search(pattern, text, re.I)
                                if match:
                                    raw_salary = match.group(0).strip()
                                    salary_range = convert_salary_to_yearly(raw_salary)
                                    print_lg(f"✅ Found salary in top card: '{salary_range}'")
                                    return salary_range
                except:
                    continue
                            
        except Exception as e:
            print_lg(f"Method 3 failed: {e}")
        
        # Method 4: Extract from job description
        try:
            print_lg("Method 4: Checking job description...")
            description_selectors = [
                ".jobs-box__html-content",
                ".jobs-description-content__text",
                ".jobs-description__content",
                "[data-test-id='job-description']"
            ]
            
            for selector in description_selectors:
                try:
                    job_description = driver.find_element(By.CSS_SELECTOR, selector)
                    desc_text = job_description.get_attribute('textContent') or ""
                    
                    # Enhanced patterns for description
                    desc_salary_patterns = [
                        # Patterns with context words
                        r'(?:salary|compensation|pay|wage|rate)[\s:]*\$?[\d,]+(?:\.\d{2})?\s*(?:-\s*\$?[\d,]+(?:\.\d{2})?)?\s*/?\s*(?:per\s+)?(?:hr|hour|yr|year)',
                        # Standalone salary patterns
                        r'\$[\d,]+K?(?:/yr|/year)?\s*(?:to|-)\s*\$[\d,]+K?(?:/yr|/year)?',
                        r'[\d,]+K\s*(?:to|-)\s*[\d,]+K(?:\s*per\s*(?:year|yr))?',
                        r'\$[\d,]+(?:,\d{3})*(?:\s*(?:to|-)\s*\$[\d,]+(?:,\d{3})*)?(?:\s*per\s*(?:year|hour))?',
                    ]
                    
                    for pattern in desc_salary_patterns:
                        matches = re.findall(pattern, desc_text, re.I)
                        if matches:
                            # Take the first reasonable match
                            for match in matches:
                                if isinstance(match, str) and any(char.isdigit() for char in match):
                                    salary_range = convert_salary_to_yearly(match.strip())
                                    print_lg(f"✅ Found salary in description: '{salary_range}'")
                                    return salary_range
                except:
                    continue
                        
        except Exception as e:
            print_lg(f"Method 4 failed: {e}")
        
        # Method 5: Try structured data
        try:
            print_lg("Method 5: Checking structured data...")
            scripts = driver.find_elements(By.CSS_SELECTOR, 'script[type="application/ld+json"]')
            for script in scripts:
                try:
                    data = json.loads(script.get_attribute('innerHTML'))
                    
                    if 'baseSalary' in data:
                        salary_data = data['baseSalary']
                        if isinstance(salary_data, dict):
                            if 'value' in salary_data:
                                value = salary_data['value']
                                currency = salary_data.get('currency', '$')
                                unit = salary_data.get('unitText', 'year')
                                raw_salary = f"{currency}{value}/{unit}"
                                salary_range = convert_salary_to_yearly(raw_salary)
                                print_lg(f"✅ Found salary in structured data: '{salary_range}'")
                                return salary_range
                            elif 'minValue' in salary_data and 'maxValue' in salary_data:
                                min_val = salary_data['minValue']
                                max_val = salary_data['maxValue']
                                currency = salary_data.get('currency', '$')
                                unit = salary_data.get('unitText', 'year')
                                raw_salary = f"{currency}{min_val} - {currency}{max_val}/{unit}"
                                salary_range = convert_salary_to_yearly(raw_salary)
                                print_lg(f"✅ Found salary range in structured data: '{salary_range}'")
                                return salary_range
                                
                except (json.JSONDecodeError, KeyError):
                    continue
                        
        except Exception as e:
            print_lg(f"Method 5 failed: {e}")
        
        print_lg("❌ No salary information found with any method")
        return "Not specified"
        
    except Exception as e:
        print_lg(f"Error in comprehensive salary extraction: {e}")
        return "Not specified"


def normalize_work_style(style_text):
    """Normalize work style to standard values: Remote, Hybrid, On-site, or Not specified"""
    if not style_text or style_text == "Not specified":
        return "Not specified"
        
    style_lower = style_text.lower()
    
    if any(term in style_lower for term in ['remote', 'work from home', 'wfh', 'virtual']):
        return "Remote"
    elif any(term in style_lower for term in ['hybrid', 'flexible', 'partially remote']):
        return "Hybrid"
    elif any(term in style_lower for term in ['on-site', 'onsite', 'in office', 'in-office', 'on site']):
        return "On-site"
    else:
        return "Not specified"

def validate_location(location):
    """Check if a string looks like a valid location"""
    # Return False for known non-location text patterns
    if not location or location == "Not specified":
        return False
        
    # These are typical patterns that appear in the location field but aren't locations
    invalid_patterns = [
        r'vary depending',
        r'may vary',
        r'to be determined',
        r'not specified',
        r'not disclosed',
        r'to be advised',
        r'requirements',
        r'qualifications',
        r'experience',
        r'applicants',
        r'see job description'
    ]
    
    for pattern in invalid_patterns:
        if re.search(pattern, location.lower()):
            return False
    
    # Location should be reasonably short (real locations aren't paragraphs)
    if len(location) > 100:
        return False
        
    # Most locations have at least one comma, space or geographical term
    location_terms = ['city', 'state', 'province', 'county', 'region', 'area']
    has_geo_term = any(term in location.lower() for term in location_terms)
    
    # Basic check - real locations are generally short
    return (len(location.split()) <= 7) or has_geo_term

def clean_location(location):
    """Clean location text from work style information and invalid patterns"""
    if not location or location == "Not specified":
        return "Not specified"
        
    # Remove work style terms
    location = re.sub(r'\b(remote|hybrid|on-site|onsite|in office|in-office)\b', '', location, flags=re.IGNORECASE)
    
    # Remove common prefixes
    location = re.sub(r'^(location[:\s]+|based in[:\s]+|located in[:\s]+)', '', location, flags=re.IGNORECASE)
    
    # Remove parentheses and their contents which often contain work style
    location = re.sub(r'\([^)]*\)', '', location)
    
    # Clean up punctuation and extra spaces
    location = re.sub(r'[,\s]+$', '', location)  # Remove trailing commas and spaces
    location = re.sub(r'\s+', ' ', location).strip()  # Normalize spaces
    
    # If location became empty or too short after cleaning, return "Not specified"
    if not location or len(location) < 2:
        return "Not specified"
        
    return location

# Function to check for Blacklisted words in About Company
def check_blacklist(rejected_jobs: set, job_id: str, company: str, blacklisted_companies: set) -> tuple[set, set, WebElement] | ValueError:
    jobs_top_card = try_find_by_classes(driver, ["job-details-jobs-unified-top-card__primary-description-container","job-details-jobs-unified-top-card__primary-description","jobs-unified-top-card__primary-description","jobs-details__main-content"])
    about_company_org = find_by_class(driver, "jobs-company__box")
    scroll_to_view(driver, about_company_org)
    about_company_org = about_company_org.text
    about_company = about_company_org.lower()
    skip_checking = False
    for word in about_company_good_words:
        if word.lower() in about_company:
            print_lg(f'Found the word "{word}". So, skipped checking for blacklist words.')
            skip_checking = True
            break
    if not skip_checking:
        for word in about_company_bad_words: 
            if word.lower() in about_company: 
                rejected_jobs.add(job_id)
                blacklisted_companies.add(company)
                raise ValueError(f'\n"{about_company_org}"\n\nContains "{word}".')
    buffer(click_gap)
    scroll_to_view(driver, jobs_top_card)
    return rejected_jobs, blacklisted_companies, jobs_top_card



# Function to extract years of experience required from About Job
def extract_years_of_experience(text: str) -> int:
    # Extract all patterns like '10+ years', '5 years', '3-5 years', etc.
    matches = re.findall(re_experience, text)
    if len(matches) == 0: 
        print_lg(f'\n{text}\n\nCouldn\'t find experience requirement in About the Job!')
        return 0
    return max([int(match) for match in matches if int(match) <= 12])



def get_job_description(
) -> tuple[
    str | Literal['Unknown'],
    int | Literal['Unknown'],
    bool,
    str | None,
    str | None
    ]:
    '''
    # Job Description
    Function to extract job description from About the Job.
    ### Returns:
    - `jobDescription: str | 'Unknown'`
    - `experience_required: int | 'Unknown'`
    - `skip: bool`
    - `skipReason: str | None`
    - `skipMessage: str | None`
    '''
    try:
        ##> ------ Dheeraj Deshwal : dheeraj9811 Email:dheeraj20194@iiitd.ac.in/dheerajdeshwal9811@gmail.com - Feature ------
        jobDescription = "Unknown"
        ##<
        experience_required = "Unknown"
        found_masters = 0
        jobDescription = find_by_class(driver, "jobs-box__html-content").text
        jobDescriptionLow = jobDescription.lower()
        skip = False
        skipReason = None
        skipMessage = None
        for word in bad_words:
            if word.lower() in jobDescriptionLow:
                skipMessage = f'\n{jobDescription}\n\nContains bad word "{word}". Skipping this job!\n'
                skipReason = "Found a Bad Word in About Job"
                skip = True
                break
        if not skip and security_clearance == False and ('polygraph' in jobDescriptionLow or 'clearance' in jobDescriptionLow or 'secret' in jobDescriptionLow):
            skipMessage = f'\n{jobDescription}\n\nFound "Clearance" or "Polygraph". Skipping this job!\n'
            skipReason = "Asking for Security clearance"
            skip = True
        if not skip:
            if did_masters and 'master' in jobDescriptionLow:
                print_lg(f'Found the word "master" in \n{jobDescription}')
                found_masters = 2
            experience_required = extract_years_of_experience(jobDescription)
            if current_experience > -1 and experience_required > current_experience + found_masters:
                skipMessage = f'\n{jobDescription}\n\nExperience required {experience_required} > Current Experience {current_experience + found_masters}. Skipping this job!\n'
                skipReason = "Required experience is high"
                skip = True
    except Exception as e:
        if jobDescription == "Unknown":    print_lg("Unable to extract job description!")
        else:
            experience_required = "Error in extraction"
            print_lg("Unable to extract years of experience required!")
            # print_lg(e)
    finally:
        return jobDescription, experience_required, skip, skipReason, skipMessage
        



"""
Fixed upload_resume function for runAiBot.py
"""

# Function to upload resume with proper path tracking
def upload_resume(modal: WebElement, resume: str) -> tuple[bool, str]:
    """Upload resume with enhanced reliability."""
    try:
        # Get the actual resume path
        global default_resume_path
        resume_path = os.path.abspath(resume if isinstance(resume, str) and os.path.exists(resume) else default_resume_path)
        
        print_lg(f"📄 Attempting to upload resume: {resume_path}")
        
        # Verify the file exists
        if not os.path.exists(resume_path):
            print_lg(f"⚠️ WARNING: Resume file does not exist: {resume_path}")
            resume_path = os.path.abspath(default_resume_path)
            
            if not os.path.exists(resume_path):
                print_lg(f"❌ ERROR: Default resume also not found: {resume_path}")
                return False, "Resume not found"
        
        # Wait strategies
        attempts = 0
        max_attempts = 3
        upload_element = None
        
        while attempts < max_attempts and not upload_element:
            attempts += 1
            try:
                # Strategy 1: Use explicit wait for file input
                upload_element = WebDriverWait(modal, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file']"))
                )
                print_lg(f"✅ Found upload input on attempt {attempts} using strategy 1")
                break
            except:
                try:
                    # Strategy 2: Look for "Upload resume" button and click it first
                    upload_button = modal.find_element(By.XPATH, 
                        ".//button[contains(.,'Upload') or contains(.,'resume') or contains(.,'file')]"
                    )
                    upload_button.click()
                    print_lg("Clicked upload button, now looking for file input")
                    
                    # Now look for the file input that should appear
                    upload_element = WebDriverWait(modal, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file']"))
                    )
                    print_lg(f"✅ Found upload input on attempt {attempts} using strategy 2")
                    break
                except:
                    try:
                        # Strategy 3: Check if we need to scroll to see the upload element
                        actions.send_keys(Keys.PAGE_DOWN).perform()
                        
                        # Try finding by name in addition to type
                        upload_element = modal.find_element(By.CSS_SELECTOR, 
                            "input[type='file'], input[name='file'], input[name='resume']"
                        )
                        print_lg(f"✅ Found upload input on attempt {attempts} using strategy 3")
                        break
                    except:
                        if attempts < max_attempts:
                            print_lg(f"Retry {attempts}/{max_attempts}: Waiting for upload element to be available...")
                            sleep(2)  # Wait before next attempt
                        else:
                            print_lg("❌ Could not find upload element after several attempts")
        
        # If we found an upload element, use it
        if upload_element:
            # Actually upload the file
            upload_element.send_keys(resume_path)
            
            # Log success
            print_lg(f"✅ Successfully uploaded resume: {os.path.basename(resume_path)}")
            return True, resume_path
        else:
            # Give detailed error for debugging
            print_lg("❌ Failed to find a valid upload element in the modal.")
            
            # Take a screenshot for debugging
            try:
                screenshot_path = f"logs/screenshots/resume_upload_fail_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
                driver.save_screenshot(screenshot_path)
                print_lg(f"Screenshot saved to {screenshot_path}")
            except:
                pass
                
            return False, "Upload element not found"
    except Exception as e:
        print_lg(f"❌ Resume upload failed for {resume}!", e)
        return False, "Resume upload failed"
        
# Function to answer common questions for Easy Apply
def answer_common_questions(label: str, answer: str) -> str:
    if 'sponsorship' in label or 'visa' in label: answer = require_visa
    return answer


# Function to answer the questions for Easy Apply
def answer_questions(modal: WebElement, questions_list: set, work_location: str, job_description: str | None = None ) -> set:
    # Get all questions from the page
     
    all_questions = modal.find_elements(By.XPATH, ".//div[@data-test-form-element]")
    # all_questions = modal.find_elements(By.CLASS_NAME, "jobs-easy-apply-form-element")
    # all_list_questions = modal.find_elements(By.XPATH, ".//div[@data-test-text-entity-list-form-component]")
    # all_single_line_questions = modal.find_elements(By.XPATH, ".//div[@data-test-single-line-text-form-component]")
    # all_questions = all_questions + all_list_questions + all_single_line_questions

    for Question in all_questions:
        # Check if it's a select Question
        select = try_xp(Question, ".//select", False)
        if select:
            label_org = "Unknown"
            try:
                label = Question.find_element(By.TAG_NAME, "label")
                label_org = label.find_element(By.TAG_NAME, "span").text
            except Exception:
                pass
            answer = 'Yes'
            label = label_org.lower()
            select = Select(select)
            selected_option = select.first_selected_option.text
            optionsText = []
            options = '"List of phone country codes"'
            if label != "phone country code":
                optionsText = [option.text for option in select.options]
                options = "".join([f' "{option}",' for option in optionsText])
            prev_answer = selected_option
            if overwrite_previous_answers or selected_option == "Select an option":
                ##> ------ WINDY_WINDWARD Email:karthik.sarode23@gmail.com - Added fuzzy logic to answer location based questions ------
                if 'email' in label or 'phone' in label: 
                    answer = prev_answer
                elif 'gender' in label or 'sex' in label: 
                    answer = gender
                elif 'disability' in label: 
                    answer = disability_status
                elif 'proficiency' in label: 
                    answer = 'Professional'
                # Add location handling
                elif any(loc_word in label for loc_word in ['location', 'city', 'state', 'country']):
                    if 'country' in label:
                        answer = country 
                    elif 'state' in label:
                        answer = state
                    elif 'city' in label:
                        answer = current_city if current_city else work_location
                    else:
                        answer = work_location
                else: 
                    answer = answer_common_questions(label,answer)
                try: 
                    select.select_by_visible_text(answer)
                except NoSuchElementException as e:
                    # Define similar phrases for common answers
                    possible_answer_phrases = []
                    if answer == 'Decline':
                        possible_answer_phrases = ["Decline", "not wish", "don't wish", "Prefer not", "not want"]
                    elif 'yes' in answer.lower():
                        possible_answer_phrases = ["Yes", "Agree", "I do", "I have"]
                    elif 'no' in answer.lower():
                        possible_answer_phrases = ["No", "Disagree", "I don't", "I do not"]
                    else:
                        # Try partial matching for any answer
                        possible_answer_phrases = [answer]
                        # Add lowercase and uppercase variants
                        possible_answer_phrases.append(answer.lower())
                        possible_answer_phrases.append(answer.upper())
                        # Try without special characters
                        possible_answer_phrases.append(''.join(c for c in answer if c.isalnum()))
                    ##<
                    foundOption = False
                    for phrase in possible_answer_phrases:
                        for option in optionsText:
                            # Check if phrase is in option or option is in phrase (bidirectional matching)
                            if phrase.lower() in option.lower() or option.lower() in phrase.lower():
                                select.select_by_visible_text(option)
                                answer = option
                                foundOption = True
                                break
                    if not foundOption:
                        #TODO: Use AI to answer the question need to be implemented logic to extract the options for the question
                        print_lg(f'Failed to find an option with text "{answer}" for question labelled "{label_org}", answering randomly!')
                        select.select_by_index(randint(1, len(select.options)-1))
                        answer = select.first_selected_option.text
                        randomly_answered_questions.add((f'{label_org} [ {options} ]',"select"))
            questions_list.add((f'{label_org} [ {options} ]', answer, "select", prev_answer))
            continue
        
        # Check if it's a radio Question
        radio = try_xp(Question, './/fieldset[@data-test-form-builder-radio-button-form-component="true"]', False)
        if radio:
            prev_answer = None
            label = try_xp(radio, './/span[@data-test-form-builder-radio-button-form-component__title]', False)
            try: label = find_by_class(label, "visually-hidden", 2.0)
            except: pass
            label_org = label.text if label else "Unknown"
            answer = 'Yes'
            label = label_org.lower()

            label_org += ' [ '
            options = radio.find_elements(By.TAG_NAME, 'input')
            options_labels = []
            
            for option in options:
                id = option.get_attribute("id")
                option_label = try_xp(radio, f'.//label[@for="{id}"]', False)
                options_labels.append( f'"{option_label.text if option_label else "Unknown"}"<{option.get_attribute("value")}>' ) # Saving option as "label <value>"
                if option.is_selected(): prev_answer = options_labels[-1]
                label_org += f' {options_labels[-1]},'

            if overwrite_previous_answers or prev_answer is None:
                if 'citizenship' in label or 'employment eligibility' in label: answer = us_citizenship
                elif 'veteran' in label or 'protected' in label: answer = veteran_status
                elif 'disability' in label or 'handicapped' in label: 
                    answer = disability_status
                else: answer = answer_common_questions(label,answer)
                foundOption = try_xp(radio, f".//label[normalize-space()='{answer}']", False)
                if foundOption: 
                    actions.move_to_element(foundOption).click().perform()
                else:    
                    possible_answer_phrases = ["Decline", "not wish", "don't wish", "Prefer not", "not want"] if answer == 'Decline' else [answer]
                    ele = options[0]
                    answer = options_labels[0]
                    for phrase in possible_answer_phrases:
                        for i, option_label in enumerate(options_labels):
                            if phrase in option_label:
                                foundOption = options[i]
                                ele = foundOption
                                answer = f'Decline ({option_label})' if len(possible_answer_phrases) > 1 else option_label
                                break
                        if foundOption: break
                    # if answer == 'Decline':
                    #     answer = options_labels[0]
                    #     for phrase in ["Prefer not", "not want", "not wish"]:
                    #         foundOption = try_xp(radio, f".//label[normalize-space()='{phrase}']", False)
                    #         if foundOption:
                    #             answer = f'Decline ({phrase})'
                    #             ele = foundOption
                    #             break
                    actions.move_to_element(ele).click().perform()
                    if not foundOption: randomly_answered_questions.add((f'{label_org} ]',"radio"))
            else: answer = prev_answer
            questions_list.add((label_org+" ]", answer, "radio", prev_answer))
            continue
        
        # Check if it's a text question
        text = try_xp(Question, ".//input[@type='text']", False)
        if text: 
            do_actions = False
            label = try_xp(Question, ".//label[@for]", False)
            try: label = label.find_element(By.CLASS_NAME,'visually-hidden')
            except: pass
            label_org = label.text if label else "Unknown"
            answer = "" # years_of_experience
            label = label_org.lower()

            prev_answer = text.get_attribute("value")
            if not prev_answer or overwrite_previous_answers:
                if 'experience' in label or 'years' in label: answer = years_of_experience
                elif 'phone' in label or 'mobile' in label: answer = phone_number
                elif 'street' in label: answer = street
                elif 'city' in label or 'location' in label or 'address' in label:
                    answer = current_city if current_city else work_location
                    do_actions = True
                elif 'signature' in label: answer = full_name # 'signature' in label or 'legal name' in label or 'your name' in label or 'full name' in label: answer = full_name     # What if question is 'name of the city or university you attend, name of referral etc?'
                elif 'name' in label:
                    if 'full' in label: answer = full_name
                    elif 'first' in label and 'last' not in label: answer = first_name
                    elif 'middle' in label and 'last' not in label: answer = middle_name
                    elif 'last' in label and 'first' not in label: answer = last_name
                    elif 'employer' in label: answer = recent_employer
                    else: answer = full_name
                elif 'notice' in label:
                    if 'month' in label:
                        answer = notice_period_months
                    elif 'week' in label:
                        answer = notice_period_weeks
                    else: answer = notice_period
                elif 'salary' in label or 'compensation' in label or 'ctc' in label or 'pay' in label: 
                    if 'current' in label or 'present' in label:
                        if 'month' in label:
                            answer = current_ctc_monthly
                        elif 'lakh' in label:
                            answer = current_ctc_lakhs
                        else:
                            answer = current_ctc
                    else:
                        if 'month' in label:
                            answer = desired_salary_monthly
                        elif 'lakh' in label:
                            answer = desired_salary_lakhs
                        else:
                            answer = desired_salary
                elif 'linkedin' in label: answer = linkedIn
                elif 'website' in label or 'blog' in label or 'portfolio' in label or 'link' in label: answer = website
                elif 'scale of 1-10' in label: answer = confidence_level
                elif 'headline' in label: answer = linkedin_headline
                elif ('hear' in label or 'come across' in label) and 'this' in label and ('job' in label or 'position' in label): answer = "https://github.com/GodsScion/Auto_job_applier_linkedIn"
                elif 'state' in label or 'province' in label: answer = state
                elif 'zip' in label or 'postal' in label or 'code' in label: answer = zipcode
                elif 'country' in label: answer = country
                else: answer = answer_common_questions(label,answer)
                ##> ------ Yang Li : MARKYangL - Feature ------
                if answer == "":
                    if use_AI and aiClient:
                        try:
                            if ai_provider.lower() == "openai":
                                answer = ai_answer_question(aiClient, label_org, question_type="text", job_description=job_description, user_information_all=user_information_all)
                            elif ai_provider.lower() == "deepseek":
                                answer = deepseek_answer_question(aiClient, label_org, options=None, question_type="text", job_description=job_description, about_company=None, user_information_all=user_information_all)
                            else:
                                randomly_answered_questions.add((label_org, "text"))
                                answer = years_of_experience
                            if answer and isinstance(answer, str) and len(answer) > 0:
                                print_lg(f'AI Answered received for question "{label_org}" \nhere is answer: "{answer}"')
                            else:
                                randomly_answered_questions.add((label_org, "text"))
                                answer = years_of_experience
                        except Exception as e:
                            print_lg("Failed to get AI answer!", e)
                            randomly_answered_questions.add((label_org, "text"))
                            answer = years_of_experience
                    else:
                        randomly_answered_questions.add((label_org, "text"))
                        answer = years_of_experience
                ##<
                text.clear()
                text.send_keys(answer)
                if do_actions:
                    sleep(2)
                    actions.send_keys(Keys.ARROW_DOWN)
                    actions.send_keys(Keys.ENTER).perform()
            questions_list.add((label, text.get_attribute("value"), "text", prev_answer))
            continue

        # Check if it's a textarea question
        text_area = try_xp(Question, ".//textarea", False)
        if text_area:
            label = try_xp(Question, ".//label[@for]", False)
            label_org = label.text if label else "Unknown"
            label = label_org.lower()
            answer = ""
            prev_answer = text_area.get_attribute("value")
            if not prev_answer or overwrite_previous_answers:
                if 'summary' in label: answer = linkedin_summary
                elif 'cover' in label: answer = cover_letter
                if answer == "":
                ##> ------ Yang Li : MARKYangL - Feature ------
                    if use_AI and aiClient:
                        try:
                            if ai_provider.lower() == "openai":
                                answer = ai_answer_question(aiClient, label_org, question_type="textarea", job_description=job_description, user_information_all=user_information_all)
                            elif ai_provider.lower() == "deepseek":
                                answer = deepseek_answer_question(aiClient, label_org, options=None, question_type="textarea", job_description=job_description, about_company=None, user_information_all=user_information_all)
                            else:
                                randomly_answered_questions.add((label_org, "textarea"))
                                answer = ""
                            if answer and isinstance(answer, str) and len(answer) > 0:
                                print_lg(f'AI Answered received for question "{label_org}" \nhere is answer: "{answer}"')
                            else:
                                randomly_answered_questions.add((label_org, "textarea"))
                                answer = ""
                        except Exception as e:
                            print_lg("Failed to get AI answer!", e)
                            randomly_answered_questions.add((label_org, "textarea"))
                            answer = ""
                    else:
                        randomly_answered_questions.add((label_org, "textarea"))
            text_area.clear()
            text_area.send_keys(answer)
            if do_actions:
                    sleep(2)
                    actions.send_keys(Keys.ARROW_DOWN)
                    actions.send_keys(Keys.ENTER).perform()
            questions_list.add((label, text_area.get_attribute("value"), "textarea", prev_answer))
            ##<
            continue

        # Check if it's a checkbox question
        checkbox = try_xp(Question, ".//input[@type='checkbox']", False)
        if checkbox:
            label = try_xp(Question, ".//span[@class='visually-hidden']", False)
            label_org = label.text if label else "Unknown"
            label = label_org.lower()
            answer = try_xp(Question, ".//label[@for]", False)  # Sometimes multiple checkboxes are given for 1 question, Not accounted for that yet
            answer = answer.text if answer else "Unknown"
            prev_answer = checkbox.is_selected()
            checked = prev_answer
            if not prev_answer:
                try:
                    actions.move_to_element(checkbox).click().perform()
                    checked = True
                except Exception as e: 
                    print_lg("Checkbox click failed!", e)
                    pass
            questions_list.add((f'{label} ([X] {answer})', checked, "checkbox", prev_answer))
            continue


    # Select todays date
    try_xp(driver, "//button[contains(@aria-label, 'This is today')]")

    # Collect important skills
    # if 'do you have' in label and 'experience' in label and ' in ' in label -> Get word (skill) after ' in ' from label
    # if 'how many years of experience do you have in ' in label -> Get word (skill) after ' in '

    return questions_list




def external_apply(pagination_element: WebElement, job_id: str, job_link: str, resume: str, date_listed, application_link: str, screenshot_name: str) -> tuple[bool, str, int]:
    '''
    Function to open new tab and save external job application links
    '''
    global tabs_count, dailyEasyApplyLimitReached
    if easy_apply_only:
        try:
            if "exceeded the daily application limit" in driver.find_element(By.CLASS_NAME, "artdeco-inline-feedback__message").text: dailyEasyApplyLimitReached = True
        except: pass
        print_lg("Easy apply failed I guess!")
        if pagination_element != None: return True, application_link, tabs_count
    try:
        wait.until(EC.element_to_be_clickable((By.XPATH, ".//button[contains(@class,'jobs-apply-button') and contains(@class, 'artdeco-button--3')]"))).click() # './/button[contains(span, "Apply") and not(span[contains(@class, "disabled")])]'
        wait_span_click(driver, "Continue", 1, True, False)
        windows = driver.window_handles
        tabs_count = len(windows)
        driver.switch_to.window(windows[-1])
        application_link = driver.current_url
        print_lg('Got the external application link "{}"'.format(application_link))
        if close_tabs and driver.current_window_handle != linkedIn_tab: driver.close()
        driver.switch_to.window(linkedIn_tab)
        return False, application_link, tabs_count
    except Exception as e:
        # print_lg(e)
        print_lg("Failed to apply!")
        failed_job(job_id, job_link, resume, date_listed, "Probably didn't find Apply button or unable to switch tabs.", e, application_link, screenshot_name)
        global failed_count
        failed_count += 1
        return True, application_link, tabs_count



def follow_company(modal: WebDriver = driver) -> None:
    '''
    Function to follow or un-follow easy applied companies based om `follow_companies`
    '''
    try:
        follow_checkbox_input = try_xp(modal, ".//input[@id='follow-company-checkbox' and @type='checkbox']", False)
        if follow_checkbox_input and follow_checkbox_input.is_selected() != follow_companies:
            try_xp(modal, ".//label[@for='follow-company-checkbox']")
    except Exception as e:
        print_lg("Failed to update follow companies checkbox!", e)
    


#< Failed attempts logging
def failed_job(job_id: str, job_link: str, resume: str, date_listed, error: str, exception: Exception, application_link: str, screenshot_name: str, salary_range: str = "Not specified") -> None:
    '''
    Function to update failed jobs list in excel
    '''
    try:
        with open(failed_file_name, 'a', newline='', encoding='utf-8') as file:
            fieldnames = ['Job ID', 'Job Link', 'Resume Tried', 'Date listed', 'Date Tried', 'Assumed Reason', 'Stack Trace', 'External Job link', 'Screenshot Name', 'Salary Range']
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            if file.tell() == 0: writer.writeheader()
            writer.writerow({'Job ID':job_id, 'Job Link':job_link, 'Resume Tried':resume, 'Date listed':date_listed, 'Date Tried':datetime.now(), 'Assumed Reason':error, 'Stack Trace':exception, 'External Job link':application_link, 'Screenshot Name':screenshot_name, 'Salary Range':salary_range})
            file.close()
    except Exception as e:
        print_lg("Failed to update failed jobs list!", e)
        pyautogui.alert("Failed to update the excel of failed jobs!\nProbably because of 1 of the following reasons:\n1. The file is currently open or in use by another program\n2. Permission denied to write to the file\n3. Failed to find the file", "Failed Logging")

def screenshot(driver: WebDriver, job_id: str, failedAt: str) -> str:
    '''
    Function to to take screenshot for debugging
    - Returns screenshot name as String
    '''
    screenshot_name = "{} - {} - {}.png".format( job_id, failedAt, str(datetime.now()) )
    path = logs_folder_path+"/screenshots/"+screenshot_name.replace(":",".")
    # special_chars = {'*', '"', '\\', '<', '>', ':', '|', '?'}
    # for char in special_chars:  path = path.replace(char, '-')
    driver.save_screenshot(path.replace("//","/"))
    return screenshot_name
#>



"""
Modify the submitted_jobs function to ensure all applications get properly marked as Applied.

Original location: runAiBot.py
"""

"""
Fixed submitted_jobs function for runAiBot.py
"""

def submitted_jobs(job_id: str, title: str, company: str, work_location: str, work_style: str, salary_range: str,
                   description: str, experience_required: int | Literal['Unknown', 'Error in extraction'], 
                   skills: list[str] | Literal['In Development'], hr_name: str | Literal['Unknown'], hr_link: str | Literal['Unknown'], resume: str, 
                   reposted: bool, date_listed: datetime | Literal['Unknown'], date_applied: datetime | Literal['Pending'], job_link: str, application_link: str, 
                   questions_list: set | None, connect_request: Literal['In Development']) -> None:
    '''
    Function to create or update the Applied jobs CSV file, once the application is submitted successfully
    '''
    try:
        # Add explicit logging for the salary
        print_lg(f"DEBUG - submitted_jobs received: Location='{work_location}', Style='{work_style}', Salary='{salary_range}'")
        
        # Process the resume information correctly for the CSV
        resume_filename = ""
        resume_path = ""
        
        # Handle the different possible resume values
        if isinstance(resume, str):
            if os.path.exists(resume):
                # This is a valid file path
                resume_filename = os.path.basename(resume)
                resume_path = resume
                resume_size = f"{os.path.getsize(resume)} bytes"
                print_lg(f"✅ CSV Entry: Resume={resume_filename} ({resume_size}) Path={resume_path}")
            elif resume == "Previous resume" or resume == "Resume not found" or resume == "Resume upload failed":
                # This is a status message
                resume_filename = resume
                resume_path = ""
                print_lg(f"ℹ️ CSV Entry: Resume={resume} Path=<empty>")
            else:
                # This might be just a filename, try to locate it
                potential_paths = [
                    os.path.join("resumes", resume),
                    os.path.join("all resumes", resume),
                    os.path.join(os.path.dirname(default_resume_path), resume)
                ]
                
                for path in potential_paths:
                    if os.path.exists(path):
                        resume_filename = resume
                        resume_path = path
                        print_lg(f"✅ Found resume file: {resume_path}")
                        break
                
                if not resume_path:
                    # Couldn't find the file, just use the filename
                    resume_filename = resume
                    resume_path = ""
                    print_lg(f"ℹ️ CSV Entry (filename only): {resume}")
        else:
            # Non-string value
            resume_filename = str(resume)
            resume_path = ""
            print_lg(f"⚠️ CSV Entry (unexpected type): {resume}")
            
        # Add debug logs
        print_lg(f"📋 Final CSV values: Salary='{salary_range}', Filename='{resume_filename}', Path='{resume_path}'")
        
        # Define required fieldnames WITH Salary Range
        required_fieldnames = [
            'Job ID', 'Title', 'Company', 'Work Location', 'Work Style', 'Salary Range',
            'About Job', 'Experience required', 'Skills required', 'HR Name', 'HR Link', 
            'Resume', 'Resume Path', 'Re-posted', 'Date Posted', 'Date Applied', 
            'Job Link', 'External Job link', 'Questions Found', 'Connect Request', 'Status', 'Applied'
        ]
        
        # Create/update the CSV with all extracted job details
        current_rows = []
        fieldnames = required_fieldnames.copy()  # Start with our required fields
                      
        # Check if file exists and read current content
        file_exists = os.path.isfile(file_name)
        if file_exists:
            try:
                with open(file_name, 'r', encoding='utf-8') as csv_file:
                    reader = csv.DictReader(csv_file)
                    current_rows = list(reader)
                    
                    # Get the fieldnames from the file if it exists
                    if current_rows and reader.fieldnames:
                        # Add any custom fields from the existing CSV
                        for field in reader.fieldnames:
                            if field not in fieldnames:
                                fieldnames.append(field)
            except Exception as e:
                print_lg(f"❌ Error reading CSV file: {str(e)}")
                # If we can't read the file, we'll create a new one with our required fields
                
        # Create the new row to append - explicitly set all required fields
        new_row = {field: '' for field in fieldnames}  # Initialize all to empty
        
        # Set values for our new row
        new_row['Job ID'] = job_id
        new_row['Title'] = title
        new_row['Company'] = company
        new_row['Work Location'] = work_location
        new_row['Work Style'] = work_style
        new_row['Salary Range'] = salary_range  # NEW: Add salary range
        new_row['About Job'] = description
        new_row['Experience required'] = experience_required
        new_row['Skills required'] = skills
        new_row['HR Name'] = hr_name
        new_row['HR Link'] = hr_link
        new_row['Resume'] = resume_filename
        new_row['Resume Path'] = resume_path
        new_row['Re-posted'] = reposted
        new_row['Date Posted'] = date_listed
        new_row['Date Applied'] = date_applied
        new_row['Job Link'] = job_link
        new_row['External Job link'] = application_link
        new_row['Questions Found'] = questions_list
        new_row['Connect Request'] = connect_request
        new_row['Status'] = 'Applied'
        new_row['Applied'] = '✓'
        
        # Log the row we're about to write
        print_lg(f"DEBUG - New row Salary Range: '{new_row['Salary Range']}'")
        
        # Write everything back to the file
        with open(file_name, mode='w', newline='', encoding='utf-8') as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            writer.writeheader()
            
            # Write existing rows
            for row in current_rows:
                # Make sure each row has all the fields
                for field in fieldnames:
                    if field not in row:
                        if field == 'Status':
                            row[field] = 'Applied'
                        elif field == 'Applied':
                            row[field] = '✓'
                        elif field == 'Resume Path':
                            row[field] = ''
                        elif field == 'Work Location':
                            row[field] = 'Not specified'
                        elif field == 'Work Style':
                            row[field] = 'Not specified'
                        elif field == 'Salary Range':  # NEW
                            row[field] = 'Not specified'
                        else:
                            row[field] = ''
                writer.writerow(row)
            
            # Write our new row
            writer.writerow(new_row)
        
        print_lg(f"✅ Successfully updated applications CSV with {title} at {company} (Salary: {salary_range})")
        
    except Exception as e:
        print_lg(f"❌ Failed to update submitted jobs list! Error: {str(e)}")
        pyautogui.alert("Failed to update the excel of applied jobs!\nProbably because of 1 of the following reasons:\n1. The file is currently open or in use by another program\n2. Permission denied to write to the file\n3. Failed to find the file", "Failed Logging")

# Function to discard the job application
def discard_job() -> None:
    actions.send_keys(Keys.ESCAPE).perform()
    wait_span_click(driver, 'Discard', 2)






# Function to apply to jobs
def apply_to_jobs(search_terms: list[str]) -> None:
    """
    Main function to apply to jobs based on search terms.
    Includes comprehensive resume tracking fixes and salary extraction.
    """
    applied_jobs = get_applied_job_ids()
    rejected_jobs = set()
    blacklisted_companies = set()
    global current_city, failed_count, skip_count, easy_applied_count, external_jobs_count, tabs_count, pause_before_submit, pause_at_failed_question, useNewResume, default_resume_path
    
    # Store the original default resume path for reference
    original_default_resume_path = default_resume_path
    print_lg(f"🔍 Original default resume path: {original_default_resume_path}")
    
    current_city = current_city.strip()

    if randomize_search_order:
        shuffle(search_terms)
        
    for searchTerm in search_terms:
        driver.get(f"https://www.linkedin.com/jobs/search/?keywords={searchTerm}")
        print_lg("\n________________________________________________________________________________________________________________________\n")
        print_lg(f'\n>>>> Now searching for "{searchTerm}" <<<<\n\n')

        apply_filters()

        current_count = 0
        try:
            while current_count < switch_number:
                # Wait until job listings are loaded
                wait.until(EC.presence_of_all_elements_located((By.XPATH, "//li[@data-occludable-job-id]")))

                pagination_element, current_page = get_page_info()

                # Find all job listings in current page
                buffer(3)
                job_listings = driver.find_elements(By.XPATH, "//li[@data-occludable-job-id]")  

                for job in job_listings:
                    if keep_screen_awake: 
                        pyautogui.press('shiftright')
                    if current_count >= switch_number: 
                        break
                        
                    print_lg("\n-@-\n")
                    
                    # Reset useNewResume for each job to ensure we consider uploading a resume
                    useNewResume = True
                    
                    # Reset to original default path at the start of each job processing
                    default_resume_path = original_default_resume_path
                    
                    # Track which resume we'll actually use for this job
                    current_resume_path = original_default_resume_path
                    
                    print_lg(f"🔍 Resume state reset: useNewResume={useNewResume}, default_path={default_resume_path}")

                    # CHANGE: Updated to get salary_range as well
                    job_id, title, company, work_location, work_style, skip = get_job_main_details(job, blacklisted_companies, rejected_jobs)

                    if not skip:
                        # The job page should already be loaded from get_job_main_details
                        # Add a small buffer to ensure all dynamic content is loaded
                        buffer(3)  # Increased buffer time
                        
                        # Extract salary from the currently loaded job page
                        salary_range = extract_salary_from_current_job()
                        print_lg(f"📄 Final salary result for Job {job_id}: '{salary_range}'")
                    else:
                        salary_range = "Not specified"
                    
                    if skip: 
                        continue
                        
                    # Redundant fail safe check for applied jobs!
                    try:
                        if job_id in applied_jobs or find_by_class(driver, "jobs-s-apply__application-link", 2):
                            print_lg(f'Already applied to "{title} | {company}" job. Job ID: {job_id}!')
                            continue
                    except Exception as e:
                        print_lg(f'Error checking if already applied: {str(e)}')
                    except Exception as e:
                        print_lg(f'Trying to Apply to "{title} | {company}" job. Job ID: {job_id}')

                    job_link = "https://www.linkedin.com/jobs/view/"+job_id
                    application_link = "Easy Applied"
                    date_applied = "Pending"
                    hr_link = "Unknown"
                    hr_name = "Unknown"
                    connect_request = "In Development" # Still in development
                    date_listed = "Unknown"
                    skills = "Needs an AI" # Still in development
                    resume_used = "Previous resume"  # Default to this if nothing else
                    reposted = False
                    questions_list = None
                    screenshot_name = "Not Available"

                    try:
                        rejected_jobs, blacklisted_companies, jobs_top_card = check_blacklist(rejected_jobs, job_id, company, blacklisted_companies)
                    except ValueError as e:
                        print_lg(e, 'Skipping this job!\n')
                        # CHANGE: Added salary_range parameter to failed_job call
                        failed_job(job_id, job_link, resume_used, date_listed, "Found Blacklisted words in About Company", e, "Skipped", screenshot_name, salary_range)
                        skip_count += 1
                        continue
                    except Exception as e:
                        print_lg("Failed to scroll to About Company!")

                    # Hiring Manager info
                    try:
                        hr_info_card = WebDriverWait(driver, 2).until(EC.presence_of_element_located((By.CLASS_NAME, "hirer-card__hirer-information")))
                        hr_link = hr_info_card.find_element(By.TAG_NAME, "a").get_attribute("href")
                        hr_name = hr_info_card.find_element(By.TAG_NAME, "span").text
                    except Exception as e:
                        print_lg(f'HR info was not given for "{title}" with Job ID: {job_id}!')

                    # Calculation of date posted
                    try:
                        time_posted_text = jobs_top_card.find_element(By.XPATH, './/span[contains(normalize-space(), " ago")]').text
                        print("Time Posted: " + time_posted_text)
                        if time_posted_text.__contains__("Reposted"):
                            reposted = True
                            time_posted_text = time_posted_text.replace("Reposted", "")
                        date_listed = calculate_date_posted(time_posted_text)
                    except Exception as e:
                        print_lg("Failed to calculate the date posted!", e)

                    # Get job description and determine if we should skip this job
                    description, experience_required, skip, reason, message = get_job_description()
                    if skip:
                        print_lg(message)
                        # CHANGE: Added salary_range parameter to failed_job call
                        failed_job(job_id, job_link, resume_used, date_listed, reason, message, "Skipped", screenshot_name, salary_range)
                        rejected_jobs.add(job_id)
                        skip_count += 1
                        continue
                    
                    # CRITICAL FIX: Custom resume handling with error safety
                    if use_resume_customizer and description != "Unknown":
                        try:
                            # Call the custom resume creator
                            custom_resume_path = create_custom_resume(
                                job_id=job_id,
                                title=title,
                                company=company,
                                work_location=work_location,
                                work_style=work_style,
                                job_description=description
                            )
                            
                            # MANUAL PATH FALLBACK: Try to find the file even if function fails
                            if not custom_resume_path or not os.path.exists(custom_resume_path):
                                # Try standard naming patterns used in your system
                                possible_paths = [
                                    os.path.abspath(f"all resumes/customized/Resume_{job_id}.docx"),
                                    os.path.abspath(f"all resumes/customized/Resume_{job_id}.pdf"),
                                    os.path.abspath(f"all resumes/customized/Resume_{title}_{company}_{job_id}.docx"),
                                    os.path.abspath(f"all resumes/customized/Resume_{title}_{company}_{job_id}.pdf"),
                                    os.path.abspath(f"all resumes/Resume_{job_id}.docx"),
                                    os.path.abspath(f"all resumes/Resume_{job_id}.pdf")
                                ]
                                
                                # Try to find any custom resume that might contain this job_id
                                custom_resume_dir = os.path.abspath("all resumes/customized")
                                if os.path.exists(custom_resume_dir):
                                    for filename in os.listdir(custom_resume_dir):
                                        if job_id in filename and os.path.isfile(os.path.join(custom_resume_dir, filename)):
                                            custom_resume_path = os.path.abspath(os.path.join(custom_resume_dir, filename))
                                            print_lg(f"✅ Found custom resume by job ID search: {custom_resume_path}")
                                            break
                                        # Also check if any file contains both title and company
                                        if title.replace(' ', '_') in filename and company.replace(' ', '_') in filename:
                                            custom_resume_path = os.path.abspath(os.path.join(custom_resume_dir, filename))
                                            print_lg(f"✅ Found custom resume by title/company match: {custom_resume_path}")
                                            break
                                
                                # Check possible paths
                                for path in possible_paths:
                                    if os.path.exists(path):
                                        custom_resume_path = path
                                        print_lg(f"✅ Found custom resume at standard path: {custom_resume_path}")
                                        break
                            
                            # Verify the custom resume was found and exists
                            if custom_resume_path and os.path.exists(custom_resume_path):
                                # Use the custom resume for this job
                                current_resume_path = custom_resume_path
                                print_lg(f"✅ Using customized resume for this job: {current_resume_path}")
                                try:
                                    file_size = os.path.getsize(current_resume_path)
                                    print_lg(f"   File size: {file_size} bytes")
                                except:
                                    print_lg("   Unable to determine file size")
                            else:
                                # If custom resume creation failed, use the original default
                                current_resume_path = original_default_resume_path
                                print_lg(f"⚠️ No valid custom resume found. Using default: {current_resume_path}")
                        except Exception as e:
                            current_resume_path = original_default_resume_path
                            print_lg(f"❌ Failed to create custom resume, using default: {current_resume_path}", e)
                    else:
                        print_lg(f"ℹ️ Not using resume customizer. Using default: {current_resume_path}")
                    
                    if use_AI and description != "Unknown":
                        try:
                            if ai_provider.lower() == "openai":
                                skills = ai_extract_skills(aiClient, description)
                            elif ai_provider.lower() == "deepseek":
                                skills = deepseek_extract_skills(aiClient, description)
                            else:
                                skills = "In Development"
                            print_lg(f"Extracted skills using {ai_provider} AI")
                        except Exception as e:
                            print_lg("Failed to extract skills:", e)
                            skills = "Error extracting skills"

                    uploaded = False
                    # Case 1: Easy Apply Button
                    if try_xp(driver, ".//button[contains(@class,'jobs-apply-button') and contains(@class, 'artdeco-button--3') and contains(@aria-label, 'Easy')]"):
                        try: 
                            try:
                                errored = ""
                                modal = find_by_class(driver, "jobs-easy-apply-modal")
                                wait_span_click(modal, "Next", 1)
                                next_button = True
                                questions_list = set()
                                next_counter = 0
                                while next_button:
                                    next_counter += 1
                                    if next_counter >= 15: 
                                        if pause_at_failed_question:
                                            screenshot(driver, job_id, "Needed manual intervention for failed question")
                                            pyautogui.alert("Couldn't answer one or more questions.\nPlease click \"Continue\" once done.\nDO NOT CLICK Back, Next or Review button in LinkedIn.\n\n\n\n\nYou can turn off \"Pause at failed question\" setting in config.py", "Help Needed", "Continue")
                                            next_counter = 1
                                            continue
                                        if questions_list: 
                                            print_lg("Stuck for one or some of the following questions...", questions_list)
                                        screenshot_name = screenshot(driver, job_id, "Failed at questions")
                                        errored = "stuck"
                                        raise Exception("Seems like stuck in a continuous loop of next, probably because of new questions.")
                                        
                                    questions_list = answer_questions(modal, questions_list, work_location, job_description=description)
                                    
                                    # CRITICAL FIX: Resume upload handling
                                                                      
                                    if useNewResume and not uploaded: 
                                        print_lg(f"🔄 Attempting to upload resume: {current_resume_path}")
                                        
                                        # First attempt - try on current page
                                        uploaded, upload_result = upload_resume(modal, current_resume_path)
                                        
                                        # If first attempt failed, try clicking Next and looking on the next page
                                        if not uploaded:
                                            print_lg("⚠️ Resume upload element not found on first page, trying next page...")
                                            try:
                                                # Try to find and click the Next button
                                                next_button = modal.find_element(By.XPATH, './/button[contains(span, "Next")]')
                                                next_button.click()
                                                buffer(click_gap)
                                                
                                                # Now try uploading on this new page
                                                uploaded, upload_result = upload_resume(modal, current_resume_path)
                                                
                                                # If we still failed, try one more page (some applications have multiple steps)
                                                if not uploaded:
                                                    print_lg("⚠️ Resume upload element not found on second page, trying one more page...")
                                                    next_button = modal.find_element(By.XPATH, './/button[contains(span, "Next")]')
                                                    next_button.click()
                                                    buffer(click_gap)
                                                    
                                                    # Final attempt
                                                    uploaded, upload_result = upload_resume(modal, current_resume_path)
                                            except Exception as e:
                                                print_lg(f"⚠️ Error while trying to navigate to next page for resume upload: {str(e)}")
                                        
                                        # Only update resume_used if upload was successful
                                        if uploaded:
                                            resume_used = upload_result
                                            print_lg(f"✅ Resume upload successful: {resume_used}")
                                        else:
                                            print_lg(f"❌ All resume upload attempts failed for {current_resume_path}")
                                            resume_used = "Previous resume"  # Mark as using previous resume
                                    
                                    try: 
                                        next_button = modal.find_element(By.XPATH, './/span[normalize-space(.)="Review"]') 
                                    except NoSuchElementException:  
                                        next_button = modal.find_element(By.XPATH, './/button[contains(span, "Next")]')
                                    try: 
                                        next_button.click()
                                    except ElementClickInterceptedException: 
                                        break    # Happens when it tries to click Next button in About Company photos section
                                    buffer(click_gap)

                            except NoSuchElementException: 
                                errored = "nose"
                            finally:
                                if questions_list and errored != "stuck": 
                                    print_lg("Answered the following questions...", questions_list)
                                    print("\n\n" + "\n".join(str(question) for question in questions_list) + "\n\n")
                                wait_span_click(driver, "Review", 1, scrollTop=True)
                                cur_pause_before_submit = pause_before_submit
                                if errored != "stuck" and cur_pause_before_submit:
                                    decision = pyautogui.confirm('1. Please verify your information.\n2. If you edited something, please return to this final screen.\n3. DO NOT CLICK "Submit Application".\n\n\n\n\nYou can turn off "Pause before submit" setting in config.py\nTo TEMPORARILY disable pausing, click "Disable Pause"', "Confirm your information",["Disable Pause", "Discard Application", "Submit Application"])
                                    if decision == "Discard Application": 
                                        raise Exception("Job application discarded by user!")
                                    pause_before_submit = False if "Disable Pause" == decision else True
                                follow_company(modal)
                                if wait_span_click(driver, "Submit application", 2, scrollTop=True): 
                                    date_applied = datetime.now()
                                    if not wait_span_click(driver, "Done", 2): 
                                        actions.send_keys(Keys.ESCAPE).perform()
                                elif errored != "stuck" and cur_pause_before_submit and "Yes" in pyautogui.confirm("You submitted the application, didn't you 😒?", "Failed to find Submit Application!", ["Yes", "No"]):
                                    date_applied = datetime.now()
                                    wait_span_click(driver, "Done", 2)
                                else:
                                    print_lg("Since, Submit Application failed, discarding the job application...")
                                    if errored == "nose": 
                                        raise Exception("Failed to click Submit application 😑")

                        except Exception as e:
                            print_lg("Failed to Easy apply!")
                            critical_error_log("Somewhere in Easy Apply process",e)
                            # CHANGE: Added salary_range parameter to failed_job call
                            failed_job(job_id, job_link, resume_used, date_listed, "Problem in Easy Applying", e, application_link, screenshot_name, salary_range)
                            failed_count += 1
                            discard_job()
                            continue
                        
                        # Add verification log after successful application
                        print_lg(f"📄 Resume verification: Final resume value sent to CSV: {resume_used}")
                    else:
                        # Case 2: Apply externally
                        skip, application_link, tabs_count = external_apply(pagination_element, job_id, job_link, resume_used, date_listed, application_link, screenshot_name)
                        if dailyEasyApplyLimitReached:
                            print_lg("\n###############  Daily application limit for Easy Apply is reached!  ###############\n")
                            return
                        if skip: 
                            continue

                    # CHANGE: Pass salary_range to submitted_jobs
                    submitted_jobs(job_id, title, company, work_location, work_style, salary_range, description, 
                                  experience_required, skills, hr_name, hr_link, resume_used, 
                                  reposted, date_listed, date_applied, job_link, application_link, 
                                  questions_list, connect_request)
                    
                    # CRITICAL FIX: Only disable resume uploads for generic resumes
                    if uploaded:
                        if current_resume_path == original_default_resume_path:
                            # Only disable future uploads if using the default generic resume
                            useNewResume = False
                            print_lg("⚠️ Generic resume used - disabling new uploads for future applications")
                        else:
                            # Keep trying to upload custom resumes for each job
                            useNewResume = True
                            print_lg("✅ Custom resume used - will continue trying to upload new resumes")

                    print_lg(f'Successfully saved "{title} | {company}" job. Job ID: {job_id} info')
                    current_count += 1
                    if application_link == "Easy Applied": 
                        easy_applied_count += 1
                    else:   
                        external_jobs_count += 1
                    applied_jobs.add(job_id)

                # Switching to next page
                if pagination_element == None:
                    print_lg("Couldn't find pagination element, probably at the end page of results!")
                    break
                try:
                    pagination_element.find_element(By.XPATH, f"//button[@aria-label='Page {current_page+1}']").click()
                    print_lg(f"\n>-> Now on Page {current_page+1} \n")
                except NoSuchElementException:
                    print_lg(f"\n>-> Didn't find Page {current_page+1}. Probably at the end page of results!\n")
                    break

        except Exception as e:
            print_lg("Failed to find Job listings!")
            critical_error_log("In Applier", e)
            print_lg(driver.page_source, pretty=True)
        
def run(total_runs: int) -> int:
    if dailyEasyApplyLimitReached:
        return total_runs
    print_lg("\n########################################################################################################################\n")
    print_lg(f"Date and Time: {datetime.now()}")
    print_lg(f"Cycle number: {total_runs}")
    print_lg(f"Currently looking for jobs posted within '{date_posted}' and sorting them by '{sort_by}'")
    apply_to_jobs(search_terms)
    print_lg("########################################################################################################################\n")
    if not dailyEasyApplyLimitReached:
        print_lg("Sleeping for 10 min...")
        sleep(300)
        print_lg("Few more min... Gonna start with in next 5 min...")
        sleep(300)
    buffer(3)
    return total_runs + 1



chatGPT_tab = False
linkedIn_tab = False

def main() -> None:
    try:
        global linkedIn_tab, tabs_count, useNewResume, aiClient
        alert_title = "Error Occurred. Closing Browser!"
        total_runs = 1        
        validate_config()
        
        if not os.path.exists(default_resume_path):
            pyautogui.alert(text='Your default resume "{}" is missing! Please update it\'s folder path "default_resume_path" in config.py\n\nOR\n\nAdd a resume with exact name and path (check for spelling mistakes including cases).\n\n\nFor now the bot will continue using your previous upload from LinkedIn!'.format(default_resume_path), title="Missing Resume", button="OK")
            useNewResume = False
        
        # Login to LinkedIn
        tabs_count = len(driver.window_handles)
        driver.get("https://www.linkedin.com/login")
        if not is_logged_in_LN(): login_LN()
        
        linkedIn_tab = driver.current_window_handle

        # # Login to ChatGPT in a new tab for resume customization
        # if use_resume_generator:
        #     try:
        #         driver.switch_to.new_window('tab')
        #         driver.get("https://chat.openai.com/")
        #         if not is_logged_in_GPT(): login_GPT()
        #         open_resume_chat()
        #         global chatGPT_tab
        #         chatGPT_tab = driver.current_window_handle
        #     except Exception as e:
        #         print_lg("Opening OpenAI chatGPT tab failed!")
        if use_AI:
            ##> ------ Yang Li : MARKYangL - Feature ------
            print_lg(f"Initializing AI client for {ai_provider}...")
            if ai_provider.lower() == "openai":
                aiClient = ai_create_openai_client()
            elif ai_provider.lower() == "deepseek":
                aiClient = deepseek_create_client()
            else:
                print_lg(f"Unknown AI provider: {ai_provider}. Supported providers are: openai, deepseek")
                aiClient = None
            ##<
        # Start applying to jobs
        driver.switch_to.window(linkedIn_tab)
        total_runs = run(total_runs)
        while(run_non_stop):
            if cycle_date_posted:
                date_options = ["Any time", "Past month", "Past week", "Past 24 hours"]
                global date_posted
                date_posted = date_options[date_options.index(date_posted)+1 if date_options.index(date_posted)+1 > len(date_options) else -1] if stop_date_cycle_at_24hr else date_options[0 if date_options.index(date_posted)+1 >= len(date_options) else date_options.index(date_posted)+1]
            if alternate_sortby:
                global sort_by
                sort_by = "Most recent" if sort_by == "Most relevant" else "Most relevant"
                total_runs = run(total_runs)
                sort_by = "Most recent" if sort_by == "Most relevant" else "Most relevant"
            total_runs = run(total_runs)
            if dailyEasyApplyLimitReached:
                break
        

    except NoSuchWindowException:   pass
    except Exception as e:
        critical_error_log("In Applier Main", e)
        pyautogui.alert(e,alert_title)
    finally:
        print_lg("\n\nTotal runs:                     {}".format(total_runs))
        print_lg("Jobs Easy Applied:              {}".format(easy_applied_count))
        print_lg("External job links collected:   {}".format(external_jobs_count))
        print_lg("                              ----------")
        print_lg("Total applied or collected:     {}".format(easy_applied_count + external_jobs_count))
        print_lg("\nFailed jobs:                    {}".format(failed_count))
        print_lg("Irrelevant jobs skipped:        {}\n".format(skip_count))
        if randomly_answered_questions: print_lg("\n\nQuestions randomly answered:\n  {}  \n\n".format(";\n".join(str(question) for question in randomly_answered_questions)))
        quote = choice([
            "You're one step closer than before.", 
            "All the best with your future interviews.", 
            "Keep up with the progress. You got this.", 
            "If you're tired, learn to take rest but never give up.",
            "Success is not final, failure is not fatal: It is the courage to continue that counts. - Winston Churchill",
            "Believe in yourself and all that you are. Know that there is something inside you that is greater than any obstacle. - Christian D. Larson",
            "Every job is a self-portrait of the person who does it. Autograph your work with excellence.",
            "The only way to do great work is to love what you do. If you haven't found it yet, keep looking. Don't settle. - Steve Jobs",
            "Opportunities don't happen, you create them. - Chris Grosser",
            "The road to success and the road to failure are almost exactly the same. The difference is perseverance.",
            "Obstacles are those frightful things you see when you take your eyes off your goal. - Henry Ford",
            "The only limit to our realization of tomorrow will be our doubts of today. - Franklin D. Roosevelt"
            ])
        msg = f"\n{quote}\n\n\nBest regards,\nSai Vignesh Golla\nhttps://www.linkedin.com/in/saivigneshgolla/\n\n"
        pyautogui.alert(msg, "Exiting..")
        print_lg(msg,"Closing the browser...")
        if tabs_count >= 10:
            msg = "NOTE: IF YOU HAVE MORE THAN 10 TABS OPENED, PLEASE CLOSE OR BOOKMARK THEM!\n\nOr it's highly likely that application will just open browser and not do anything next time!" 
            pyautogui.alert(msg,"Info")
            print_lg("\n"+msg)
        ##> ------ Yang Li : MARKYangL - Feature ------
        if use_AI and aiClient:
            try:
                if ai_provider.lower() == "openai":
                    ai_close_openai_client(aiClient)
                elif ai_provider.lower() == "deepseek":
                    ai_close_openai_client(aiClient)  
                print_lg(f"Closed {ai_provider} AI client.")
            except Exception as e:
                print_lg("Failed to close AI client:", e)
        ##<
        try: driver.quit()
        except Exception as e: critical_error_log("When quitting...", e)


if __name__ == "__main__":
    main()
