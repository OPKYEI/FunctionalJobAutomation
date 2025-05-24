# src/scraper_linkedin/linkedin_manager.py

import logging
from typing import List, Dict, Any
from src.config import LINKEDIN_EMAIL, LINKEDIN_PASSWORD

from .integrated_scraper import IntegratedLinkedInScraper

class LinkedIn:
    """Manager for LinkedIn job searches."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.linkedin = IntegratedLinkedInScraper(LINKEDIN_EMAIL, LINKEDIN_PASSWORD)
        self.scraped_job_data: List[Dict[str, Any]] = []

    def search_jobs_runner(self, keyword: str, **kwargs) -> None:
        """Run a job search with the given keyword and parameters."""
        try:
            self.scraped_job_data = self.linkedin.search_jobs_runner(keyword, **kwargs)
            self.logger.info(f"Successfully scraped {len(self.scraped_job_data)} job listings")
        except Exception as e:
            self.logger.error(f"An error occurred in search_jobs_runner: {str(e)}")

    def get_scraped_data(self) -> List[Dict[str, Any]]:
        """Get the scraped job data."""
        return self.scraped_job_data