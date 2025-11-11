from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import yaml
import os
import sqlite3
from typing import List, Dict, Any
import requests
from prometheus_client import Gauge, make_asgi_app

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
os.makedirs("/data", exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS backup_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        status TEXT NOT NULL,
        size REAL,
        duration REAL,
        checksum TEXT
    )
    """)
    conn.commit()
    conn.close()

init_db()

# --- Pydantic Models ---
class BackupHistory(BaseModel):
    name: str
    timestamp: str
    status: str
    size: float
    duration: float
    checksum: str

# --- Helper Functions ---
def get_config():
    config_path = os.environ.get("CONFIG_PATH", "/config/config.yaml")
    if not os.path.exists(config_path):
        raise HTTPException(status_code=500, detail="Configuration file not found.")
    with open(config_path, "r") as f:
        return yaml.safe_load(f)

# --- API Endpoints ---
@app.get("/api/backups")
def get_backups() -> List[Dict[str, Any]]:
    config = get_config()
    return config.get("backups", [])

@app.post("/api/backups/run/{name}")
def run_backup(name: str):
    runner_url = os.environ.get("RUNNER_URL")
    if not runner_url:
        raise HTTPException(status_code=500, detail="RUNNER_URL not configured.")
    try:
        response = requests.post(f"{runner_url}/run/{name}")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
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
    runner_url = os.environ.get("RUNNER_URL")
    if not runner_url:
        raise HTTPException(status_code=500, detail="RUNNER_URL not configured.")
    try:
        response = requests.post(f"{runner_url}/reload")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=str(e))
