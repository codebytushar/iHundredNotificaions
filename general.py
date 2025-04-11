import os
import psycopg2
from dotenv import load_dotenv
import boto3
from botocore.exceptions import ClientError
import logging
from typing import List, Dict, Optional, Tuple  # Add Tuple to imports
from datetime import datetime
# another_script.py
from logger import get_logger

logger = get_logger()

# Load environment variables
load_dotenv()

# # Configure logging
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

# Database configuration
DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "database": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "port": os.getenv("DB_PORT", "5432"),
}

# AWS Configuration
AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")
SENDER_EMAIL = "IHundred Admin <100activitypoints@scet.ac.in>"

class Student:
    def __init__(self, email: str, enrollmentno: str, name: str):
        self.email = email
        self.enrollmentno = enrollmentno
        self.name = name

class EmailSender:
    def __init__(self):
        self.ses_client = boto3.client(
            'ses',
            region_name=AWS_REGION,
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
        )
    
    def send_email(self, recipients: List[str], subject: str, html_body: str) -> bool:
        try:
            response = self.ses_client.send_email(
                Source=SENDER_EMAIL,
                Destination={'ToAddresses': [recipients]},
                Message={
                    'Subject': {'Data': subject},
                    'Body': {
                        'Html': {'Data': html_body},
                        'Text': {'Data': "Please view this email in an HTML-enabled client."}
                    }
                }
            )
            logger.info(f"Email sent to {', '.join(recipients)}")
            return True
        except ClientError as e:
            logger.error(f"AWS SES Error: {e.response['Error']['Message']}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return False

class DatabaseManager:
    def __init__(self):
        self.conn = psycopg2.connect(**DB_CONFIG)
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.conn.close()
    
    def get_final_year_batch(self) -> str:
        """Get the current final year batch"""
        query = """SELECT batch FROM public."Batches" WHERE "IsFinalYear" = 'Yes'"""
        with self.conn.cursor() as cursor:
            cursor.execute(query)
            return cursor.fetchone()[0]
    
    def get_students_needing_reminder(self, batch: str) -> List[Student]:
        """Get students who need the 100 points reminder"""
        query = """
            SELECT email, enrollmentno, name 
            FROM public."StudentsWithPointsandPendingActivitiesCount" 
            WHERE batch != %s AND total_points < 100 
            ORDER BY enrollmentno
        """
        with self.conn.cursor() as cursor:
            cursor.execute(query, (batch,))
            return [Student(*row) for row in cursor.fetchall()]

def create_student_email() -> Tuple[str, str]:
    """Create the reminder email content"""
    subject = "Plan Ahead for Success: 100 Activity Points Reminder!"
    
    html_body = """
<!DOCTYPE html>
<html>
<head>
    <style>
        body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }
        .header {
            color: #2c3e50;
            font-size: 24px;
            margin-bottom: 20px;
            text-align: center;
        }
        .highlight {
            background-color: #fffde7;
            padding: 15px;
            border-left: 4px solid #ffc107;
            margin: 15px 0;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
        }
        th, td {
            border: 1px solid #dddddd;
            padding: 8px;
            text-align: left;
        }
        th {
            background-color: #f5f5f5;
        }
        .footer {
            margin-top: 30px;
            font-size: 14px;
            color: #7f8c8d;
        }
        .cta-button {
            background-color: #2c3e50;
            color: white;
            padding: 10px 20px;
            text-decoration: none;
            border-radius: 4px;
            display: inline-block;
            margin: 15px 0;
        }
    </style>
</head>
<body>
    <div class="header">Stay On Track with Your 100 Points Activity!</div>
    
    <p>Dear Student,</p>
    
    <p>As you progress through your graduation at SCET, we want to remind you about the <strong>100 Points Activity system</strong> - a crucial component of your academic journey.</p>
    
    <div class="highlight">
    <strong>Key Requirements:</strong>
    <ul>
        <li><strong>25 points/year</strong> recommended to maintain excellent grades (AA)</li>
        <li><strong>50 points minimum</strong> required to graduate</li>
        <li><strong>100 points</strong> is the ideal target for exceptional achievement</li>
    </ul>
    </div>
    
    <p><strong>Why This Matters Now:</strong><br>
    Starting early gives you the advantage to:
    <ul>
    <li>Gradually accumulate points without last-minute pressure</li>
    <li>Explore diverse activities that match your interests</li>
    <li>Achieve higher grades each academic year</li>
    </ul>
    </p>
    
    <p><strong>Activity Opportunities:</strong></p>
    <table>
    <tr>
        <th>Category</th>
        <th>Examples</th>
        <th>Potential Points</th>
    </tr>
    <tr>
        <td>Sports & Games</td>
        <td>College tournaments, Zonal competitions</td>
        <td>5-25 per event</td>
    </tr>
    <tr>
        <td>Technical Events</td>
        <td>Tech fests, Project competitions</td>
        <td>10-50 per event</td>
    </tr>
    <tr>
        <td>Leadership Roles</td>
        <td>Club secretary, Event coordinator</td>
        <td>10-100 per role</td>
    </tr>
    <tr>
        <td>Innovation</td>
        <td>Prototypes, Patents, Startup projects</td>
        <td>30-100 per achievement</td>
    </tr>
    </table>
    
    <p><strong>Next Steps:</strong></p>
    <ol>
    <li>Review your current points in the <a href="https://ihundred.scet.ac.in/" target="_blank">100 Points Activity portal</a></li>
    <li>Plan activities for this semester using the 100 Points Guidelines</li>
    <li>Consult your faculty mentor for personalized suggestions</li>
    </ol>
    
    <center>
    <a href="https://ihundred2.s3.ap-south-1.amazonaws.com/V1.1_Guidelines+for+100+Activity.pdf" class="cta-button">View Complete Guidelines</a>
    </center>
    
    <div class="footer">
    <p>We are here to support you in achieving your academic goals. If you have any questions or need assistance, please feel free to reach out.</p>
    <p>Best regards,<br>
    <strong>100 Points Activity Team</strong><br>
    Sarvajanik College of Engineering & Technology</p>
    </div>
</body>
</html>
    """
    return subject, html_body

def send_reminders():
    """Main function to send all reminders"""
    email_sender = EmailSender()
    
    with DatabaseManager() as db:
        try:
            # Get the final year batch
            batch = db.get_final_year_batch()
            logger.info(f"Processing reminders for non-final year students (excluding batch {batch})")
            
            # Get students who need reminders
            students = db.get_students_needing_reminder(batch)
            
            if not students:
                logger.info("No students found needing reminders")
                return
            
            # Create email content
            subject, html_body = create_student_email()
            
            # Get unique student emails
            student_emails = list({student.email for student in students})
            
            # Send emails in chunks (AWS SES has limits on recipients per email)
            chunk_size = 100  # Adjust based on your SES limits
            for i in range(0, len(student_emails), chunk_size):
                chunk = student_emails[i:i + chunk_size]
                if email_sender.send_email(chunk, subject, html_body):
                    logger.info(f"Sent reminder to {len(chunk)} students")
                else:
                    logger.error(f"Failed to send reminder to {len(chunk)} students")
            
            logger.info("All reminders sent successfully")
            
        except Exception as e:
            logger.error(f"Error in reminder process: {str(e)}")
            raise

if __name__ == "__main__":
    send_reminders()