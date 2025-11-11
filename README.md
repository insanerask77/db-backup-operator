# Dockerized Backup System for PostgreSQL and MongoDB

This project provides a simple and configurable backup system for PostgreSQL and MongoDB databases, running in a lightweight Docker container.

## Features

-   **Declarative Configuration**: Configure your backups using a simple YAML file.
-   **Support for PostgreSQL and MongoDB**: Back up both PostgreSQL and MongoDB databases.
-   **Automated Backups**: Schedule your backups using cron expressions.
-   **Configurable Compression**: Choose between `gz`, `zip`, or `none` for your backup compression.
-   **Retention Policies**: Automatically clean up old backups by specifying how many to keep or for how long.
-   **MD5 Checksums**: Verify the integrity of your backups with MD5 checksums.
-   **Lightweight**: Based on Alpine Linux for a small footprint.

## Getting Started

### Prerequisites

-   [Docker](https://docs.docker.com/get-docker/)
-   [Docker Compose](https://docs.docker.com/compose/install/)

### Configuration

1.  **Copy the configuration file**:
    ```bash
    cp config/config.yaml.example config/config.yaml
    ```

2.  **Edit `config/config.yaml`**:
    Update the `config.yaml` file to match your database settings.

    ```yaml
    global:
      backup_path: /backups

    databases:
      - name: my_postgres_db
        type: postgres
        host: postgres_host
        port: 5432
        user: postgres_user
        password: postgres_password
        dbname: my_database
        cron_schedule: "0 2 * * *" # At 02:00 every day
        compression: gz # Options: gz, zip, none
        retention:
          keep_last: 10 # Keep the last 10 backups

      - name: my_mongo_db
        type: mongodb
        host: mongo_host
        port: 27017
        user: mongo_user
        password: mongo_password
        dbname: my_mongo_database
        cron_schedule: "0 3 * * *" # At 03:00 every day
        compression: zip # Options: gz, zip, none
        retention:
          keep_days: 30 # Keep backups for the last 30 days
    ```

### Configuration Options

-   `compression`: Sets the compression method for the backup.
    -   `gz`: Compresses the backup using gzip.
    -   `zip`: Compresses the backup using zip.
    -   `none`: Stores the backup without compression.

-   `retention`: Sets the policy for cleaning up old backups.
    -   `keep_last`: Keeps the specified number of the most recent backups.
    -   `keep_days`: Keeps all backups from the specified number of recent days.

### Running the Backup Container

To start the backup container, run the following command:

```bash
docker-compose up -d --build
```

The container will start and the cron jobs will be scheduled automatically.

## Backups

Backups are stored in the `backups/` directory on your host machine. Each backup is a compressed file (or uncompressed, depending on your configuration) and is accompanied by an MD5 checksum file.
