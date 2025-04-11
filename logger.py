# logger_config.py
import os
from dotenv import load_dotenv
from datetime import datetime
import logging
import boto3
from botocore.exceptions import ClientError, BotoCoreError
import watchtower  # Python CloudWatch logging handler
from logger import get_logger

logger = get_logger()

load_dotenv()

class CloudWatchFormatter(logging.Formatter):
    """Custom formatter to match your desired format"""
    def format(self, record):
        timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')
        return f"{timestamp} [{record.levelname}]: {record.getMessage()}"

def get_logger(name='ActivityPortal'):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # Avoid adding handlers multiple times
    if logger.hasHandlers():
        return logger

    formatter = CloudWatchFormatter()

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # CloudWatch handler if AWS credentials are present
    if all(os.getenv(var) for var in ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_REGION']):
        try:
            cloudwatch_handler = watchtower.CloudWatchLogHandler(
                log_group='ActivityPortalLogs',
                stream_name='ServerLogs',
                boto3_client=boto3.client(
                    'logs',
                    region_name=os.getenv('AWS_REGION'),
                    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
                )
            )
            cloudwatch_handler.setFormatter(formatter)
            logger.addHandler(cloudwatch_handler)
        except (ClientError, BotoCoreError) as e:
            logger.error(f"Failed to initialize CloudWatch logging: {str(e)}")

    return logger
