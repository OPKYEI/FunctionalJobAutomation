"""
Job application status manager module.

This module enhances the job application tracking with status management 
and ensures all applications (Easy Apply and External) are properly marked.
"""

import os
import pandas as pd
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    filename='status_manager.log'
)
logger = logging.getLogger(__name__)

# Path to the applied jobs CSV
APPLIED_JOBS_CSV = "all excels/all_applied_applications_history.csv"

# Valid application statuses
APPLICATION_STATUSES = [
    'Applied', 
    'Assessment',
    'Follow-up Required',
    'Interview Scheduled', 
    'Interviewed', 
    'Rejected', 
    'Offered', 
    'Accepted', 
    'Declined'
]

def ensure_status_column():
    """
    Make sure the Status column exists in the CSV and all applications have a status.
    """
    try:
        if not os.path.exists(APPLIED_JOBS_CSV):
            logger.warning(f"CSV file {APPLIED_JOBS_CSV} does not exist yet.")
            return False
            
        # Load the CSV
        df = pd.read_csv(APPLIED_JOBS_CSV)
        
        # Add Status column if it doesn't exist
        if 'Status' not in df.columns:
            df['Status'] = 'Applied'
            logger.info("Added Status column to applications CSV")
        else:
            # Ensure all rows have a status
            df['Status'] = df['Status'].fillna('Applied')
            logger.info("Filled missing status values with 'Applied'")
        
        # Ensure Applied column is filled for all applications
        if 'Applied' in df.columns:
            # Fill any empty or NaN values with check mark
            df['Applied'] = df['Applied'].fillna('✓')
            # Convert any non-empty, non-check-mark values to check mark
            df.loc[df['Applied'].notnull() & (df['Applied'] != ''), 'Applied'] = '✓'
            logger.info("Updated Applied column for all applications")
            
        # Write back to CSV
        df.to_csv(APPLIED_JOBS_CSV, index=False)
        logger.info("Successfully updated application status tracking")
        return True
        
    except Exception as e:
        logger.error(f"Error ensuring status column: {e}")
        return False

def update_application_status(job_id, new_status, notes=None):
    """Update the status of a job application in the CSV file."""
    if new_status not in APPLICATION_STATUSES:
        print(f"Error: '{new_status}' is not a valid status. Valid statuses are: {', '.join(APPLICATION_STATUSES)}")
        return False
        
    try:
        # Read the current data
        df = pd.read_csv(APPLIED_JOBS_CSV)
        
        # Find the job by ID
        job_idx = df.index[df['Job ID'] == job_id].tolist()
        if not job_idx:
            print(f"Error: Job ID '{job_id}' not found.")
            return False
            
        # Update the status
        df.at[job_idx[0], 'Status'] = new_status
        
        # Add notes if provided
        if notes and 'Notes' in df.columns:
            current_notes = df.at[job_idx[0], 'Notes']
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
            new_note = f"[{timestamp}] Status changed to '{new_status}': {notes}"
            
            if pd.isna(current_notes):
                df.at[job_idx[0], 'Notes'] = new_note
            else:
                df.at[job_idx[0], 'Notes'] = f"{current_notes}\n{new_note}"
        
        # Save the updated data
        df.to_csv(APPLIED_JOBS_CSV, index=False)
        return True
        
    except Exception as e:
        print(f"Error updating application status: {e}")
        return False

def get_application_by_company(company_name):
    """
    Get all applications for a specific company.
    
    Args:
        company_name: Name of the company (case-insensitive partial match)
    
    Returns:
        DataFrame: Matching applications
    """
    try:
        df = pd.read_csv(APPLIED_JOBS_CSV)
        mask = df['Company'].str.contains(company_name, case=False, na=False)
        return df[mask]
    except Exception as e:
        logger.error(f"Error searching for company {company_name}: {e}")
        return pd.DataFrame()

def get_applications_by_status(status):
    """
    Get all applications with a specific status.
    
    Args:
        status: Status to filter by
    
    Returns:
        DataFrame: Matching applications
    """
    if status not in APPLICATION_STATUSES:
        logger.error(f"Invalid status: {status}")
        return pd.DataFrame()
        
    try:
        df = pd.read_csv(APPLIED_JOBS_CSV)
        if 'Status' not in df.columns:
            df['Status'] = 'Applied'
            df.to_csv(APPLIED_JOBS_CSV, index=False)
            
        return df[df['Status'] == status]
    except Exception as e:
        logger.error(f"Error searching for status {status}: {e}")
        return pd.DataFrame()

def generate_application_stats():
    """
    Generate statistics about job applications by status.
    
    Returns:
        dict: Statistics by status
    """
    try:
        df = pd.read_csv(APPLIED_JOBS_CSV)
        if 'Status' not in df.columns:
            df['Status'] = 'Applied'
            
        stats = {
            'total': len(df),
            'statuses': df['Status'].value_counts().to_dict()
        }
        
        # Calculate response rate
        interviews = stats['statuses'].get('Interview Scheduled', 0) + \
                     stats['statuses'].get('Interviewed', 0) + \
                     stats['statuses'].get('Offered', 0) + \
                     stats['statuses'].get('Accepted', 0) + \
                     stats['statuses'].get('Declined', 0)
                     
        if stats['total'] > 0:
            stats['response_rate'] = (interviews / stats['total']) * 100
        else:
            stats['response_rate'] = 0
            
        return stats
    except Exception as e:
        logger.error(f"Error generating application stats: {e}")
        return {}

# Run this when the module is imported to ensure the Status column exists
ensure_status_column()

if __name__ == "__main__":
    # If run directly, ensure everything is set up
    if ensure_status_column():
        print("Status tracking is configured and ready.")
    else:
        print("Error setting up status tracking.")
