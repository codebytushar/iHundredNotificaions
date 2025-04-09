import os
from dotenv import load_dotenv  # Add this import
import psycopg2
import boto3
from botocore.exceptions import ClientError
import logging
from typing import List, Dict, Tuple, Optional
load_dotenv()  # Add this line before accessing any environment variables

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database configuration
DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "database": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "port": os.getenv("DB_PORT", "5432"),
}

# AWS Configuration
AWS_REGION = os.getenv("AWS_REGION")
SENDER_EMAIL = "IHundred Admin <100activitypoints@scet.ac.in>"

class UnAllocatedStudent:
    def __init__(self, id: str, name: str, email: str, role: str, 
                 verifierEmail: Optional[str], deptcode: str, 
                 batch: str, enrollmentno: str, userstatus: str):
        self.id = id
        self.name = name
        self.email = email
        self.role = role
        self.verifierEmail = verifierEmail
        self.deptcode = deptcode
        self.batch = batch
        self.enrollmentno = enrollmentno
        self.userstatus = userstatus

class Department:
    def __init__(self, deptcode: str, deprepemail: str):
        self.deptcode = deptcode
        self.deprepemail = deprepemail

class EmailSender:
    def __init__(self):
        self.ses_client = boto3.client(
            'ses',
            region_name=AWS_REGION,
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
        )

    def send_email(self, recipient: str, subject: str, html_body: str, text_body: str) -> bool:
        if not recipient:
            logger.error("No recipient specified")
            return False

        try:
            response = self.ses_client.send_email(
                Source=SENDER_EMAIL,
                Destination={'ToAddresses': [recipient]},
                Message={
                    'Subject': {'Data': subject},
                    'Body': {
                        'Html': {'Data': html_body},
                        'Text': {'Data': text_body}
                    }
                }
            )
            logger.info(f"Email successfully sent to {recipient}")
            return True
        except ClientError as e:
            logger.error(f"AWS SES Error sending to {recipient}: {e.response['Error']['Message']}")
        except Exception as e:
            logger.error(f"Unexpected error sending to {recipient}: {str(e)}")
        return False

class DatabaseManager:
    def __init__(self):
        self.conn = psycopg2.connect(**DB_CONFIG)
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.conn.close()
    
    def get_unallocated_students(self) -> List[UnAllocatedStudent]:
        """Get list of students without verifiers"""
        query = """
            SELECT id, name, email, role, "verifierEmail", deptcode, batch, enrollmentno, userstatus 
            FROM public."User" 
            WHERE "verifierEmail" IS NULL AND role = 'student'
        """
        with self.conn.cursor() as cursor:
            cursor.execute(query)
            return [
                UnAllocatedStudent(*row) for row in cursor.fetchall()
            ]
    
    def get_departments(self) -> List[Department]:
        """Get department information"""
        query = "SELECT deptcode, deprepemail FROM public.\"Departments\""
        with self.conn.cursor() as cursor:
            cursor.execute(query)
            return [Department(*row) for row in cursor.fetchall()]

def generate_student_tables(students: List[UnAllocatedStudent]) -> Tuple[str, str]:
    """Generate HTML tables for pending approval and verifier allocation"""
    
    # Pending Approval table
    pending_approval = """
    <table border="1" style="border-collapse: collapse; width: 100%; margin-bottom: 20px;">
        <thead>
            <tr style="background-color: #f2f2f2;">
                <th style="padding: 8px;">Name</th>
                <th style="padding: 8px;">Email</th>
                <th style="padding: 8px;">Enrollment No</th>
                <th style="padding: 8px;">Department</th>
                <th style="padding: 8px;">Status</th>
                <th style="padding: 8px;">Verifier</th>
            </tr>
        </thead>
        <tbody>
    """
    
    # Pending Verifier Allocation table
    pending_allocation = """
    <table border="1" style="border-collapse: collapse; width: 100%;">
        <thead>
            <tr style="background-color: #f2f2f2;">
                <th style="padding: 8px;">Name</th>
                <th style="padding: 8px;">Email</th>
                <th style="padding: 8px;">Enrollment No</th>
                <th style="padding: 8px;">Department</th>
                <th style="padding: 8px;">Status</th>
                <th style="padding: 8px;">Batch</th>
                <th style="padding: 8px;">Verifier</th>
            </tr>
        </thead>
        <tbody>
    """
    
    for student in students:
        if student.userstatus == "pending":
            pending_approval += f"""
            <tr>
                <td style="padding: 8px;">{student.name}</td>
                <td style="padding: 8px;">{student.email}</td>
                <td style="padding: 8px;">{student.enrollmentno}</td>
                <td style="padding: 8px;">{student.deptcode}</td>
                <td style="padding: 8px;">{student.userstatus}</td>
                <td style="padding: 8px;">{student.verifierEmail or 'None'}</td>
            </tr>
            """
        
        if not student.verifierEmail and student.userstatus == "verified":
            pending_allocation += f"""
            <tr>
                <td style="padding: 8px;">{student.name}</td>
                <td style="padding: 8px;">{student.email}</td>
                <td style="padding: 8px;">{student.enrollmentno}</td>
                <td style="padding: 8px;">{student.deptcode}</td>
                <td style="padding: 8px;">{student.userstatus}</td>
                <td style="padding: 8px;">{student.batch}</td>
                <td style="padding: 8px;">{student.verifierEmail or 'None'}</td>
            </tr>
            """
    
    pending_approval += "</tbody></table>"
    pending_allocation += "</tbody></table>"
    
    return pending_approval, pending_allocation

def create_email_content(deptcode: str, count: int, 
                        pending_approval: str, pending_allocation: str) -> Tuple[str, str]:
    """Generate both HTML and plain text email content"""
    
    subject = f"Notification: Unallocated Students in {deptcode}"
    
    text_body = f"""
Dear {deptcode} Department Representative,

This is to inform you that there are {count} students in your department ({deptcode}) who are unallocated.

Please review the following students who require attention:
1. Students pending approval
2. Students pending verifier allocation

Please take the necessary actions at your earliest convenience.

Go to Dashboard: https://ihundred.scet.ac.in/dashboard

Best regards,
100 Points Activity Team
    """
    
    html_body = f"""
<!DOCTYPE html>
<html>
<head>
  <style>
    body {{
      font-family: Arial, sans-serif;
      line-height: 1.6;
      color: #333;
      margin: 0;
      padding: 20px;
      background-color: #f9f9f9;
    }}
    .email-container {{
      max-width: 600px;
      margin: 0 auto;
      padding: 20px;
      background-color: #ffffff;
      border: 1px solid #ddd;
      border-radius: 8px;
      box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    }}
    h1 {{
      color: #2c3e50;
      font-size: 24px;
      margin-bottom: 20px;
    }}
    h2 {{
      color: #34495e;
      font-size: 20px;
      margin-top: 30px;
      margin-bottom: 10px;
    }}
    .button {{
      display: inline-block;
      padding: 10px 20px;
      background-color: #3498db;
      color: white;
      text-decoration: none;
      border-radius: 4px;
      margin-top: 20px;
    }}
    .footer {{
      margin-top: 30px;
      font-size: 14px;
      color: #777;
      text-align: center;
    }}
  </style>
</head>
<body>
  <div class="email-container">
    <h1>Notification: Pending Student Actions</h1>
    <p>Dear Department Representative,</p>
    <p>This is a notification regarding <strong>{count} students</strong> in your department ({deptcode}) who require your attention.</p>

    <h2>Pending Approval</h2>
    {pending_approval}

    <h2>Pending Verifier Allocation</h2>
    {pending_allocation}

    <p>Please take the necessary actions at your earliest convenience.</p>

    <a href="https://ihundred.scet.ac.in/dashboard" class="button">Go to Dashboard</a>

    <div class="footer">
      <p>Best regards,</p>
      <p><strong>100 Points Activity Team</strong></p>
      <p><em>This is an automated email. Please do not reply.</em></p>
    </div>
  </div>
</body>
</html>
    """
    
    return subject, text_body, html_body

def send_unallocated_student_notifications():
    """Main function to send notifications about unallocated students"""
    email_sender = EmailSender()
    
    with DatabaseManager() as db:
        # Get all required data
        students = db.get_unallocated_students()
        departments = db.get_departments()
        
        if not students:
            logger.info("No unallocated students found")
            return
        
        # Group students by department
        dept_students: Dict[str, List[UnAllocatedStudent]] = {}
        for student in students:
            if student.deptcode not in dept_students:
                dept_students[student.deptcode] = []
            dept_students[student.deptcode].append(student)
        
        # Create department email mapping
        dept_emails = {dept.deptcode: dept.deprepemail for dept in departments}
        
        # Process each department
        for deptcode, students in dept_students.items():
            if not students:
                continue
                
            rep_email = dept_emails.get(deptcode)
            if not rep_email:
                logger.warning(f"No representative email found for department {deptcode}")
                continue
            
            # Generate email content
            pending_approval, pending_allocation = generate_student_tables(students)
            subject, text_body, html_body = create_email_content(
                deptcode, len(students), pending_approval, pending_allocation
            )
            
            # Send email
            if email_sender.send_email(rep_email, subject, html_body, text_body):
                logger.info(f"Sent notification to {rep_email} for {len(students)} unallocated students in {deptcode}")
            else:
                logger.error(f"Failed to send notification to {rep_email}")

if __name__ == "__main__":
    send_unallocated_student_notifications()