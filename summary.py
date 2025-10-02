import os
import psycopg2
from dotenv import load_dotenv
import boto3
from botocore.exceptions import ClientError
from logger_config import get_logger
from typing import List, Dict, Tuple

# Load environment variables
load_dotenv()

# Configure logging
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

class EmailSender:
    def __init__(self):
        self.ses_client = boto3.client(
            'ses',
            region_name=AWS_REGION,
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
        )
    
    def send_email(self, recipients: List[str], subject: str, html_body: str) -> bool:
        # cleaned_recipients = [email.strip() for email in recipients if email.strip()]
        cleaned_recipients = ['tushar.gohil@scet.ac.in','100activitypoints@scet.ac.in']
        try:
            response = self.ses_client.send_email(
                Source=SENDER_EMAIL,
                Destination={'ToAddresses': cleaned_recipients},
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
            logger.error(f"Failed to send email: {e.response['Error']['Message']}")
            return False

class DatabaseManager:
    def __init__(self):
        self.conn = psycopg2.connect(**DB_CONFIG)
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.conn.close()
    
    def get_summary_report(self) -> List[Dict]:
        """Get summary report data excluding ASH and DET departments"""
        query = """
            SELECT * FROM public."AdminSummary" 
            WHERE deptcode NOT IN ('ASH','DET') 
            AND batch IS NOT NULL 
            AND batch != '2020-2021' 
            AND batch != '2021-2022'
            ORDER BY batch, deptcode
        """
        with self.conn.cursor() as cursor:
            cursor.execute(query)
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    def get_final_year_batch(self) -> str:
        """Get the current final year batch"""
        query = """SELECT batch FROM public."Batches" WHERE "IsFinalYear" = 'Yes'"""
        with self.conn.cursor() as cursor:
            cursor.execute(query)
            return cursor.fetchone()[0]
    
    def get_departments(self) -> List[Dict]:
        """Get department information with HOD and representative emails"""
        query = """SELECT deptcode, deprepemail, hodemail FROM public."Departments\""""
        with self.conn.cursor() as cursor:
            cursor.execute(query)
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    def get_verifier_performance(self) -> List[Dict]:
        """Get verifier performance statistics from VerifierStastics table"""
        query = """
            SELECT 
                "verifierEmail",
                total_activities,
                pending_count,
                avg_pending_days,
                max_pending_days,
                performance_status
            FROM public."VerifierStastics"
            ORDER BY pending_count DESC
        """
        with self.conn.cursor() as cursor:
            cursor.execute(query)
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
    

def generate_summary_table(data: List[Dict], final_year_batch: str) -> str:
    """Generate HTML table for summary report"""
    table = """
    <table border="1" cellpadding="5" cellspacing="0" style="border-collapse: collapse; width: 100%; margin-bottom: 20px;">
        <thead>
            <tr style="background-color: #3498db; color: white;">
                <th>Department</th>
                <th>Batch</th>
                <th>Registered</th>
                <th>≥100</th>
                <th>≥75</th>
                <th>≥50</th>
                <th>&lt;50</th>
            </tr>
        </thead>
        <tbody>
    """
    
    for item in data:
        registered = item['gte100'] + item['gte75'] + item['gte50'] + item['lt50']
        highlight = 'background-color: yellow;' if item['batch'] == final_year_batch and item['lt50'] > 0 else ''
        
        table += f"""
        <tr>
            <td>{item['deptcode']}</td>
            <td>{item['batch']}</td>
            <td>{registered}</td>
            <td>{item['gte100']}</td>
            <td>{item['gte75']}</td>
            <td>{item['gte50']}</td>
            <td style="{highlight}">{item['lt50']}</td>
        </tr>
        """
    
    table += """
        </tbody>
    </table>
    """
    return table

def generate_verifier_table(data: List[Dict]) -> str:
    """Generate HTML table for verifier performance"""
    table = """
    <table border="1" cellpadding="5" cellspacing="0" style="border-collapse: collapse; width: 100%; margin-top: 30px;">
        <thead>
            <tr style="background-color: #3498db; color: white;">
                <th>Verifier Email</th>
                <th>Total Activities</th>
                <th>Pending Activities</th>
                <th>Avg Pending Days</th>
                <th>Max Pending Days</th>
                <th>Remarks</th>
            </tr>
        </thead>
        <tbody>
    """
    
    for item in data:
        table += f"""
        <tr>
            <td style="text-align: left; font-weight: bold;">{item['verifierEmail']}</td>
            <td style="text-align: center; font-weight: bold;">{item['total_activities']}</td>
            <td style="text-align: center; font-weight: bold;">{item['pending_count']}</td>
            <td style="text-align: center; font-weight: bold;">{round(item['avg_pending_days'], 1)}</td>
            <td style="text-align: center; font-weight: bold;">{round(item['max_pending_days'], 1)}</td>
            <td style="text-align: center; font-weight: bold;">{item['performance_status']}</td>
        </tr>
        """
    
    table += """
        </tbody>
    </table>
    """
    return table

def generate_email_content(summary_table: str, verifier_table: str) -> Tuple[str, str]:
    """Generate email subject and HTML content"""
    subject = "Current Status of 100 Points Activity @ SCET"
    
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>100 Points Activity Report</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            margin: 0;
            padding: 20px;
        }}
        .email-container {{
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            border: 1px solid #ddd;
            border-radius: 8px;
            background-color: #f9f9f9;
        }}
        h1 {{
            color: #2c3e50;
            text-align: center;
        }}
        h2 {{
            color: #34495e;
            margin-top: 30px;
            border-bottom: 2px solid #3498db;
            padding-bottom: 5px;
        }}
        .note {{
            font-style: italic;
            color: #666;
            margin: 10px 0;
        }}
        .footer {{
            margin-top: 30px;
            padding-top: 10px;
            border-top: 1px solid #ddd;
            text-align: center;
            font-size: 14px;
            color: #777;
        }}
    </style>
</head>
<body>
    <div class="email-container">
        <h1>100 Points Activity Status Report</h1>
        
        <h2>Student Points Summary</h2>
        {summary_table}
        <p class="note">Note: Yellow highlights indicate students with less than 50 points in the final year batch.</p>
        
        <h2>Verifier Performance</h2>
        {verifier_table}
        <p class="note">Note: This report shows verifiers with their pending activity counts and processing times.</p>
        
        <div class="footer">
            <p>This is an automated email. Please do not reply.</p>
            <p>100 Points Activity Team | Sarvajanik College of Engineering and Technology</p>
        </div>
    </div>
</body>
</html>
    """
    
    return subject, html

def send_summary_report():
    """Main function to generate and send the summary report"""
    email_sender = EmailSender()
    
    with DatabaseManager() as db:
        try:
            # Get all required data
            summary_data = db.get_summary_report()
            final_year_batch = db.get_final_year_batch()
            departments = db.get_departments()
            verifier_data = db.get_verifier_performance()
            
            # List of verifiers to whom emails should not be sent
            excluded_verifiers = [
                'foram.patel@scet.ac.in',
                'rakesh.patelco@scet.ac.in',
                'sudhir.yardi@scet.ac.in',
                'bhargavi.rani@scet.ac.in',
                'juhi.mehta@scet.ac.in',
                'bijal.mehta@scet.ac.in'
            ]

            # Filter out excluded verifiers from the verifier data
            verifier_data = [verifier for verifier in verifier_data if verifier['verifierEmail'] not in excluded_verifiers]
           
            # Remove blank entries from verifier data
            verifier_data = [verifier for verifier in verifier_data if verifier['verifierEmail'] and all(verifier.values())]

            # Generate tables
            summary_table = generate_summary_table(summary_data, final_year_batch)
            verifier_table = generate_verifier_table(verifier_data)
            
            # Create email content
            subject, html_body = generate_email_content(summary_table, verifier_table)
            
            # Prepare recipient list
            recipients = set()
            for dept in departments:
                if dept['deprepemail']:
                    recipients.add(dept['deprepemail'])
                if dept['hodemail']:
                    recipients.add(dept['hodemail'])
            
            # Add additional recipients
            additional_recipients = [
                'dean-academic@scet.ac.in',
                'principal@scet.ac.in',
                'tushar.gohil@scet.ac.in'
            ]
            recipients.update(additional_recipients)

            # Add verifier emails to recipients
            for verifier in verifier_data:
                recipients.add(verifier['verifierEmail'])
            
            # Send email
            if len(recipients) > 10:
                recipient_chunks = [list(recipients)[i:i + 10] for i in range(0, len(recipients), 10)]
                for chunk in recipient_chunks:
                    if email_sender.send_email(chunk, subject, html_body):
                        logger.info(f"Monthly summary report sent successfully to chunk: {chunk}")
                    else:
                        logger.error(f"Failed to send monthly summary report to chunk: {chunk}")
            else:
                if email_sender.send_email(list(recipients), subject, html_body):
                    logger.info("Monthly summary report sent successfully")
                else:
                    logger.error("Failed to send monthly summary report")
                
        except Exception as e:
            logger.error(f"Error generating report: {str(e)}")
            raise

if __name__ == "__main__":
    logger.info("Monthly Summary Report : Scheduled Script Started Running...")
    send_summary_report()
    logger.info("Monthly Summary Report : Scheduled Script Ended...")