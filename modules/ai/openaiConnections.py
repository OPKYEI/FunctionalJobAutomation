'''
Author:     Sai Vignesh Golla
LinkedIn:   https://www.linkedin.com/in/saivigneshgolla/

Copyright (C) 2024 Sai Vignesh Golla

License:    GNU Affero General Public License
            https://www.gnu.org/licenses/agpl-3.0.en.html
            
GitHub:     https://github.com/GodsScion/Auto_job_applier_linkedIn

version:    24.12.29.12.30
'''


from config.secrets import *
from config.settings import showAiErrorAlerts
from config.personals import ethnicity, gender, disability_status, veteran_status
from config.questions import *
from config.search import security_clearance, did_masters

from modules.helpers import print_lg, critical_error_log, convert_to_json
from modules.ai.prompts import *

from pyautogui import confirm
from openai import OpenAI
from openai.types.model import Model
from openai.types.chat import ChatCompletion, ChatCompletionChunk
from typing import Iterator, Literal
import json
import random
import signal
import threading
import time
from contextlib import contextmanager

# Free AI imports - will install if not present
try:
    from g4f.client import Client
    from bs4 import BeautifulSoup
    import requests
    from concurrent.futures import ThreadPoolExecutor, as_completed
except ImportError:
    import subprocess
    import sys
    print_lg("Installing required packages for free AI access...")
    for package in ["g4f", "bs4", "requests", "curl_cffi"]:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
    
    # Now import after installation
    from g4f.client import Client
    from bs4 import BeautifulSoup
    import requests
    from concurrent.futures import ThreadPoolExecutor, as_completed

# Free mode setting - set to True to use free AI instead of paid API
USE_FREE_AI = True

# GPT model candidates in order of preference
GPT_MODEL_CANDIDATES = [
    "gpt-4o",           # Primary choice - most reliable
    "gpt-4",            # Secondary choice
    "claude-3-sonnet",  # Tertiary choice
    "gpt-3.5-turbo",    # Fallback option
]

# Timeout settings
AI_REQUEST_TIMEOUT = 20  # seconds
PROXY_TIMEOUT = 10       # seconds

# Simple mock response class to mimic OpenAI response structure
class MockChatCompletion:
    def __init__(self, content):
        self.choices = [MockChoice(content)]

class MockChoice:
    def __init__(self, content):
        self.message = MockMessage(content)

class MockMessage:
    def __init__(self, content):
        self.content = content

# Cross-platform timeout context manager
@contextmanager
def timeout_context(seconds):
    """Cross-platform timeout context manager using threading"""
    result = {'completed': False, 'exception': None, 'return_value': None}
    
    def target():
        try:
            result['return_value'] = yield
            result['completed'] = True
        except Exception as e:
            result['exception'] = e
    
    thread = threading.Thread(target=target)
    thread.daemon = True
    thread.start()
    thread.join(timeout=seconds)
    
    if not result['completed']:
        raise TimeoutError(f"Operation timed out after {seconds} seconds")
    
    if result['exception']:
        raise result['exception']
    
    return result['return_value']

# Timeout wrapper for AI calls
def with_timeout(func, timeout_seconds, *args, **kwargs):
    """Execute a function with a timeout"""
    result = {'value': None, 'exception': None, 'completed': False}
    
    def target():
        try:
            result['value'] = func(*args, **kwargs)
            result['completed'] = True
        except Exception as e:
            result['exception'] = e
            result['completed'] = True
    
    thread = threading.Thread(target=target)
    thread.daemon = True
    thread.start()
    thread.join(timeout=timeout_seconds)
    
    if not result['completed']:
        raise TimeoutError(f"AI request timed out after {timeout_seconds} seconds")
    
    if result['exception']:
        raise result['exception']
    
    return result['value']

# Proxy rotation class for free AI mode
class ProxyRotator:
    def __init__(self):
        self.proxies = None
        self.current_proxy = None

    def get_proxy(self):
        if self.proxies:
            self.current_proxy = random.choice(self.proxies)
            return {'all': self.current_proxy, 'https': self.current_proxy, 'http': self.current_proxy}
        else:
            self.proxies = self.get_working_proxies()
            self.current_proxy = random.choice(self.proxies) if self.proxies else None
            return {'all': self.current_proxy, 'https': self.current_proxy, 'http': self.current_proxy} if self.current_proxy else None

    def remove_current_proxy(self):
        if self.current_proxy and self.proxies and self.current_proxy in self.proxies:
            self.proxies.remove(self.current_proxy)

    @staticmethod
    def get_proxies():
        try:
            response = requests.get('https://free-proxy-list.net/', timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            proxies = []
            table = soup.find('table', class_='table table-striped table-bordered')
            if table:
                tbody = table.find('tbody')
                if tbody:
                    rows = tbody.find_all('tr')
                    for row in rows:
                        tds = row.find_all('td')
                        ip = tds[0].text.strip()
                        port = tds[1].text.strip()
                        proxies.append(f'http://{ip}:{port}')
                else:
                    print_lg("No table body found")
            else:
                print_lg("No table found")
            return proxies
        except Exception as e:
            print_lg(f"Error getting proxies: {e}")
            return []

    @staticmethod
    def check_proxy(proxy):
        try:
            response = requests.get('https://httpbin.org/ip', 
                                  proxies={'http': proxy, 'https': proxy}, 
                                  timeout=PROXY_TIMEOUT)
            if response.status_code == 200:
                return proxy
        except:
            pass
        return None

    def get_working_proxies(self):
        try:
            proxies = self.get_proxies()
            working_proxies = []
            
            with ThreadPoolExecutor(max_workers=20) as executor:
                future_to_proxy = {executor.submit(self.check_proxy, proxy): proxy for proxy in proxies}
                for future in as_completed(future_to_proxy):
                    result = future.result()
                    if result:
                        working_proxies.append(result)
                        
            print_lg(f"Found {len(working_proxies)} working proxies")
            return working_proxies
        except Exception as e:
            print_lg(f"Error finding working proxies: {e}")
            return []

    def refresh_proxies(self):
        self.proxies = self.get_working_proxies()

# Initialize proxy rotator
proxy_rotator = ProxyRotator()

# API check instructions message
apiCheckInstructions = """

1. Make sure your AI API connection details like url, key, model names, etc are correct.
2. If you're using an local LLM, please check if the server is running.
3. Check if appropriate LLM and Embedding models are loaded and running.

Open `secret.py` in `/config` folder to configure your AI API connections.

ERROR:
"""

# Function to show an AI error alert
def ai_error_alert(message: str, stackTrace: str, title: str = "AI Connection Error") -> None:
    """
    Function to show an AI error alert and log it.
    """
    global showAiErrorAlerts
    if showAiErrorAlerts:
        if "Pause AI error alerts" == confirm(f"{message}{stackTrace}\n", title, ["Pause AI error alerts", "Okay Continue"]):
            showAiErrorAlerts = False
    critical_error_log(message, stackTrace)


# Function to check if an error occurred
def ai_check_error(response: ChatCompletion | ChatCompletionChunk) -> None:
    """
    Function to check if an error occurred.
    * Takes in `response` of type `ChatCompletion` or `ChatCompletionChunk`
    * Raises a `ValueError` if an error is found
    """
    if hasattr(response, 'model_extra') and response.model_extra and response.model_extra.get("error"):
        raise ValueError(
            f'Error occurred with API: "{response.model_extra.get("error")}"'
        )


# Function to create an OpenAI client
def ai_create_openai_client() -> OpenAI | str:
    """
    Function to create an OpenAI client.
    * Takes no arguments
    * Returns an `OpenAI` object or a string indicating free mode
    """
    try:
        print_lg("Creating OpenAI client...")
        
        if not use_AI:
            raise ValueError("AI is not enabled! Please enable it by setting `use_AI = True` in `secrets.py` in `config` folder.")
        
        # If free AI mode is enabled, return a marker
        if USE_FREE_AI:
            print_lg("Free AI mode is enabled - using free AI providers")
            print_lg("Loading proxies for free AI access...")
            proxy_rotator.get_proxy()
            return "FREE_AI_MODE"
        
        # Regular OpenAI API client creation
        client = OpenAI(base_url=llm_api_url, api_key=llm_api_key)

        models = ai_get_models_list(client)
        if isinstance(models, list) and len(models) > 0 and "error" in models:
            raise ValueError(models[1])
        if len(models) == 0:
            raise ValueError("No models are available!")
        if llm_model not in [model.id for model in models if hasattr(model, 'id')]:
            raise ValueError(f"Model `{llm_model}` is not found!")
        
        print_lg("---- SUCCESSFULLY CREATED OPENAI CLIENT! ----")
        print_lg(f"Using API URL: {llm_api_url}")
        print_lg(f"Using Model: {llm_model}")
        print_lg("Check './config/secrets.py' for more details.\n")
        print_lg("---------------------------------------------")

        return client
    except Exception as e:
        if USE_FREE_AI:
            print_lg("Error with regular API, but Free AI mode is enabled - continuing with free mode")
            print_lg("Loading proxies for free AI access...")
            proxy_rotator.get_proxy()
            return "FREE_AI_MODE"
        ai_error_alert(f"Error occurred while creating OpenAI client. {apiCheckInstructions}", e)
        return None


# Function to close an OpenAI client
def ai_close_openai_client(client: OpenAI | str) -> None:
    """
    Function to close an OpenAI client.
    * Takes in `client` of type `OpenAI` or a string marker
    * Returns no value
    """
    try:
        if client and client != "FREE_AI_MODE":
            print_lg("Closing OpenAI client...")
            client.close()
        elif client == "FREE_AI_MODE":
            print_lg("Closing free AI session...")
    except Exception as e:
        ai_error_alert("Error occurred while closing OpenAI client.", e)


# Function for free AI completion with timeout and proxy rotation
def free_ai_completion(prompt: str, response_format: dict = None, stream: bool = False):
    """Get completion from free AI models with timeout, proxy rotation and fallbacks"""
    success_list = []
    
    def make_ai_request(model_name, use_proxy=True):
        """Make a single AI request with timeout"""
        try:
            proxies = proxy_rotator.get_proxy() if use_proxy else None
            client = Client(proxies=proxies)
            
            response = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                stream=stream
            )
            
            if stream:
                result = ""
                print_lg("--STREAMING STARTED")
                for chunk in response:
                    chunk_content = chunk.choices[0].delta.content
                    if chunk_content:
                        result += chunk_content
                        print_lg(chunk_content, end="", flush=True)
                print_lg("\n--STREAMING COMPLETE")
                content = result
            else:
                content = response.choices[0].message.content
                
            proxy_status = "proxy" if use_proxy else "no-proxy"
            print_lg(f"Success with {model_name} via {proxy_status}")
            success_list.append([model_name, proxy_status])
            
            if response_format and response_format.get("type") == "json_object":
                return extract_json_from_text(content)
            return content
            
        except Exception as e:
            proxy_status = "proxy" if use_proxy else "no-proxy"
            print_lg(f"Failed with {model_name} via {proxy_status}: {e}")
            if use_proxy:
                proxy_rotator.remove_current_proxy()
            raise e
    
    # Try each model with different strategies
    for model_name in GPT_MODEL_CANDIDATES:
        # Strategy 1: With proxy and timeout
        for attempt in (1, 2):
            try:
                print_lg(f"Trying {model_name} with proxy (attempt {attempt}) - timeout: {AI_REQUEST_TIMEOUT}s")
                result = with_timeout(make_ai_request, AI_REQUEST_TIMEOUT, model_name, True)
                return result
            except TimeoutError:
                print_lg(f"Timeout with {model_name} (attempt {attempt})")
                proxy_rotator.remove_current_proxy()
                continue
            except Exception as e:
                print_lg(f"Error with {model_name} (attempt {attempt}): {e}")
                proxy_rotator.remove_current_proxy()
                continue

        # Strategy 2: Without proxy but with timeout
        try:
            print_lg(f"Trying {model_name} without proxy - timeout: {AI_REQUEST_TIMEOUT}s")
            result = with_timeout(make_ai_request, AI_REQUEST_TIMEOUT, model_name, False)
            return result
        except TimeoutError:
            print_lg(f"Timeout with {model_name} (no proxy)")
            continue
        except Exception as e:
            print_lg(f"Error with {model_name} (no proxy): {e}")
            continue
    
    # If all attempts fail, return fallback
    print_lg("All AI models failed or timed out")
    if response_format and response_format.get("type") == "json_object":
        return {
            "is_job_related": False,
            "company_match": None,
            "status": "Other",
            "confidence": 0.0,
            "reasoning": "All AI services unavailable or timed out"
        }
    return "ERROR: All AI models failed or timed out. Please try again."


# Extract JSON from text that might contain other content
def extract_json_from_text(text: str):
    """Extract structured JSON from model output text with robust error handling"""
    try:
        # Handle code block format if present
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
            
        # Find JSON object within text if not properly formatted
        start_idx = text.find('{')
        end_idx = text.rfind('}') + 1
        if start_idx >= 0 and end_idx > start_idx:
            text = text[start_idx:end_idx]
        
        # First try standard parsing
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # If standard parsing fails, try to fix common JSON issues
            fixed_text = fix_json_string(text)
            return json.loads(fixed_text)
            
    except Exception as e:
        print_lg(f"Failed to parse JSON: {text}")
        print_lg(f"Error: {str(e)}")
        # Return a structured fallback for email analysis
        return {
            "is_job_related": False,
            "company_match": None,
            "status": "Other",
            "confidence": 0.0,
            "reasoning": "JSON parsing failed"
        }

def fix_json_string(json_str):
    """Fix common JSON formatting issues from AI responses"""
    import re
    
    # Convert Unicode escape sequences
    json_str = json_str.encode().decode('unicode_escape')
    
    # Fix missing quotes around property names
    json_str = re.sub(r'([{,]\s*)([a-zA-Z_]+)(\s*:)', r'\1"\2"\3', json_str)
    
    # Fix truncated property names (like data__stack should be data_tech_stack)
    json_str = json_str.replace("data__stack", "data_tech_stack")
    json_str = json_str.replace("anal_methods", "analytical_methods")
    json_str = json_str.replace("requiredqualifications", "required_qualifications")
    
    # Fix missing commas between elements
    json_str = re.sub(r'"(\s*)\n\s*"', '",\n"', json_str)
    
    # Fix missing quotes around string values
    json_str = re.sub(r':\s*([a-zA-Z0-9_]+)([,}\n])', r': "\1"\2', json_str)
    
    # Fix improper quotes in arrays
    json_str = re.sub(r'\["([^"]*)"([^"]*)"([^"]*)"\]', r'["\1", "\2", "\3"]', json_str)
    
    # Fix missing commas between array items
    json_str = re.sub(r'"\s*"', '", "', json_str)
    
    # Add missing quotes for keys with weird characters
    json_str = re.sub(r'([{,]\s*)([^\s":,}]+)(\s*:)', r'\1"\2"\3', json_str)
    
    # Fix missing quotes for values with weird characters
    json_str = re.sub(r':\s*([^",{\[\s][^",}\]\s]*)([,}\]])', r': "\1"\2', json_str)
    
    # Fix leading/trailing whitespace
    json_str = json_str.strip()
    
    return json_str


# Function to get list of models available in OpenAI API
def ai_get_models_list(client: OpenAI | str) -> list[Model | str]:
    """
    Function to get list of models available in OpenAI API.
    * Takes in `client` of type `OpenAI` or a string marker
    * Returns a `list` object
    """
    if client == "FREE_AI_MODE":
        # In free AI mode, return the candidate models list
        print_lg("Using free AI mode with these models:")
        print_lg(GPT_MODEL_CANDIDATES)
        return GPT_MODEL_CANDIDATES
    
    try:
        print_lg("Getting AI models list...")
        if not client: raise ValueError("Client is not available!")
        models = client.models.list()
        ai_check_error(models)
        print_lg("Available models:")
        print_lg(models.data, pretty=True)
        return models.data
    except Exception as e:
        critical_error_log("Error occurred while getting models list!", e)
        return ["error", str(e)]


def model_supports_temperature(model_name: str) -> bool:
    """
    Checks if the specified model supports the temperature parameter.
    
    Args:
        model_name (str): The name of the AI model.
    
    Returns:
        bool: True if the model supports temperature adjustments, otherwise False.
    """
    return model_name in ["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo", "gpt-4o", "gpt-4o-mini"]


# Function to get chat completion from OpenAI API with timeout
def ai_completion(client: OpenAI | str, messages: list[dict], response_format: dict = None, temperature: float = 0, stream: bool = stream_output) -> dict | str:
    """
    Function that completes a chat and prints and formats the results with timeout handling.
    * Takes in `client` of type `OpenAI` or a string marker
    * Takes in `messages` of type `list[dict]`. Example: `[{"role": "user", "content": "Hello"}]`
    * Takes in `response_format` of type `dict` for JSON representation, default is `None`
    * Takes in `temperature` of type `float` for temperature, default is `0`
    * Takes in `stream` of type `bool` to indicate if it's a streaming call or not
    * Returns a response that might be a dict object or string, depending on response_format
    """
    # Free AI mode handling with timeout
    if client == "FREE_AI_MODE" or (USE_FREE_AI and not client):
        prompt = messages[0]["content"] if messages and len(messages) > 0 else ""
        
        try:
            result = free_ai_completion(prompt, response_format, stream)
            print_lg("\nFree AI Answer:\n")
            print_lg(result, pretty=isinstance(result, dict))
            
            # Return a mock OpenAI response structure
            return MockChatCompletion(json.dumps(result) if isinstance(result, dict) else result)
        except TimeoutError as e:
            print_lg(f"AI request timed out: {e}")
            # Return timeout fallback
            if response_format and response_format.get("type") == "json_object":
                fallback = {
                    "is_job_related": False,
                    "company_match": None,
                    "status": "Other",
                    "confidence": 0.0,
                    "reasoning": "Request timed out"
                }
                return MockChatCompletion(json.dumps(fallback))
            return MockChatCompletion("Request timed out")
    
    # Paid API behavior with timeout
    if not client: 
        raise ValueError("Client is not available!")

    params = {"model": llm_model, "messages": messages, "stream": stream}

    if model_supports_temperature(llm_model):
        params["temperature"] = temperature
    if response_format and llm_spec in ["openai", "openai-like"]:
        params["response_format"] = response_format

    try:
        # Use timeout for paid API as well
        def make_openai_request():
            return client.chat.completions.create(**params)
        
        completion = with_timeout(make_openai_request, AI_REQUEST_TIMEOUT)
        
        result = ""
        
        # Log response
        if stream:
            print_lg("--STREAMING STARTED")
            for chunk in completion:
                ai_check_error(chunk)
                chunkMessage = chunk.choices[0].delta.content
                if chunkMessage != None:
                    result += chunkMessage
                print_lg(chunkMessage, end="", flush=True)
            print_lg("\n--STREAMING COMPLETE")
        else:
            ai_check_error(completion)
            result = completion.choices[0].message.content
        
        if response_format:
            result = convert_to_json(result)
        
        print_lg("\nAI Answer to Question:\n")
        print_lg(result, pretty=isinstance(result, dict))
        return completion
        
    except TimeoutError as e:
        print_lg(f"OpenAI API request timed out: {e}")
        raise e


def ai_extract_skills(client: OpenAI | str, job_description: str, stream: bool = stream_output) -> dict | str:
    """
    Function to extract skills from job description using AI with timeout.
    * Takes in `client` of type `OpenAI` or a string marker
    * Takes in `job_description` of type `str`
    * Takes in `stream` of type `bool` 
    * Returns extracted skills
    """
    print_lg("-- EXTRACTING SKILLS FROM JOB DESCRIPTION")
    try:
        # Use the optimized DeepSeek prompt for better JSON structure
        prompt = deepseek_extract_skills_prompt.format(job_description)
        prompt += "\nReturn your answer in a valid JSON object with these fields: data_tech_stack, analytical_methods, domain_knowledge, professional_skills, required_qualifications, preferred_qualifications"

        messages = [{"role": "user", "content": prompt}]
        
        # Handle FREE_AI_MODE directly here instead of relying on ai_completion
        if client == "FREE_AI_MODE" or (USE_FREE_AI and not isinstance(client, OpenAI)):
            result = free_ai_completion(prompt, {"type": "json_object"}, stream)
            print_lg("\nFree AI Extracted Skills:\n")
            print_lg(result, pretty=True)
            return result
        else:
            # Regular OpenAI API behavior with timeout
            return ai_completion(
                client, 
                messages, 
                response_format={"type": "json_object"},
                stream=stream
            )
    except TimeoutError as e:
        print_lg(f"Skills extraction timed out: {e}")
        return {
            "data_tech_stack": [],
            "analytical_methods": [],
            "domain_knowledge": [],
            "professional_skills": [],
            "required_qualifications": [],
            "preferred_qualifications": []
        }
    except Exception as e:
        error_msg = f"Error occurred while extracting skills. {apiCheckInstructions}"
        ai_error_alert(error_msg, e)
        print_lg(error_msg)
        print_lg(str(e))
        # Return a default empty skills structure
        return {
            "data_tech_stack": [],
            "analytical_methods": [],
            "domain_knowledge": [],
            "professional_skills": [],
            "required_qualifications": [],
            "preferred_qualifications": []
        }


def ai_answer_question(
    client: OpenAI | str, 
    question: str, options: list[str] | None = None, question_type: Literal['text', 'textarea', 'single_select', 'multiple_select'] = 'text', 
    job_description: str = None, about_company: str = None, user_information_all: str = None,
    stream: bool = stream_output
) -> str:
    """
    Function to generate AI-based answers for questions in a form with timeout.
    
    Parameters:
    - `client`: OpenAI client instance or free mode marker
    - `question`: The question being answered.
    - `options`: List of options (for `single_select` or `multiple_select` questions).
    - `question_type`: Type of question (text, textarea, single_select, multiple_select)
    - `job_description`: Optional job description for context.
    - `about_company`: Optional company details for context.
    - `user_information_all`: information about you, AI can use to answer question.
    - `stream`: Whether to use streaming AI completion.
    
    Returns:
    - `str`: The AI-generated answer.
    """

    print_lg("-- ANSWERING QUESTION using AI")
    try:
        prompt = ai_answer_prompt.format(user_information_all or "N/A", question)
         # Append optional details if provided
        if job_description and job_description != "Unknown":
            prompt += f"\nJob Description:\n{job_description}"
        if about_company and about_company != "Unknown":
            prompt += f"\nAbout the Company:\n{about_company}"

        # Add options to the prompt if available
        if options and (question_type in ['single_select', 'multiple_select']):
            options_str = "OPTIONS:\n" + "\n".join([f"- {option}" for option in options])
            prompt += f"\n\n{options_str}"
            
            if question_type == 'single_select':
                prompt += "\n\nPlease select exactly ONE option from the list above."
            else:
                prompt += "\n\nYou may select MULTIPLE options from the list above if appropriate."

        messages = [{"role": "user", "content": prompt}]
        print_lg("Prompt we are passing to AI: ", prompt)
        response = ai_completion(client, messages, stream=stream)
        
        # Handle mock response structure
        if hasattr(response, 'choices'):
            return response.choices[0].message.content
        return str(response)
        
    except TimeoutError as e:
        print_lg(f"Question answering timed out: {e}")
        if question_type == 'text':
            return "5" if "years" in question.lower() else "Yes"
        else:
            return "I have extensive experience in this area."
    except Exception as e:
        ai_error_alert(f"Error occurred while answering question. {apiCheckInstructions}", e)
        # Provide a fallback answer if error occurs
        if question_type == 'text':
            return "5" if "years" in question.lower() else "Yes"
        else:
            return "I have extensive experience in this area with proven results."


def ai_gen_experience(
    client: OpenAI, 
    job_description: str, about_company: str, 
    required_skills: dict, user_experience: dict,
    stream: bool = stream_output
) -> dict | ValueError:
    pass



def ai_generate_resume(
    client: OpenAI, 
    job_description: str, about_company: str, required_skills: dict,
    stream: bool = stream_output
) -> dict | ValueError:
    '''
    Function to generate resume. Takes in user experience and template info from config.
    '''
    pass



def ai_generate_coverletter(
    client: OpenAI, 
    job_description: str, about_company: str, required_skills: dict,
    stream: bool = stream_output
) -> dict | ValueError:
    '''
    Function to generate resume. Takes in user experience and template info from config.
    '''
    pass



##< Evaluation Agents
def ai_evaluate_resume(
    client: OpenAI, 
    job_description: str, about_company: str, required_skills: dict,
    resume: str,
    stream: bool = stream_output
) -> dict | ValueError:
    pass



def ai_check_job_relevance(
    client: OpenAI, 
    job_description: str, about_company: str,
    stream: bool = stream_output
) -> dict:
    pass