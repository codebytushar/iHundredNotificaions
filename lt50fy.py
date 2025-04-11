import os
import psycopg2
from dotenv import load_dotenv
import boto3
from botocore.exceptions import ClientError
from logger_config import get_logger
from typing import List, Dict, Optional, Tuple  # Add Tuple to imports
from datetime import datetime

# Load environment variables
load_dotenv()

logger = get_logger()

# Database configuration
DB_CONFIG = {
    'host': os.getenv("DB_HOST"),
    'dbname': os.getenv("DB_NAME"),
    'user': os.getenv("DB_USER"),
    'password': os.getenv("DB_PASSWORD"),
    'port': os.getenv("DB_PORT", 5432),
}

# AWS Configuration
AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")
SENDER_EMAIL = "IHundred Admin <100activitypoints@scet.ac.in>"

class Department:
    def __init__(self, deptcode: str, name: str, deprep: str, deprepemail: str, 
                 hodname: str, hodemail: str, lt50: int = 0):
        self.deptcode = deptcode
        self.name = name
        self.deprep = deprep
        self.deprepemail = deprepemail
        self.hodname = hodname
        self.hodemail = hodemail
        self.lt50 = lt50

class Student:
    def __init__(self, name: str, email: str, enrollmentno: str, 
                 total_points: int, pending_activities: int):
        self.name = name
        self.email = email
        self.enrollmentno = enrollmentno
        self.total_points = total_points
        self.pending_activities = pending_activities

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
    
    def get_departments_with_lt50_students(self, batch: str) -> List[Department]:
        """Get departments with students having less than 50 points in final year"""
        query = """
            SELECT 
                d.deptcode, d.name, d.deprep, d.deprepemail, d.hodname, d.hodemail,
                SUM(a.lt50) as lt50_count
            FROM public."Departments" d
            JOIN public."AdminSummary" a ON d.deptcode = a.deptcode
            WHERE a.batch = %s AND a.lt50 > 0 AND d.deptcode NOT IN ('ASH', 'DET')
            GROUP BY d.deptcode, d.name, d.deprep, d.deprepemail, d.hodname, d.hodemail
            ORDER BY d.deptcode
        """
        with self.conn.cursor() as cursor:
            cursor.execute(query, (batch,))
            return [
                Department(*row) for row in cursor.fetchall()
            ]
    
    def get_students_with_lt50_points(self, deptcode: str, batch: str) -> List[Student]:
        """Get students with less than 50 points in a department"""
        query = """
            SELECT name, email, enrollmentno, total_points, pending_activities
            FROM public."StudentsWithPointsandPendingActivitiesCount"
            WHERE deptcode = %s AND batch = %s AND total_points < 50
            ORDER BY enrollmentno
        """
        with self.conn.cursor() as cursor:
            cursor.execute(query, (deptcode, batch))
            return [
                Student(*row) for row in cursor.fetchall()
            ]

def create_department_email(department: Department) -> Tuple[str, str]:
    """Create email content for department representatives"""
    subject = f"Notification: Students with Less Than 50 Points in {department.name}"
    
    html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Student Points Notification</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .email-container {{
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 20px;
            background-color: #f9f9f9;
        }}
        .header {{
            font-size: 18px;
            font-weight: bold;
            margin-bottom: 20px;
        }}
        .content {{
            margin-bottom: 20px;
        }}
        .footer {{
            font-size: 14px;
            color: #777;
            margin-top: 20px;
        }}
        strong {{
            color: #e74c3c;
        }}
    </style>
</head>
<body>
    <div class="email-container">
        <div class="header">Dear {department.deprep},</div>
        <div class="content">
            <p>This is to inform you that there are <strong>{department.lt50} students</strong> 
            in your department (<strong>{department.name}</strong>) who have less than 50 points 
            and are in their final year.</p>
            
            <p>Please take the necessary actions to help these students meet the graduation requirements.</p>
        </div>
        <div class="footer">
            Regards,<br>
            <strong>100 Points Activity Team</strong>
        </div>
    </div>
</body>
</html>
    """
    return subject, html_body

def create_student_email(student: Student) -> Tuple[str, str]:
    """Create email content for students"""
    subject = "Important Notification: Less Than 50 Points in Your 100 Points Activity Record"
    
    html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Important Notification</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .email-container {{
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 20px;
            background-color: #f9f9f9;
        }}
        .header {{
            font-size: 18px;
            font-weight: bold;
            margin-bottom: 20px;
        }}
        .content {{
            margin-bottom: 20px;
        }}
        .footer {{
            font-size: 14px;
            color: #777;
            margin-top: 20px;
        }}
        strong {{
            color: #e74c3c;
        }}
    </style>
</head>
<body>
    <div class="email-container">
        <div class="header">Dear {student.name},</div>
        <div class="content">
            <p>We hope this message finds you well. This is to inform you that you currently have 
            <strong>less than 50 points</strong> in your 100 Points Activity record, and you are 
            in your final year of study.</p>
            
            <p>It is crucial to address this matter promptly to ensure you meet all the requirements 
            for graduation. We encourage you to take the necessary steps to improve your points balance.</p>
            
            <p>If you need guidance or support, please feel free to reach out to your department 
            or the 100 Points Activity Team.</p>
        </div>
        <div class="footer">
            Regards,<br>
            <strong>100 Points Activity Team</strong>
        </div>
    </div>
</body>
</html>
    """
    return subject, html_body

def send_notifications():
    """Main function to send all notifications"""
    email_sender = EmailSender()
    
    with DatabaseManager() as db:
        try:
            # Get the final year batch
            batch = db.get_final_year_batch()
            logger.info(f"Processing notifications for final year batch: {batch}")
            
            # Get departments with students having <50 points
            departments = db.get_departments_with_lt50_students(batch)
            
            if not departments:
                logger.info("No departments found with students having less than 50 points")
                return
            
            for department in departments:
                # Send email to department representatives
                dept_subject, dept_body = create_department_email(department)
                recipients = [email for email in [department.deprepemail, department.hodemail] if email]
                
                if email_sender.send_email(recipients, dept_subject, dept_body):
                    logger.info(f"Sent notification to {department.name} department representatives")
                
                # Send emails to individual students
                students = db.get_students_with_lt50_points(department.deptcode, batch)
                for student in students:
                    student_subject, student_body = create_student_email(student)
                    if email_sender.send_email([student.email], student_subject, student_body):
                        logger.info(f"Sent notification to student {student.name} ({student.enrollmentno})")
            
            logger.info("All notifications sent successfully")
            
        except Exception as e:
            logger.error(f"Error in notification process: {str(e)}")
            raise

if __name__ == "__main__":
    logger.info("Notifications Regarding Less Than 50 points and In a Final Year : Scheduled Script Started Running...")
    send_notifications()
    logger.info("Notifications Regarding Less Than 50 points and In a Final Year : Scheduled Script Ended...")