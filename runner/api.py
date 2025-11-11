from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import subprocess
from typing import List, Dict, Any
from prometheus_client import Gauge, make_asgi_app
import sqlite3
import os
import yaml

from runner import get_config

# --- FastAPI App ---
app = FastAPI()

# --- Prometheus Metrics ---
backup_last_success_timestamp = Gauge('backup_last_success_timestamp', 'The timestamp of the last successful backup.', ['db', 'type'])
backup_size_bytes = Gauge('backup_size_bytes', 'The size of the last backup in bytes.', ['db', 'type'])
backup_status = Gauge('backup_status', 'The status of the last backup (1 for success, 0 for failure).', ['db', 'type'])
backup_duration_seconds = Gauge('backup_duration_seconds', 'The duration of the last backup in seconds.', ['db', 'type'])

metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# --- Database Setup ---
DB_FILE = "/data/backups.db"

# --- Pydantic Models ---
class BackupHistory(BaseModel):
    name: str
    timestamp: str
    status: str
    size: float
    duration: float
    checksum: str

# --- API Endpoints ---
@app.get("/api/backups")
def get_backups() -> List[Dict[str, Any]]:
    config = get_config()
    return config.get("backups", [])

@app.post("/api/backups/run/{name}")
def run_backup_endpoint(name: str):
    """Triggers an on-demand backup."""
    try:
        subprocess.Popen(['python', '/usr/src/app/runner.py', name])
        return {'status': 'Backup started'}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/backups/restore/{name}")
def restore_backup(name: str):
    # This is a placeholder for the restore functionality
    return {"message": f"Restore for {name} is not yet implemented."}

@app.get("/api/backups/history/{name}")
def get_backup_history(name: str) -> List[BackupHistory]:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT name, timestamp, status, size, duration, checksum FROM backup_history WHERE name = ?", (name,))
    history = [
        BackupHistory(name=row[0], timestamp=row[1], status=row[2], size=row[3], duration=row[4], checksum=row[5])
        for row in cursor.fetchall()
    ]
    conn.close()
    return history

@app.post("/api/backups/history/{name}")
def record_backup_history(name: str, history_entry: BackupHistory):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO backup_history (name, timestamp, status, size, duration, checksum) VALUES (?, ?, ?, ?, ?, ?)",
        (name, history_entry.timestamp, history_entry.status, history_entry.size, history_entry.duration, history_entry.checksum)
    )
    conn.commit()
    conn.close()

    # Update Prometheus metrics
    config = get_config()
    backup_config = next((b for b in config.get('backups', []) if b['name'] == name), None)
    if backup_config:
        db_type = backup_config.get('type', 'unknown')
        if history_entry.status == 'success':
            backup_last_success_timestamp.labels(db=name, type=db_type).set_to_current_time()
            backup_status.labels(db=name, type=db_type).set(1)
        else:
            backup_status.labels(db=name, type=db_type).set(0)
        backup_size_bytes.labels(db=name, type=db_type).set(history_entry.size)
        backup_duration_seconds.labels(db=name, type=db_type).set(history_entry.duration)

    return {"message": "History recorded."}

@app.post("/api/config/reload")
def reload_config():
    """Triggers a configuration reload by re-running the scheduler."""
    try:
        subprocess.Popen(['python', '/usr/src/app/scheduler.py'])
        return {'status': 'Configuration reloaded'}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000)
