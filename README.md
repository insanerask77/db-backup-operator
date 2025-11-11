# Backup Runner API

This document provides an overview of the Backup Runner API endpoints.

## Endpoints

### GET /api/backups

- **Description:** Retrieves a list of all configured backups.
- **Response:**
  - `200 OK`: A JSON array of backup configurations.

  ```json
  [
    {
      "name": "postgres-main",
      "type": "postgres",
      ...
    },
    {
      "name": "mongo-analytics",
      "type": "mongo",
      ...
    }
  ]
  ```

### POST /api/backups/run/{name}

- **Description:** Triggers an on-demand backup for the specified backup name.
- **Parameters:**
  - `name` (string, required): The name of the backup to run.
- **Response:**
  - `200 OK`: If the backup was started successfully.
  - `500 Internal Server Error`: If there was an error starting the backup.

  ```json
  {
    "status": "Backup started"
  }
  ```

### POST /api/backups/restore/{name}

- **Description:** Triggers an on-demand restore for the specified backup name. By default, it restores the latest backup.
- **Parameters:**
  - `name` (string, required): The name of the backup to restore.
- **Query Parameters:**
  - `file` (string, optional): The specific filename to restore.
- **Response:**
  - `200 OK`: If the restore was started successfully.
  - `404 Not Found`: If the backup configuration or file is not found.
  - `500 Internal Server Error`: If there was an error starting the restore.

  ```json
  {
    "status": "Restore started from /backups/postgres-main/postgres-main-20251111070000.sql.gz"
  }
  ```

### GET /api/backups/history/{name}

- **Description:** Retrieves the backup history for the specified backup name.
- **Parameters:**
  - `name` (string, required): The name of the backup to retrieve the history for.
- **Response:**
  - `200 OK`: A JSON array of backup history entries.

  ```json
  [
    {
      "name": "postgres-main",
      "timestamp": "2025-11-11T12:00:00Z",
      "status": "success",
      "size": 1024,
      "duration": 10.5,
      "checksum": "md5:..."
    }
  ]
  ```

### GET /api/backups/files/{name}

- **Description:** Lists the available backup files for a given backup.
- **Parameters:**
  - `name` (string, required): The name of the backup.
- **Response:**
  - `200 OK`: A JSON array of backup file details.

  ```json
  [
    {
      "name": "postgres-main-20251111070000.sql.gz",
      "size": 1024,
      "modified": "2025-11-11T07:00:00Z",
      "checksum": "md5:..."
    }
  ]
  ```

### GET /api/backups/download/{name}/{filename}

- **Description:** Downloads a specific backup file.
- **Parameters:**
  - `name` (string, required): The name of the backup.
  - `filename` (string, required): The name of the file to download.
- **Response:**
  - `200 OK`: The backup file.
  - `404 Not Found`: If the file is not found.

### POST /api/config/reload

- **Description:** Triggers a reload of the backup configuration. This will re-read the `config.yaml` file and update the cron jobs.
- **Response:**
  - `200 OK`: If the configuration was reloaded successfully.
  - `500 Internal Server Error`: If there was an error reloading the configuration.

  ```json
  {
    "status": "Configuration reloaded"
  }
  ```

## Configuration

### Environment Variables

- `LOG_LEVEL`: Sets the logging level for the application. Defaults to `INFO`. Possible values are `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`.
