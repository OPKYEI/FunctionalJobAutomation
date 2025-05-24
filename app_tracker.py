"""
Command-line utility for job application tracking management.

This script provides various commands for managing job application status:
- List all applications
- Update status of applications
- Search for applications
- Run email scanning for status updates
- Show statistics
"""

import os
import argparse
import pandas as pd
from datetime import datetime
import time
import schedule

# Import our modules
from modules.tracking import status_manager
from modules.tracking import email_scanner

# Try to import email credentials - handle both old and new formats
try:
    # Try multi-account format first
    from config.secrets import EMAIL_ACCOUNTS
    # Use the first account credentials for compatibility
    EMAIL_USERNAME = EMAIL_ACCOUNTS[0]["username"]
    EMAIL_PASSWORD = EMAIL_ACCOUNTS[0]["password"]
except ImportError:
    try:
        # Fall back to single account format
        from config.secrets import EMAIL_USERNAME, EMAIL_PASSWORD
    except ImportError:
        # No credentials found, will show error when used
        EMAIL_USERNAME = None
        EMAIL_PASSWORD = None
def main():
    parser = argparse.ArgumentParser(description='Job Application Tracking Management')
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # List applications command
    list_parser = subparsers.add_parser('list', help='List job applications')
    list_parser.add_argument('--status', choices=status_manager.APPLICATION_STATUSES, 
                            help='Filter by status')
    list_parser.add_argument('--company', help='Filter by company name (case-insensitive)')
    
    # Update status command
    update_parser = subparsers.add_parser('update', help='Update job application status')
    update_parser.add_argument('job_id', help='Job ID to update')
    update_parser.add_argument('status', choices=status_manager.APPLICATION_STATUSES,
                              help='New status')
    update_parser.add_argument('--notes', help='Notes about the status change')
    
    # Scan emails command
    scan_parser = subparsers.add_parser('scan', help='Scan emails for status updates')
    
    # Run scheduled scanning
    schedule_parser = subparsers.add_parser('schedule', help='Run scheduled email scanning')
    schedule_parser.add_argument('--interval', type=int, default=360, 
                               help='Scanning interval in minutes (default: 60)')
    
    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Show application statistics')
    
    # Parse the arguments
    args = parser.parse_args()
    
    # Process commands
    if args.command == 'list':
        list_applications(args)
    elif args.command == 'update':
        update_application(args)
    elif args.command == 'scan':
        scan_emails()
    elif args.command == 'schedule':
        run_scheduled_scanning(args.interval)
    elif args.command == 'stats':
        show_statistics()
    else:
        parser.print_help()

def list_applications(args):
    """List job applications with optional filtering."""
    # Load the CSV
    try:
        df = pd.read_csv(status_manager.APPLIED_JOBS_CSV)
        
        # Apply filters if provided
        if args.status:
            df = df[df['Status'] == args.status]
        if args.company:
            df = df[df['Company'].str.contains(args.company, case=False, na=False)]
        
        # Select only the important columns for display
        display_cols = ['Job ID', 'Title', 'Company', 'Status', 'Date Applied', 'External Link']
        display_cols = [col for col in display_cols if col in df.columns]
        
        # Print results
        if len(df) == 0:
            print("No applications found matching the criteria.")
        else:
            pd.set_option('display.max_rows', None)
            pd.set_option('display.max_columns', None)
            pd.set_option('display.width', None)
            print(f"\nFound {len(df)} application(s):")
            print(df[display_cols].to_string(index=False))
            
    except Exception as e:
        print(f"Error listing applications: {e}")

def update_application(args):
    """Update the status of a job application."""
    result = status_manager.update_application_status(args.job_id, args.status, args.notes)
    if result:
        print(f"Successfully updated job {args.job_id} to status '{args.status}'")
    else:
        print(f"Failed to update job {args.job_id}")

def scan_emails():
    """Run a single email scan for status updates with improved reporting."""
    print("🔍 Scanning emails for application status updates...")
    try:
        # Show credentials info if available
        try:
            if 'EMAIL_ACCOUNTS' in globals():
                print(f"Using multi-account configuration with {len(EMAIL_ACCOUNTS)} account(s)")
                for i, account in enumerate(EMAIL_ACCOUNTS):
                    print(f"Account {i+1}: {account['username']}")
            elif EMAIL_USERNAME:
                print(f"Using username: {EMAIL_USERNAME}")
                print(f"Password length: {len(EMAIL_PASSWORD) if EMAIL_PASSWORD else 0}")
        except:
            print("Email credentials not available in app_tracker.py")
        
        # Before scanning, count statuses
        before_stats = status_manager.generate_application_stats()
        if not before_stats:
            print("Error generating statistics.")
            return
        
        # Run the scan
        start_time = datetime.now()
        updates = email_scanner.scan_for_status_updates()
        scan_duration = datetime.now() - start_time
        
        # After scanning, count statuses again
        after_stats = status_manager.generate_application_stats()
        if not after_stats:
            print("Error generating statistics.")
            return
        
        # Calculate changes
        print("\n" + "="*50)
        print("📈 STATUS CHANGES SUMMARY:")
        print("="*50)
        
        before_counts = before_stats['statuses']
        after_counts = after_stats['statuses']
        
        # Print before and after counts
        print("Status               Before  After   Change")
        print("-"*50)
        all_statuses = sorted(set(list(before_counts.keys()) + list(after_counts.keys())))
        
        changed = False
        for status in all_statuses:
            before = before_counts.get(status, 0)
            after = after_counts.get(status, 0)
            change = after - before
            
            # Add arrow indicators for changes
            change_str = f"{change:+d}" if change != 0 else "0"
            if change > 0:
                change_str += " ↑"
                changed = True
            elif change < 0:
                change_str += " ↓"
                changed = True
            else:
                change_str += "  "
                
            print(f"{status.ljust(20)} {str(before).ljust(7)} {str(after).ljust(7)} {change_str}")
        
        # Bottom line
        print("-"*50)
        if changed:
            print(f"✅ Email scan complete! Processed in {scan_duration.total_seconds():.1f} seconds")
        else:
            print(f"ℹ️ Email scan complete - no status changes detected ({scan_duration.total_seconds():.1f} seconds)")
        
        # Debug info
        print(f"🔍 Debug: Found {updates} total updates across all accounts")
        
    except Exception as e:
        print(f"❌ Error during email scan: {e}")
        import traceback
        traceback.print_exc()

def run_scheduled_scanning(interval):
    """Run scheduled email scanning at regular intervals."""
    print(f"Starting scheduled scanning every {interval} minutes.")
    print("Press Ctrl+C to stop.")
    
    # Schedule the job
    schedule.every(interval).minutes.do(scheduled_scan)
    
    # Run the first scan immediately
    scheduled_scan()
    
    # Keep the script running
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nScheduled scanning stopped.")

def scheduled_scan():
    """Run a scan with timestamp for scheduled execution."""
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Running scheduled email scan...")
    try:
        email_scanner.scan_for_status_updates()
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Scan complete!")
    except Exception as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error: {e}")

def show_statistics():
    """Show application statistics."""
    stats = status_manager.generate_application_stats()
    if not stats:
        print("Error generating statistics.")
        return
        
    print("\n=== JOB APPLICATION STATISTICS ===")
    print(f"Total Applications: {stats['total']}")
    print("\nApplications by Status:")
    for status, count in stats['statuses'].items():
        print(f"  {status}: {count}")
    
    print(f"\nResponse Rate: {stats['response_rate']:.1f}%")
    print("====================================")

if __name__ == "__main__":
    main()
