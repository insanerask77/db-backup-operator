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
DATABASES_COUNT=$(yq e '.databases | length' $CONFIG_FILE)

# Function to perform a backup for a specific database
perform_backup() {
    local DB_NAME=$1
    local DB_TYPE=$2
    local DB_HOST=$3
    local DB_PORT=$4
    local DB_USER=$5
    local DB_PASS=$6
    local DB_DBNAME=$7

    TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
    BACKUP_FILENAME="${DB_NAME}_${TIMESTAMP}"

    echo "----------------------------------------"
    echo "Backing up database: $DB_NAME ($DB_TYPE)"

    if [ "$DB_TYPE" == "postgres" ]; then
        BACKUP_FILE_PATH="${BACKUP_DIR}/${BACKUP_FILENAME}.sql.gz"
        export PGPASSWORD=$DB_PASS
        pg_dump -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_DBNAME | gzip > $BACKUP_FILE_PATH
        unset PGPASSWORD
    elif [ "$DB_TYPE" == "mongodb" ]; then
        BACKUP_FILE_PATH="${BACKUP_DIR}/${BACKUP_FILENAME}.archive.gz"
        mongodump --host $DB_HOST --port $DB_PORT -u $DB_USER -p "$DB_PASS" --db $DB_DBNAME --archive --quiet | gzip > $BACKUP_FILE_PATH
    else
        echo "Error: Unsupported database type '$DB_TYPE' for database '$DB_NAME'"
        return 1
    fi

    if [ $? -eq 0 ]; then
        echo "Backup for $DB_NAME created successfully at $BACKUP_FILE_PATH"
        md5sum $BACKUP_FILE_PATH > "${BACKUP_FILE_PATH}.md5"
        echo "MD5 checksum created for $BACKUP_FILE_PATH"
    else
        echo "Error: Backup failed for database $DB_NAME"
    fi
}

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

    perform_backup "$TARGET_DB_NAME" "$DB_TYPE" "$DB_HOST" "$DB_PORT" "$DB_USER" "$DB_PASS" "$DB_DBNAME"
else
    # Backup all databases
    for i in $(seq 0 $(($DATABASES_COUNT - 1))); do
        DB_NAME=$(yq e ".databases[$i].name" $CONFIG_FILE)
        DB_TYPE=$(yq e ".databases[$i].type" $CONFIG_FILE)
        DB_HOST=$(yq e ".databases[$i].host" $CONFIG_FILE)
        DB_PORT=$(yq e ".databases[$i].port" $CONFIG_FILE)
        DB_USER=$(yq e ".databases[$i].user" $CONFIG_FILE)
        DB_PASS=$(yq e ".databases[$i].password" $CONFIG_FILE)
        DB_DBNAME=$(yq e ".databases[$i].dbname" $CONFIG_FILE)

        perform_backup "$DB_NAME" "$DB_TYPE" "$DB_HOST" "$DB_PORT" "$DB_USER" "$DB_PASS" "$DB_DBNAME"
    done
fi

echo "----------------------------------------"
echo "Backup process finished."
