#!/bin/bash

# Configuration
DB_PATH="/opt/german_ai_tutor/backend/data/app.db"
BACKUP_DIR="/opt/german_ai_tutor/backend/data/backups"
RETENTION_COUNT=7 # Keep the last 7 backups

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Generate timestamp for the backup file
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="$BACKUP_DIR/app_db_backup_$TIMESTAMP.db"

# Perform the backup
cp "$DB_PATH" "$BACKUP_FILE"

# Check if backup was successful
if [ $? -eq 0 ]; then
  echo "$(date +"%Y-%m-%d %H:%M:%S") - Backup successful: $BACKUP_FILE"
else
  echo "$(date +"%Y-%m-%d %H:%M:%S") - Backup failed for $DB_PATH"
  exit 1
fi

# Rotate old backups (keep the newest RETENTION_COUNT files)
# ls -t sorts by modification time (newest first). tail -n +X skips the first X-1 lines.
OLD_BACKUPS=$(ls -t "$BACKUP_DIR"/app_db_backup_*.db 2>/dev/null | tail -n +$((RETENTION_COUNT + 1)))
if [ -n "$OLD_BACKUPS" ]; then
 echo "$(date +"%Y-%m-%d %H:%M:%S") - Removing old backups:"
 for old_backup in $OLD_BACKUPS; do
   rm "$old_backup"
   echo "$(date +"%Y-%m-%d %H:%M:%S") -   Removed: $old_backup"
 done
else
 echo "$(date +"%Y-%m-%d %H:%M:%S") - No old backups to remove."
fi

echo "$(date +"%Y-%m-%d %H:%M:%S") - Backup and rotation complete."