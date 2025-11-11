from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
import subprocess
from typing import List, Dict, Any, Optional
from prometheus_client import Gauge, make_asgi_app
import sqlite3
import os
import yaml
import logging
from datetime import datetime
from fastapi.responses import FileResponse

from runner import get_config, calculate_checksum

# Configure logging
log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=log_level, format='%(asctime)s - %(levelname)s - %(message)s')

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
    checksum: Optional[str]

class BackupHistoryIn(BaseModel):
    timestamp: str
    status: str
    size: float
    duration: float
    checksum: Optional[str]

class BackupFile(BaseModel):
    name: str
    size: int
    modified: str
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
        subprocess.Popen(['python', '/usr/src/app/runner.py', 'backup', name])
        return {'status': 'Backup started'}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/backups/restore/{name}")
def restore_backup(name: str, file: str = Query(None)):
    """Triggers an on-demand restore."""
    config = get_config()
    backup_config = next((b for b in config.get('backups', []) if b['name'] == name), None)
    if not backup_config:
        raise HTTPException(status_code=404, detail="Backup config not found.")

    if not file:
        backup_dir = os.path.join(backup_config['storage']['path'], name)
        if not os.path.exists(backup_dir):
            raise HTTPException(status_code=404, detail="Backup directory not found.")
        files = sorted(
            [os.path.join(backup_dir, f) for f in os.listdir(backup_dir)],
            key=os.path.getmtime,
            reverse=True
        )
        if not files:
            raise HTTPException(status_code=404, detail="No backup files found.")
        file = files[0]

    try:
        subprocess.Popen(['python', '/usr/src/app/runner.py', 'restore', name, '--file', file])
        return {'status': f'Restore started from {file}'}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
def record_backup_history(name: str, history_entry: BackupHistoryIn):
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

@app.get("/api/backups/files/{name}", response_model=List[BackupFile])
def list_backup_files(name: str):
    config = get_config()
    backup_config = next((b for b in config.get('backups', []) if b['name'] == name), None)
    if not backup_config:
        raise HTTPException(status_code=404, detail="Backup config not found.")

    backup_dir = os.path.join(backup_config['storage']['path'], name)
    if not os.path.exists(backup_dir):
        return []

    files = []
    for f in os.listdir(backup_dir):
        filepath = os.path.join(backup_dir, f)
        files.append(
            BackupFile(
                name=f,
                size=os.path.getsize(filepath),
                modified=datetime.fromtimestamp(os.path.getmtime(filepath)).isoformat(),
                checksum=calculate_checksum(filepath)
            )
        )
    return files

@app.get("/api/backups/download/{name}/{filename}")
def download_backup_file(name: str, filename: str):
    config = get_config()
    backup_config = next((b for b in config.get('backups', []) if b['name'] == name), None)
    if not backup_config:
        raise HTTPException(status_code=404, detail="Backup config not found.")

    filepath = os.path.join(backup_config['storage']['path'], name, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found.")

    return FileResponse(filepath, media_type='application/octet-stream', filename=filename)

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
