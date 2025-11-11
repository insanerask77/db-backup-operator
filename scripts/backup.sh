#!/bin/bash

set -e
set -o pipefail

CONFIG_FILE="/config/config.yaml"
TARGET_DB_NAME=$1

# Check if the configuration file exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: Configuration file not found at $CONFIG_FILE"
    exit 1
fi

BACKUP_DIR=$(yq e '.global.backup_path' $CONFIG_FILE)

# Function to apply retention policy
apply_retention_policy() {
    local DB_NAME=$1
    local KEEP_LAST=$2
    local KEEP_DAYS=$3

    echo "Applying retention policy for database: $DB_NAME"

    if [ -n "$KEEP_LAST" ] && [ "$KEEP_LAST" -gt 0 ]; then
        echo "Keeping the last $KEEP_LAST backups..."
        # List files in reverse chronological order, skip the first N, and delete the rest
        REMOVABLE_FILES=$(ls -1t ${BACKUP_DIR}/${DB_NAME}_* | tail -n +$(($KEEP_LAST + 1)))
        for FILE in $REMOVABLE_FILES; do
            if [ -f "$FILE" ]; then
                echo "Deleting old backup: $FILE"
                rm "$FILE"
                if [ -f "${FILE}.md5" ]; then
                    echo "Deleting checksum: ${FILE}.md5"
                    rm "${FILE}.md5"
                fi
            fi
        done
    elif [ -n "$KEEP_DAYS" ] && [ "$KEEP_DAYS" -gt 0 ]; then
        echo "Keeping backups for the last $KEEP_DAYS days..."
        find "$BACKUP_DIR" -name "${DB_NAME}_*" -mtime +$((KEEP_DAYS - 1)) -print -exec rm {} \;
        find "$BACKUP_DIR" -name "${DB_NAME}_*.md5" -mtime +$((KEEP_DAYS - 1)) -print -exec rm {} \;
    else
        echo "No retention policy specified for $DB_NAME. Skipping cleanup."
    fi
}

# Function to perform a backup for a specific database
perform_backup() {
    local DB_NAME=$1
    local DB_TYPE=$2
    local DB_HOST=$3
    local DB_PORT=$4
    local DB_USER=$5
    local DB_PASS=$6
    local DB_DBNAME=$7
    local DB_COMPRESSION=$8

    TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
    BACKUP_FILENAME_BASE="${DB_NAME}_${TIMESTAMP}"

    local BACKUP_FILE_PATH=""
    local DUMP_CMD=""
    local EXT=""

    echo "----------------------------------------"
    echo "Backing up database: $DB_NAME ($DB_TYPE)"
    echo "Compression method: $DB_COMPRESSION"

    # Set up dump command and file extension based on DB type
    if [ "$DB_TYPE" == "postgres" ]; then
        export PGPASSWORD=$DB_PASS
        DUMP_CMD="pg_dump -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_DBNAME"
        EXT=".sql"
    elif [ "$DB_TYPE" == "mongodb" ]; then
        DUMP_CMD="mongodump --host $DB_HOST --port $DB_PORT -u $DB_USER -p \"$DB_PASS\" --db $DB_DBNAME --archive --quiet"
        EXT=".archive"
    else
        echo "Error: Unsupported database type '$DB_TYPE' for database '$DB_NAME'"
        return 1
    fi

    # Apply compression
    case "$DB_COMPRESSION" in
        "gz")
            BACKUP_FILE_PATH="${BACKUP_DIR}/${BACKUP_FILENAME_BASE}${EXT}.gz"
            $DUMP_CMD | gzip > "$BACKUP_FILE_PATH"
            ;;
        "zip")
            BACKUP_FILE_PATH="${BACKUP_DIR}/${BACKUP_FILENAME_BASE}${EXT}.zip"
            $DUMP_CMD | zip -q - - > "$BACKUP_FILE_PATH"
            ;;
        "none")
            BACKUP_FILE_PATH="${BACKUP_DIR}/${BACKUP_FILENAME_BASE}${EXT}"
            $DUMP_CMD > "$BACKUP_FILE_PATH"
            ;;
        *)
            echo "Error: Unsupported compression type '$DB_COMPRESSION'. Defaulting to gzip."
            BACKUP_FILE_PATH="${BACKUP_DIR}/${BACKUP_FILENAME_BASE}${EXT}.gz"
            $DUMP_CMD | gzip > "$BACKUP_FILE_PATH"
            ;;
    esac

    # Unset password for security
    if [ "$DB_TYPE" == "postgres" ]; then
        unset PGPASSWORD
    fi

    if [ $? -eq 0 ]; then
        echo "Backup for $DB_NAME created successfully at $BACKUP_FILE_PATH"
        md5sum "$BACKUP_FILE_PATH" > "${BACKUP_FILE_PATH}.md5"
        echo "MD5 Checksum:"
        cat "${BACKUP_FILE_PATH}.md5"
        return 0
    else
        echo "Error: Backup failed for database $DB_NAME"
        return 1
    fi
}

# Main script logic
echo "Starting backup process..."

if [ -n "$TARGET_DB_NAME" ]; then
    # Backup a specific database
    DB_INDEX=$(yq e ".databases[] | select(.name == \"$TARGET_DB_NAME\") | key" $CONFIG_FILE)
    if [ -z "$DB_INDEX" ]; then
        echo "Error: Database '$TARGET_DB_NAME' not found in configuration file."
        exit 1
    fi

    DB_TYPE=$(yq e ".databases[$DB_INDEX].type" $CONFIG_FILE)
    DB_HOST=$(yq e ".databases[$DB_INDEX].host" $CONFIG_FILE)
    DB_PORT=$(yq e ".databases[$DB_INDEX].port" $CONFIG_FILE)
    DB_USER=$(yq e ".databases[$DB_INDEX].user" $CONFIG_FILE)
    DB_PASS=$(yq e ".databases[$DB_INDEX].password" $CONFIG_FILE)
    DB_DBNAME=$(yq e ".databases[$DB_INDEX].dbname" $CONFIG_FILE)
    DB_COMPRESSION=$(yq e ".databases[$DB_INDEX].compression // \"gz\"" $CONFIG_FILE)
    KEEP_LAST=$(yq e ".databases[$DB_INDEX].retention.keep_last // \"\"" $CONFIG_FILE)
    KEEP_DAYS=$(yq e ".databases[$DB_INDEX].retention.keep_days // \"\"" $CONFIG_FILE)

    perform_backup "$TARGET_DB_NAME" "$DB_TYPE" "$DB_HOST" "$DB_PORT" "$DB_USER" "$DB_PASS" "$DB_DBNAME" "$DB_COMPRESSION"
    if [ $? -eq 0 ]; then
        apply_retention_policy "$TARGET_DB_NAME" "$KEEP_LAST" "$KEEP_DAYS"
    fi
else
    # Backup all databases
    DATABASES_COUNT=$(yq e '.databases | length' $CONFIG_FILE)
    for i in $(seq 0 $(($DATABASES_COUNT - 1))); do
        DB_NAME=$(yq e ".databases[$i].name" $CONFIG_FILE)
        DB_TYPE=$(yq e ".databases[$i].type" $CONFIG_FILE)
        DB_HOST=$(yq e ".databases[$i].host" $CONFIG_FILE)
        DB_PORT=$(yq e ".databases[$i].port" $CONFIG_FILE)
        DB_USER=$(yq e ".databases[$i].user" $CONFIG_FILE)
        DB_PASS=$(yq e ".databases[$i].password" $CONFIG_FILE)
        DB_DBNAME=$(yq e ".databases[$i].dbname" $CONFIG_FILE)
        DB_COMPRESSION=$(yq e ".databases[$i].compression // \"gz\"" $CONFIG_FILE)
        KEEP_LAST=$(yq e ".databases[$i].retention.keep_last // \"\"" $CONFIG_FILE)
        KEEP_DAYS=$(yq e ".databases[$i].retention.keep_days // \"\"" $CONFIG_FILE)

        perform_backup "$DB_NAME" "$DB_TYPE" "$DB_HOST" "$DB_PORT" "$DB_USER" "$DB_PASS" "$DB_DBNAME" "$DB_COMPRESSION"
        if [ $? -eq 0 ]; then
            apply_retention_policy "$DB_NAME" "$KEEP_LAST" "$KEEP_DAYS"
        fi
    done
fi

echo "----------------------------------------"
echo "Backup process finished."
