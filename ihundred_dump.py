import os
import subprocess
import datetime
import shutil
from pathlib import Path

# Environment Variables (can also be fetched from GitHub secrets)
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
BACKUP_DIR = os.getenv("BACKUP_DIR", "/backups")

STORAGE_ACCOUNT = os.getenv("AZURE_STORAGE_ACCOUNT")
STORAGE_CONTAINER = os.getenv("AZURE_STORAGE_CONTAINER")
SAS_TOKEN = os.getenv("AZURE_SAS_TOKEN")

# Prepare backup file path
timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
backup_file = Path(BACKUP_DIR) / f"backup_{timestamp}.sql"

# Ensure backup directory exists
Path(BACKUP_DIR).mkdir(parents=True, exist_ok=True)

# Export password for pg_dump
env = os.environ.copy()
env["PGPASSWORD"] = DB_PASSWORD

# Run pg_dump
print(f"Backing up database to {backup_file}...")
dump_command = [
    "pg_dump",
    "-h", DB_HOST,
    "-U", DB_USER,
    "-p", DB_PORT,
    "-F", "c",  # Custom format
    "-b",
    "-v",
    "-f", str(backup_file),
    DB_NAME
]

result = subprocess.run(dump_command, env=env)

if result.returncode == 0:
    print("Backup completed successfully. Uploading to Azure Storage...")

    azcopy_command = [
        "azcopy",
        "copy",
        str(backup_file),
        f"https://{STORAGE_ACCOUNT}.blob.core.windows.net/{STORAGE_CONTAINER}/{backup_file.name}?{SAS_TOKEN}"
    ]

    subprocess.run(azcopy_command)
else:
    print("Backup failed.")
    exit(1)

# Optional: Clean up files older than 30 days
print("Cleaning up old backups...")
now = datetime.datetime.now()
for file in Path(BACKUP_DIR).glob("*.sql"):
    if (now - datetime.datetime.fromtimestamp(file.stat().st_mtime)).days > 30:
        file.unlink()
        print(f"Deleted old backup: {file}")
