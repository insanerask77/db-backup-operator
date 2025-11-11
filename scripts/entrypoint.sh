#!/bin/bash

set -e

CONFIG_FILE="/config/config.yaml"
CRON_FILE="/etc/crontabs/root"

# Check if the configuration file exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: Configuration file not found at $CONFIG_FILE"
    exit 1
fi

# Clear the crontab
> $CRON_FILE

DATABASES_COUNT=$(yq e '.databases | length' $CONFIG_FILE)

echo "Setting up cron jobs..."

for i in $(seq 0 $(($DATABASES_COUNT - 1))); do
    DB_NAME=$(yq e ".databases[$i].name" $CONFIG_FILE)
    CRON_SCHEDULE=$(yq e ".databases[$i].cron_schedule" $CONFIG_FILE)

    if [ -n "$CRON_SCHEDULE" ]; then
        echo "Adding cron job for database: $DB_NAME"
        echo "$CRON_SCHEDULE /app/scripts/backup.sh \"$DB_NAME\" >> /var/log/cron.log 2>&1" >> $CRON_FILE
    else
        echo "Warning: No cron schedule found for database '$DB_NAME'. Skipping."
    fi
done

# Add a newline to the end of the file
echo "" >> $CRON_FILE

echo "----------------------------------------"
echo "Generated crontab:"
cat $CRON_FILE
echo "----------------------------------------"

# Start the cron daemon
echo "Starting cron daemon..."
exec crond -f -l 8
