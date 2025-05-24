# src/scraper_linkedin/integrated_scraper.py

import logging
import re
from datetime import datetime
import time
from linkedin_jobs_scraper import LinkedinScraper
from linkedin_jobs_scraper.events import Events, EventData, EventMetrics
from linkedin_jobs_scraper.query import Query, QueryOptions, QueryFilters
from linkedin_jobs_scraper.filters import (
    RelevanceFilters, TimeFilters, TypeFilters, ExperienceLevelFilters,
    OnSiteOrRemoteFilters
)
from typing import List, Dict, Any

class IntegratedLinkedInScraper:
    """Drop-in replacement for JobScout's LinkedIn scraper."""
    
    def __init__(self, username: str, password: str):
        """Initialize the LinkedIn scraper with credentials."""
        self.username = username
        self.password = password
        self.logger = logging.getLogger(__name__)
        self.scraped_job_data: List[Dict[str, Any]] = []
        self._setup_scraper()
    
    def _setup_scraper(self):
        """Configure the LinkedIn scraper."""
        # Create the scraper without authentication initially
        self.scraper = LinkedinScraper(
            chrome_executable_path=None,  # For default Chrome installation
            chrome_options=None,  # Custom Chrome options
            headless=True,  # Hide browser UI
            max_workers=1,  # Number of threads for scraping (reduce for stability)
            slow_mo=1.0,  # Slow down scraping to avoid detection
            page_load_timeout=60  # Page load timeout
        )
        
        # Add event handlers
        def on_data(data: EventData):
            job_info = {
                'job_position_title': data.title,
                'job_id': data.job_id if hasattr(data, 'job_id') else '',
                'job_position_link': data.link,
                'company_logo': '',  # Not provided directly
                'company_name': data.company,
                'location': data.place,
                'days_ago': data.date,
                'no_of_applicants': 0,  # Would need parsing
                'salary': self._extract_salary(data.description),
                'workplace': self._extract_workplace(data.description),
                'job_type': '',  # Would need parsing
                'experience_level': '',  # Would need parsing
                'industry': '',  # Would need parsing
                'is_easy_apply': False,  # Would need specific detection
                'apply_link': data.apply_link if hasattr(data, 'apply_link') and data.apply_link else "",
                'job_description': data.description
            }
            self.scraped_job_data.append(job_info)
            self.logger.info(f"Scraped job: {job_info['job_position_title']} at {job_info['company_name']}")
        
        def on_error(error):
            self.logger.error(f"Scraping error: {error}")
        
        def on_end():
            self.logger.info(f"Scraping completed. Found {len(self.scraped_job_data)} jobs.")
        
        # Register event handlers
        self.scraper.on(Events.DATA, on_data)
        self.scraper.on(Events.ERROR, on_error)
        self.scraper.on(Events.END, on_end)
    
    def _extract_salary(self, description: str) -> str:
        """Extract salary information from job description."""
        # Simplified salary extraction
        salary_patterns = [
            r'(?:[$£€])\s*(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)\s*(?:k|K)?\s*(?:-|to|–|and|through)\s*(?:[$£€])?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)',
            r'(?:salary|compensation|pay)(?:\s+range)?(?:\s+is)?(?:\s+between)?\s*(?:[$£€])?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)\s*(?:k|K)?\s*(?:-|to|–|and|through)\s*(?:[$£€])?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)',
        ]
        
        for pattern in salary_patterns:
            matches = re.findall(pattern, description, re.IGNORECASE)
            if matches:
                if isinstance(matches[0], tuple) and len(matches[0]) >= 2:
                    min_salary = matches[0][0].replace(',', '').replace('K', '000').replace('k', '000')
                    max_salary = matches[0][1].replace(',', '').replace('K', '000').replace('k', '000')
                    return f"${min_salary}-${max_salary}"
        
        return "Not specified"
    
    def _extract_workplace(self, description: str) -> str:
        """Extract workplace type from description."""
        workplace_patterns = {
            'Remote': [r'\bremote\b', r'\bwork from home\b', r'\bwfh\b'],
            'Hybrid': [r'\bhybrid\b', r'\bflexible\b'],
            'On-site': [r'\bon-?site\b', r'\bin-?office\b']
        }
        
        for workplace_type, patterns in workplace_patterns.items():
            for pattern in patterns:
                if re.search(pattern, description, re.IGNORECASE):
                    return workplace_type
        
        return "Not specified"
    
    def search_jobs_runner(self, keyword: str, **kwargs):
        """Run a job search with the given keyword and parameters."""
        try:
            time_filter = self._convert_time_filter(kwargs.get('time_filter', '1 day'))
            
            # Create query
            query = Query(
                query=keyword,
                options=QueryOptions(
                    locations=['United States', 'Canada'],
                    apply_link=True,
                    limit=50,
                    filters=QueryFilters(
                        relevance=RelevanceFilters.RECENT,
                        time=time_filter,
                        type=[TypeFilters.FULL_TIME],
                        experience=[
                            ExperienceLevelFilters.ENTRY_LEVEL,
                            ExperienceLevelFilters.ASSOCIATE
                        ]
                    )
                )
            )
            
            # Clear previous data
            self.scraped_job_data = []
            
            # Run the scraper
            self.logger.info(f"Starting LinkedIn job search for: {keyword}")
            self.scraper.run(queries=[query])
            
            return self.scraped_job_data
        
        except Exception as e:
            self.logger.error(f"Error in search_jobs_runner: {str(e)}")
            return []
    
    def _convert_time_filter(self, time_filter: str) -> TimeFilters:
        """Convert time filter string to TimeFilters enum."""
        mapping = {
            '1 day': TimeFilters.DAY,
            '1 week': TimeFilters.WEEK,
            '1 month': TimeFilters.MONTH
        }
        return mapping.get(time_filter.lower(), TimeFilters.DAY)
    
    def get_scraped_data(self) -> List[Dict[str, Any]]:
        """Get the scraped job data."""
        return self.scraped_job_data