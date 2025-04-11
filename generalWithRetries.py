import os
import psycopg2
from dotenv import load_dotenv
import boto3
from botocore.exceptions import ClientError
from typing import List, Dict, Optional, Tuple, Set
from datetime import datetime
import time
from general import create_student_email
from logger import get_logger

logger = get_logger()
# Load environment variables
load_dotenv()



# Constants
MAX_RETRIES = 3  # Maximum number of retry attempts
RETRY_DELAY = 5  # Seconds to wait between retries
CHUNK_SIZE = 14  # Number of recipients per email (AWS SES limit is 50)

class EmailTracker:
    def __init__(self):
        self.successful_emails: Set[str] = set()
        self.failed_emails: Set[str] = set()
    
    def add_success(self, email: str):
        self.successful_emails.add(email)
        if email in self.failed_emails:
            self.failed_emails.remove(email)
    
    def add_failure(self, email: str):
        self.failed_emails.add(email)
    
    def get_failed_emails(self) -> List[str]:
        return list(self.failed_emails)

class EmailSender:
    def __init__(self):
        self.ses_client = boto3.client(
            'ses',
            region_name=os.getenv("AWS_REGION", "ap-south-1"),
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
        )
    
    def send_email(self, recipients: List[str], subject: str, html_body: str) -> bool:
        """Send email to a list of recipients with error handling"""
        try:
            response = self.ses_client.send_email(
                Source="IHundred Admin <100activitypoints@scet.ac.in>",
                Destination={'ToAddresses': [recipients]},
                Message={
                    'Subject': {'Data': subject},
                    'Body': {
                        'Html': {'Data': html_body},
                        'Text': {'Data': "Please view this email in an HTML-enabled client."}
                    }
                }
            )
            return True
        except ClientError as e:
            logger.error(f"AWS SES Error: {e.response['Error']['Message']}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return False

def send_emails_with_retry(
    email_sender: EmailSender,
    tracker: EmailTracker,
    recipients: List[str],
    subject: str,
    html_body: str
):
    """Send emails with retry logic for failed attempts"""
    for attempt in range(MAX_RETRIES + 1):
        try:
            if email_sender.send_email(recipients, subject, html_body):
                for email in recipients:
                    tracker.add_success(email)
                logger.info(f"Successfully sent to {len(recipients)} recipients")
                return
            else:
                raise Exception("Email sending failed")
        except Exception as e:
            if attempt == MAX_RETRIES:
                logger.error(f"Final attempt failed for {len(recipients)} recipients")
                for email in recipients:
                    tracker.add_failure(email)
                break
            
            logger.warning(f"Attempt {attempt + 1} failed, retrying in {RETRY_DELAY} seconds...")
            time.sleep(RETRY_DELAY)

def send_reminders():
    """Main function to send all reminders with tracking"""
    email_sender = EmailSender()
    tracker = EmailTracker()
    
    with psycopg2.connect(
        host=os.getenv("DB_HOST"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        port=os.getenv("DB_PORT", "5432")
    ) as conn:
        try:
            # Get the final year batch
            with conn.cursor() as cursor:
                cursor.execute("""SELECT batch FROM public."Batches" WHERE "IsFinalYear" = 'Yes'""")
                batch = cursor.fetchone()[0]
            
            logger.info(f"Processing reminders for non-final year students (excluding batch {batch})")
            
            # Get students who need reminders
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT DISTINCT email 
                    FROM public."StudentsWithPointsandPendingActivitiesCount" 
                    WHERE batch != %s AND total_points < 100
                """, (batch,))
                student_emails = [row[0] for row in cursor.fetchall()]
            
            if not student_emails:
                logger.info("No students found needing reminders")
                return
            
            # Create email content
            subject, html_body = create_student_email()
            
            # Process emails in chunks
            for i in range(0, len(student_emails), CHUNK_SIZE):
                chunk = student_emails[i:i + CHUNK_SIZE]
                send_emails_with_retry(email_sender, tracker, chunk, subject, html_body)
            
            # Log final results
            logger.info(f"Successfully sent to {len(tracker.successful_emails)} emails")
            if tracker.failed_emails:
                logger.error(f"Failed to send to {len(tracker.failed_emails)} emails: {list(tracker.failed_emails)}")
                # Here you could save failed emails to a file or database for later retry
                with open("failed_emails.txt", "w") as f:
                    f.write("\n".join(tracker.failed_emails))
            
        except Exception as e:
            logger.error(f"Error in reminder process: {str(e)}")
            raise

if __name__ == "__main__":
    send_reminders()