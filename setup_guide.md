# Installation Guide: Job Application Status Tracking System

This guide will help you set up the job application status tracking system with automated email scanning.

## 1. Create Required Directories

First, create the necessary directory structure:

```bash
mkdir -p modules/tracking
```

## 2. Install Dependencies

Install the required Python packages:

```bash
pip install pandas schedule imaplib-ssl
```

## 3. Copy Files to Correct Locations

1. Save `email_scanner.py` to `modules/tracking/email_scanner.py`
2. Save `status_manager.py` to `modules/tracking/status_manager.py`
3. Save `app_tracker.py` to the root directory
4. Create a blank `__init__.py` file in the `modules/tracking` directory:

```bash
touch modules/tracking/__init__.py
```

## 4. Update Your runAiBot.py File

Replace the `submitted_jobs` function in your `runAiBot.py` with the updated version provided. This ensures that all applications (both Easy Apply and External Link) will be properly marked in the "Applied" column.

## 5. Configure Email Access

For the email scanner to work, edit `modules/tracking/email_scanner.py` and update these values:

```python
# Email configuration (to be moved to secrets.py)
EMAIL_USERNAME = "your.email@gmail.com"  # Your email address
EMAIL_PASSWORD = "your-app-password"     # App password (not your regular password)
IMAP_SERVER = "imap.gmail.com"           # IMAP server (change if not using Gmail)
IMAP_PORT = 993
```

**Note about Gmail**: If you're using Gmail, you need to:
1. Enable 2-Step Verification in your Google Account
2. Generate an "App Password" from your Google Account security settings
3. Use that App Password instead of your regular password

## 6. Running the Application Tracker

### One-time Status Update

To ensure all your existing applications have a Status:

```bash
python app_tracker.py list
```

### Scanning Emails for Updates

To scan your emails for status updates:

```bash
python app_tracker.py scan
```

### Schedule Regular Scanning

To continuously scan for updates every 30 minutes:

```bash
python app_tracker.py schedule --interval 30
```

### Checking Statistics

To see overall application statistics:

```bash
python app_tracker.py stats
```

### Manually Updating Status

To manually update an application status:

```bash
python app_tracker.py update JOB_ID "Interview Scheduled" --notes "Phone interview scheduled for next Tuesday"
```

Replace `JOB_ID` with the actual Job ID from your applications.

## 7. Integration with runAiBot.py

The system will automatically mark all applications as "Applied" ✓ in the Applied column. The status tracking is fully integrated with your existing application system.
