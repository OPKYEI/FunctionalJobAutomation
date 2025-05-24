from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import csv
from datetime import datetime
import os
import pandas as pd

app = Flask(__name__)
CORS(app)

PATH = 'all excels/'
##> ------ Karthik Sarode : karthik.sarode23@gmail.com - UI for excel files ------
@app.route('/')
def home():
    """Displays the home page of the application."""
    return render_template('index.html')

"""
Updated get_applied_jobs route for app.py to include Location
"""

@app.route('/applied-jobs', methods=['GET'])
def get_applied_jobs():
    '''
    Retrieves a list of applied jobs from the applications history CSV file.
    
    Returns a JSON response containing a list of jobs, each with details such as 
    Job ID, Title, Company, Work Location, HR Name, etc.
    
    If the CSV file is not found, returns a 404 error with a relevant message.
    If any other exception occurs, returns a 500 error with the exception message.
    '''

    try:
        jobs = []
        with open(PATH + 'all_applied_applications_history.csv', 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                jobs.append({
                    'Job_ID': row['Job ID'],
                    'Title': row['Title'],
                    'Company': row['Company'],
                    'Work_Location': row.get('Work Location', 'Not specified'),  # Add location field
                    'Work_Style': row.get('Work Style', 'Not specified'),  # ← ADD THIS LINE
                    'HR_Name': row.get('HR Name', ''),
                    'HR_Link': row.get('HR Link', ''),
                    'Job_Link': row.get('Job Link', ''),
                    'External_Job_link': row.get('External Job link', ''),
                    'Date_Applied': row.get('Date Applied', ''),
                    'Status': row.get('Status', 'Applied'),
                    'Interview_Date': row.get('Interview Date', ''),  # Add Interview Date
                    'Resume': row.get('Resume', ''),  # Include resume filename for verification
                    'Salary_Range': row.get('Salary Range', ''), 
                    'Notes': row.get('Notes', '')  # Include notes
                })
        return jsonify(jobs)
    except FileNotFoundError:
        return jsonify({"error": "No applications history found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500
'''
@app.route('/applied-jobs/<job_id>', methods=['PUT'])
def update_applied_date(job_id):
    """
    Updates the 'Date Applied' field of a job in the applications history CSV file.

    Args:
        job_id (str): The Job ID of the job to be updated.

    Request body should contain:
        date_applied (str): The new date in format 'YYYY-MM-DD HH:MM:SS'
                           If not provided, current date and time will be used.
        
    Returns:
        A JSON response with a message indicating success or failure of the update.
    """
    try:
        # Get the new date from the request body, or use current time if not provided
        request_data = request.get_json() or {}
        new_date = request_data.get('date_applied')
        
        # If no date provided, use current time
        if not new_date:
            new_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        else:
            # Validate the date format
            try:
                datetime.strptime(new_date, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                return jsonify({"error": "Invalid date format. Use 'YYYY-MM-DD HH:MM:SS'"}), 400
        
        csvPath = PATH + 'all_applied_applications_history.csv'
        
        if not os.path.exists(csvPath):
            return jsonify({"error": f"CSV file not found at {csvPath}"}), 404
            
        # Use pandas for easier handling
        df = pd.read_csv(csvPath)
        
        # Find the job
        job_mask = df['Job ID'] == job_id
        if not job_mask.any():
            return jsonify({"error": f"Job ID {job_id} not found"}), 404
            
        # Update the date applied
        df.loc[job_mask, 'Date Applied'] = new_date
        
        # Add note about manual update
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
        new_note = f"[{timestamp}] Date Applied manually updated to '{new_date}' via web interface"
        
        # Check if Notes column exists, if not create it
        if 'Notes' not in df.columns:
            df['Notes'] = ''
            
        # Update notes (append to existing)
        current_notes = df.loc[job_mask, 'Notes'].iloc[0]
        if pd.isna(current_notes) or current_notes == '':
            df.loc[job_mask, 'Notes'] = new_note
        else:
            df.loc[job_mask, 'Notes'] = current_notes + '\n' + new_note
            
        # Save the updates
        df.to_csv(csvPath, index=False)
        
        return jsonify({
            "message": "Date Applied updated successfully",
            "job_id": job_id,
            "new_date": new_date
        }), 200
        
    except Exception as e:
        print(f"Error updating date applied: {str(e)}")  # Debug log
        return jsonify({"error": str(e)}), 500
'''
@app.route('/applied-jobs/<job_id>/date-applied', methods=['PUT'])
def update_date_applied(job_id):
    """
    Updates the 'Date Applied' field of a job in the applications history CSV file.
    """
    try:
        # Get the new date from the request body
        request_data = request.get_json() or {}
        new_date = request_data.get('date_applied')
        notes = request_data.get('notes', '')
        
        # If no date provided, use current time
        if not new_date:
            new_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        else:
            # Ensure the date is in the correct format
            try:
                # Try to parse the date to validate it
                parsed_date = datetime.strptime(new_date, '%Y-%m-%d %H:%M:%S')
                # Format it consistently
                new_date = parsed_date.strftime('%Y-%m-%d %H:%M:%S')
            except ValueError:
                # If the format is different, try to handle it
                try:
                    # This handles formats like "2025-05-19T07:04" (HTML datetime-local format)
                    if 'T' in new_date:
                        parsed_date = datetime.strptime(new_date, '%Y-%m-%dT%H:%M')
                        new_date = parsed_date.strftime('%Y-%m-%d %H:%M:%S')
                except ValueError:
                    return jsonify({"error": "Invalid date format. Use 'YYYY-MM-DD HH:MM:SS'"}), 400
        
        csvPath = PATH + 'all_applied_applications_history.csv'
        
        if not os.path.exists(csvPath):
            return jsonify({"error": f"CSV file not found at {csvPath}"}), 404
            
        # Use pandas for easier handling
        df = pd.read_csv(csvPath)
        
        # Find the job
        job_mask = df['Job ID'] == job_id
        if not job_mask.any():
            return jsonify({"error": f"Job ID {job_id} not found"}), 404
            
        # Update the date applied
        df.loc[job_mask, 'Date Applied'] = new_date
        
        # Add note about manual update
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
        new_note = f"[{timestamp}] Date Applied manually updated to '{new_date}' via web interface"
        if notes:
            new_note += f"\nUser notes: {notes}"
        
        # Check if Notes column exists, if not create it
        if 'Notes' not in df.columns:
            df['Notes'] = ''
            
        # Update notes (append to existing)
        current_notes = df.loc[job_mask, 'Notes'].iloc[0]
        if pd.isna(current_notes) or current_notes == '':
            df.loc[job_mask, 'Notes'] = new_note
        else:
            df.loc[job_mask, 'Notes'] = current_notes + '\n' + new_note
            
        # Save the updates
        df.to_csv(csvPath, index=False)
        
        return jsonify({
            "message": "Date Applied updated successfully",
            "job_id": job_id,
            "new_date": new_date,
            "status": "success"
        }), 200
        
    except Exception as e:
        print(f"Error updating date applied: {str(e)}")  # Debug log
        return jsonify({"error": str(e), "status": "error"}), 500
        
@app.route('/applied-jobs/<job_id>/status', methods=['PUT'])
def update_job_status(job_id):
    """
    Updates the 'Status' field of a job in the applications history CSV file.

    Args:
        job_id (str): The Job ID of the job to be updated.

    Request body should contain:
        status (str): The new status value

    Returns:
        A JSON response with a message indicating success or failure of the update
        operation.
    """
    try:
        # Get the new status from the request body
        request_data = request.get_json()
        if not request_data or 'status' not in request_data:
            return jsonify({"error": "Status field is required"}), 400
            
        new_status = request_data['status']
        
        # Define valid statuses
        valid_statuses = ['Applied', 'Assessment', 'Follow-up Required', 
                          'Interview Scheduled', 'Interviewed', 'Rejected', 
                          'Offered', 'Accepted', 'Declined']
                          
        if new_status not in valid_statuses:
            return jsonify({"error": f"Invalid status. Must be one of: {', '.join(valid_statuses)}"}), 400
        
        csvPath = PATH + 'all_applied_applications_history.csv'
        
        if not os.path.exists(csvPath):
            return jsonify({"error": f"CSV file not found at {csvPath}"}), 404
            
        # Use pandas for easier handling
        df = pd.read_csv(csvPath)
        
        # Find the job
        job_mask = df['Job ID'] == job_id
        if not job_mask.any():
            return jsonify({"error": f"Job ID {job_id} not found"}), 404
            
        # Update the status
        df.loc[job_mask, 'Status'] = new_status
        
        # Add note about manual update
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
        new_note = f"[{timestamp}] Status manually updated to '{new_status}' via web interface"
        
        # Check if Notes column exists, if not create it
        if 'Notes' not in df.columns:
            df['Notes'] = ''
            
        # Update notes (append to existing)
        current_notes = df.loc[job_mask, 'Notes'].iloc[0]
        if pd.isna(current_notes) or current_notes == '':
            df.loc[job_mask, 'Notes'] = new_note
        else:
            df.loc[job_mask, 'Notes'] = current_notes + '\n' + new_note
            
        # Save the updates
        df.to_csv(csvPath, index=False)
        
        return jsonify({
            "message": f"Status updated successfully to '{new_status}'",
            "job_id": job_id
        }), 200
        
    except Exception as e:
        print(f"Error updating job status: {str(e)}")  # Debug log
        return jsonify({"error": str(e)}), 500

@app.route('/applied-jobs/<job_id>/interview-date', methods=['PUT'])
def update_interview_date(job_id):
    """
    Updates the 'Interview Date' field of a job in the applications history CSV file.

    Args:
        job_id (str): The Job ID of the job to be updated.

    Request body should contain:
        interview_date (str): The new interview date in format 'YYYY-MM-DD HH:MM:SS'
        
    Returns:
        A JSON response with a message indicating success or failure of the update
        operation.
    """
    try:
        # Get the new interview date from the request body
        request_data = request.get_json()
        if not request_data or 'interview_date' not in request_data:
            return jsonify({"error": "Interview date field is required"}), 400
            
        new_interview_date = request_data['interview_date']
        
        # Validate the date format
        try:
            if new_interview_date:  # Allow empty string to clear the date
                datetime.strptime(new_interview_date, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            return jsonify({"error": "Invalid date format. Use 'YYYY-MM-DD HH:MM:SS'"}), 400
        
        csvPath = PATH + 'all_applied_applications_history.csv'
        
        if not os.path.exists(csvPath):
            return jsonify({"error": f"CSV file not found at {csvPath}"}), 404
            
        # Use pandas for easier handling
        df = pd.read_csv(csvPath)
        
        # Add Interview Date column if it doesn't exist
        if 'Interview Date' not in df.columns:
            df['Interview Date'] = None
            
        # Find the job
        job_mask = df['Job ID'] == job_id
        if not job_mask.any():
            return jsonify({"error": f"Job ID {job_id} not found"}), 404
            
        # Update the interview date
        df.loc[job_mask, 'Interview Date'] = new_interview_date
        
        # Update status to Interview Scheduled if adding a date and current status is Applied
        current_status = df.loc[job_mask, 'Status'].iloc[0]
        if new_interview_date and current_status == 'Applied':
            df.loc[job_mask, 'Status'] = 'Interview Scheduled'
            status_update_msg = f"Status automatically updated to 'Interview Scheduled'"
        else:
            status_update_msg = ""
        
        # Add note about manual update
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
        new_note = f"[{timestamp}] Interview date manually updated to '{new_interview_date}' via web interface"
        if status_update_msg:
            new_note += f"\n{status_update_msg}"
        
        # Check if Notes column exists, if not create it
        if 'Notes' not in df.columns:
            df['Notes'] = ''
            
        # Update notes (append to existing)
        current_notes = df.loc[job_mask, 'Notes'].iloc[0]
        if pd.isna(current_notes) or current_notes == '':
            df.loc[job_mask, 'Notes'] = new_note
        else:
            df.loc[job_mask, 'Notes'] = current_notes + '\n' + new_note
            
        # Save the updates
        df.to_csv(csvPath, index=False)
        
        response_message = f"Interview date updated successfully"
        if status_update_msg:
            response_message += f". {status_update_msg}"
            
        return jsonify({
            "message": response_message,
            "job_id": job_id
        }), 200
        
    except Exception as e:
        print(f"Error updating interview date: {str(e)}")  # Debug log
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)