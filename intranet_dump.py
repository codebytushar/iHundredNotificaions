import os
import subprocess
import datetime
from pathlib import Path

# Environment Variables or inline (you can replace with secrets/environment in GitHub Actions)
DB_HOST = os.getenv("DB_HOST", "ep-damp-term-487147.us-east-1.aws.neon.tech")
DB_PORT = os.getenv("DB_PORT", "5432")
INTRANET_DB_NAME = os.getenv("INTRANET_DB_NAME", "intranet")
DB_USER = os.getenv("DB_USER", "goheltushar")
DB_PASSWORD = os.getenv("DB_PASSWORD", "your_password_here")
BACKUP_DIR = os.getenv("BACKUP_DIR", "/home/ihundred/backups")

STORAGE_ACCOUNT = os.getenv("AZURE_STORAGE_ACCOUNT", "ihundredbackups")
INTRANET_AZURE_STORAGE_CONTAINER = os.getenv("INTRANET_AZURE_STORAGE_CONTAINER", "intranetdbs")
INTRANET_AZURE_SAS_TOKEN = os.getenv("INTRANET_AZURE_SAS_TOKEN", "your_sas_token_here")

# Prepare backup file
timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
backup_file = Path(BACKUP_DIR) / f"backup_{timestamp}.sql"

# Ensure backup directory exists
Path(BACKUP_DIR).mkdir(parents=True, exist_ok=True)

# Export PGPASSWORD
env = os.environ.copy()
env["PGPASSWORD"] = DB_PASSWORD

# Perform pg_dump
print(f"Starting backup of database '{INTRANET_DB_NAME}' to {backup_file}...")
dump_cmd = [
    "pg_dump",
    "-h", DB_HOST,
    "-U", DB_USER,
    "-p", DB_PORT,
    "-F", "c",  # Custom format
    "-b",
    "-v",
    "-f", str(backup_file),
    INTRANET_DB_NAME
]

result = subprocess.run(dump_cmd, env=env)

if result.returncode == 0:
    print("Backup completed successfully. Uploading to Azure Blob Storage...")

    azcopy_cmd = [
        "azcopy",
        "copy",
        str(backup_file),
        f"https://{STORAGE_ACCOUNT}.blob.core.windows.net/{INTRANET_AZURE_STORAGE_CONTAINER}/{backup_file.name}?{INTRANET_AZURE_SAS_TOKEN}"
    ]

    subprocess.run(azcopy_cmd)
else:
    print("Backup failed.")
    exit(1)

# Cleanup old files older than 30 days
print("Cleaning up backups older than 30 days...")
now = datetime.datetime.now()
for file in Path(BACKUP_DIR).glob("*.sql"):
    if (now - datetime.datetime.fromtimestamp(file.stat().st_mtime)).days > 30:
        file.unlink()
        print(f"Deleted old backup: {file}")
