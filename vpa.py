import os
from dotenv import load_dotenv  # Add this import
from typing import List, Dict, Optional
import psycopg2
from psycopg2 import sql as psql
import boto3
from logger_config import get_logger

load_dotenv()  # Add this line before accessing any environment variables

# Set up logging
logger = get_logger()

# Database configuration
DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "database": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "port": os.getenv("DB_PORT", "5432"),
}

# AWS SES configuration
AWS_REGION = os.getenv("AWS_REGION")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
SENDER_EMAIL = "IHundred Admin <100activitypoints@scet.ac.in>"

class VerifiersPendingCount:
    def __init__(self, verifierEmail: str, pendingActivitiesCount: int):
        self.verifierEmail = verifierEmail
        self.pendingActivitiesCount = pendingActivitiesCount

class VerifierStatistics:
    def __init__(self, verifierEmail: str, total_activities: int, 
        pending_activities: int,
                 avg_pending_days: float, max_pending_days: int):
        self.verifierEmail = verifierEmail
        self.total_activities = total_activities
        self.pending_activities = pending_activities
        self.avg_pending_days = avg_pending_days
        self.max_pending_days = max_pending_days

def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)

def send_email(recipient: str, subject: str, html_body: str) -> bool:
    ses_client = boto3.client(
        'ses',
        region_name=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY
    )
    
    try:
        # response = ses_client.send_email(
        #     Source=SENDER_EMAIL,
        #     Destination={'ToAddresses': [recipient]},
        #     Message={
        #         'Subject': {'Data': subject},
        #         'Body': {
        #             'Html': {'Data': html_body},
        #             'Text': {'Data': "Please view this email in an HTML-enabled client."}
        #         }
        #     }
        # )
        logger.info(f"Email sent to {recipient}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {recipient}: {str(e)}")
        return False

def get_verifiers_with_pending_activities() -> List[VerifiersPendingCount]:
    query = """
        SELECT public."User"."verifierEmail", COUNT(*) as "pendingActivitiesCount"
        FROM public."User"
        JOIN public."Activity" ON public."User".email = public."Activity"."ownerEmail" 
        WHERE status = 'Pending' 
        AND userstatus = 'verified' 
        AND public."User"."verifierEmail" IS NOT NULL 
        GROUP BY public."User"."verifierEmail"
    """
    
    verifiers = []
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query)
            for row in cursor.fetchall():
                verifiers.append(VerifiersPendingCount(row[0], row[1]))
    return verifiers

def get_verifiers_statistics() -> Dict[str, VerifierStatistics]:
    query = "SELECT * FROM public.\"VerifierStastics\""
    stats = {}
    
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query)
            for row in cursor.fetchall():
                stats[row[0]] = VerifierStatistics(row[0], row[1], row[2], row[3], row[4])
    return stats

def create_email_content(verifier: VerifiersPendingCount, stats: Optional[VerifierStatistics]) -> str:
    return f"""
    <html>
        <head>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    background-color: #f4f4f4;
                    color: #333;
                    margin: 0;
                    padding: 0;
                }}
                .container {{
                    max-width: 600px;
                    margin: 20px auto;
                    padding: 20px;
                    background-color: #fff;
                    border-radius: 8px;
                    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
                }}
                .footer-note {{
                    font-size: 12px;
                    color: #888;
                    font-style: italic;
                    margin-top: 20px;
                    border-top: 1px solid #eee;
                    padding-top: 10px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Pending Activities Notification</h1>
                <p>Hello, {verifier.verifierEmail}</p>
                <p>You have <strong>{verifier.pendingActivitiesCount}</strong> pending activities that require your attention.</p>
                <p>Please review them at your earliest convenience to ensure timely processing.</p>
                <p><a href="https://ihundred.scet.ac.in">Go to Portal</a></p>

                <h2>Your Statistics:</h2>
                <table style="width: 100%; border-collapse: collapse; margin: 15px 0;">
                    <tr style="background-color: #f2f2f2;">
                        <th style="padding: 10px; border: 1px solid #ddd;">Total Activities</th>
                        <th style="padding: 10px; border: 1px solid #ddd;">Pending Activities</th>
                        <th style="padding: 10px; border: 1px solid #ddd;">Avg Pending Days</th>
                        <th style="padding: 10px; border: 1px solid #ddd;">Max Pending Days</th>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border: 1px solid #ddd; text-align: center;">{stats.total_activities if stats else 'N/A'}</td>
                        <td style="padding: 10px; border: 1px solid #ddd; text-align: center;">{verifier.pendingActivitiesCount}</td>
                        <td style="padding: 10px; border: 1px solid #ddd; text-align: center;">{round(stats.avg_pending_days) if stats else 'N/A'}</td>
                        <td style="padding: 10px; border: 1px solid #ddd; text-align: center;">{round(stats.max_pending_days) if stats else 'N/A'}</td>
                    </tr>
                </table>

                <h2>Performance Status:</h2>
                <table style="width: 100%; border-collapse: collapse; margin: 15px 0;">
                    <tr style="background-color: #f2f2f2;">
                        <th style="padding: 10px; border: 1px solid #ddd;">Performance Status</th>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border: 1px solid #ddd; text-align: center;">
                            {(
                                'CRITICAL - Low volume, high delay' if stats and stats.total_activities < 5 and stats.avg_pending_days > 7 else
                                'High Risk - Few activities, long delays' if stats and stats.total_activities < 10 and stats.avg_pending_days > 5 else
                                'High Delay - Regardless of volume' if stats and stats.avg_pending_days > 10 else
                                'Inefficient Processing' if stats and stats.avg_pending_days / (stats.total_activities or 1) > 1 else
                                'Within Expected Range'
                            )}
                        </td>
                    </tr>
                </table>

                <div class="footer-note">
                    <p>This is an automated email. Please do not reply.</p>
                    <p>100 Points Activity Team, Sarvajanik College of Engineering and Technology</p>
                </div>
            </div>
        </body>
    </html>
    """

def send_pending_notifications():
    verifiers = get_verifiers_with_pending_activities()
    if not verifiers:
        logger.info("No verifiers with pending activities found")
        return

    stats_map = get_verifiers_statistics()
    
    for verifier in verifiers:
        print(verifier.verifierEmail, verifier.pendingActivitiesCount)
        # Uncomment the following line to print statistics for each verifier
        stats = stats_map.get(verifier.verifierEmail)
        # if stats:
        #     print(stats.verifierEmail, stats.total_activities, stats.pending_activities, stats.avg_pending_days, stats.max_pending_days)
        email_content = create_email_content(verifier, stats)
        # print(email_content)
        
        if send_email(
            recipient=verifier.verifierEmail,
            subject="⚠️ Urgent: Pending Activities Require Your Attention!",
            html_body=email_content.replace(
            "<strong>", "<strong style='color: red;'>"
            )
        ):
            logger.info(f"Notification sent to {verifier.verifierEmail} with {verifier.pendingActivitiesCount} pending activities")
        else:
            logger.error(f"Failed to send notification to {verifier.verifierEmail}")

if __name__ == "__main__":
    logger.info("Notifications to verifiers regarding Pending Activities to verify: Scheduled Script Started Running...")
    send_pending_notifications()
    logger.info("Notifications to verifiers regarding Pending Activities to verify: Scheduled Script Ended...")