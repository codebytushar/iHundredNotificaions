import os
import psycopg2
from dotenv import load_dotenv
import boto3
from botocore.exceptions import ClientError
from logger_config import get_logger
from typing import List, Dict, Tuple, Optional

# Load environment variables
load_dotenv()

logger = get_logger()

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

class StudentRecord:
    def __init__(self, enrollmentno: str, name: str, email: str, 
                 total_points: int, pending_activities: int, verifierEmail: str):
        self.enrollmentno = enrollmentno
        self.name = name
        self.email = email
        self.total_points = total_points
        self.pending_activities = pending_activities
        self.verifierEmail = verifierEmail

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
                Destination={'ToAddresses': recipients},
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
            logger.error(f"AWS SES Error sending email: {e.response['Error']['Message']}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending email: {str(e)}")
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
    
    def get_students_with_50_to_100_points(self, batch: str) -> List[StudentRecord]:
        """Get students with points between 50-100 in the final year"""
        query = """
            SELECT enrollmentno, name, email, total_points, pending_activities, "verifierEmail"
            FROM public."StudentsWithPointsandPendingActivitiesCount"
            WHERE batch = %s AND total_points >= 50 AND total_points < 100
            ORDER BY enrollmentno
        """
        with self.conn.cursor() as cursor:
            cursor.execute(query, (batch,))
            return [
                StudentRecord(*row) for row in cursor.fetchall()
            ]

def create_student_email() -> Tuple[str, str]:
    """Create email content for students"""
    subject = "Important Notification: Less Than 100 Points in Your 100 Points Activity Record"
    
    html_body = """
<!DOCTYPE html>
<html>
<head>
<style>
    body {
        font-family: Arial, sans-serif;
        line-height: 1.6;
        color: #333333;
        max-width: 600px;
        margin: 0 auto;
        padding: 20px;
    }
    .header {
        color: #2c3e50;
        font-size: 24px;
        margin-bottom: 20px;
    }
    .content {
        margin-bottom: 20px;
    }
    strong {
        color: #e74c3c;
    }
    .footer {
        margin-top: 30px;
        font-style: italic;
        color: #7f8c8d;
    }
    .signature {
        font-weight: bold;
        margin-top: 20px;
    }
</style>
</head>
<body>
<div class="header">Reminder: 100 Points Activity Record Update</div>

<div class="content">
    <p>Dear Student,</p>
    
    <p>We hope you are doing well. This is a friendly reminder that your current <strong>100 Points Activity record shows fewer than 100 points</strong>. While the <strong>minimum requirement to graduate is 50 points</strong>, achieving the full <strong>100 points</strong> is strongly encouraged to maximize your learning experience and meet the desired benchmark for your degree.</p>
    
    <p>As you are in your final year, we urge you to take proactive steps to improve your points balance before graduation. If you need assistance identifying eligible activities or have any questions, please don't hesitate to contact your department or the 100 Points Activity Team.</p>
    
    <p>Thank you for your attention to this matter. We're here to support you in reaching your academic goals!</p>
</div>

<div class="footer">
    <p>Best regards,</p>
    <p class="signature">100 Points Activity Team, SCET.</p>
</div>
</body>
</html>
    """
    return subject, html_body

def create_verifier_email(students: List[StudentRecord]) -> Tuple[str, str]:
    """Create email content for verifiers"""
    subject = "Action Required: Students With Less Than 100 Points in 100 Points Activity"
    
    student_rows = "\n".join([
        f"""
        <tr>
            <td>{student.enrollmentno}</td>
            <td>{student.name}</td>
            <td>{student.total_points}</td>
            <td>{student.pending_activities}</td>
        </tr>
        """ for student in students
    ])
    
    html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            color: #2c3e50;
            font-size: 24px;
            margin-bottom: 20px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            border: 1px solid #dddddd;
            padding: 8px;
            text-align: left;
        }}
        th {{
            background-color: #f2f2f2;
        }}
        .footer {{
            margin-top: 30px;
            font-style: italic;
            color: #7f8c8d;
        }}
    </style>
</head>
<body>
    <div class="header">Students With Less Than 100 Points</div>
    
    <p>Dear Verifier,</p>
    
    <p>The following students under your supervision currently have less than 100 points in their 100 Points Activity record and in final year of their graduation (minimum required for graduation is 50 points):</p>
    
    <table>
        <thead>
            <tr>
                <th>Enrollment No</th>
                <th>Student Name</th>
                <th>Current Points</th>
                <th>Pending Activities</th>
            </tr>
        </thead>
        <tbody>
            {student_rows}
        </tbody>
    </table>
    
    <p>Please encourage these students to participate in additional activities to reach the recommended 100 points before graduation.</p>
    
    <div class="footer">
        <p>Best regards,</p>
        <p><strong>100 Points Activity Team, SCET</strong></p>
    </div>
</body>
</html>
    """
    return subject, html_body

def send_notifications():
    """Main function to send notifications"""
    email_sender = EmailSender()
    
    with DatabaseManager() as db:
        try:
            # Get the final year batch
            batch = db.get_final_year_batch()
            logger.info(f"Processing notifications for final year batch: {batch}")
            
            # Get students with 50-100 points
            students = db.get_students_with_50_to_100_points(batch)
            
            if not students:
                logger.info("No students found with points between 50-100")
                return
            
            # Send emails to students
            student_subject, student_body = create_student_email()
            student_emails = list(set([student.email for student in students]))
            
            if email_sender.send_email(student_emails, student_subject, student_body):
                logger.info(f"Sent notifications to {len(student_emails)} students")
            
            # Group students by verifier and send emails
            verifier_map: Dict[str, List[StudentRecord]] = {}
            for student in students:
                if student.verifierEmail not in verifier_map:
                    verifier_map[student.verifierEmail] = []
                verifier_map[student.verifierEmail].append(student)
            
            for verifier_email, verifier_students in verifier_map.items():
                verifier_subject, verifier_body = create_verifier_email(verifier_students)
                if email_sender.send_email([verifier_email], verifier_subject, verifier_body):
                    logger.info(f"Sent notification to verifier {verifier_email} about {len(verifier_students)} students")
                
        except Exception as e:
            logger.error(f"Error in notification process: {str(e)}")
            raise

if __name__ == "__main__":
    logger.info("Notification to Final Year Students to Complete 100 Points : Schedule Script Started Running...")
    send_notifications()
    logger.info("Notification to Final Year Students to Complete 100 Points : Schedule Script Ended...")