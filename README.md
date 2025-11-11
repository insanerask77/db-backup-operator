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
