import os
import yaml
import subprocess
import hashlib
import gnupg
import requests
from datetime import datetime
import logging
import argparse
import time

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_config():
    """Reads and returns the YAML configuration."""
    config_path = os.environ.get("CONFIG_PATH", "/config/config.yaml")
    if not os.path.exists(config_path):
        logging.error(f"Configuration file not found at {config_path}")
        return None
    with open(config_path, "r") as f:
        return yaml.safe_load(f)

def run_command(command):
    """Executes a shell command and returns the output."""
    logging.info(f"Running command: {' '.join(command)}")
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()
    if process.returncode != 0:
        logging.error(f"Error executing command: {stderr.decode('utf-8')}")
        return None
    return stdout

def calculate_checksum(filepath, algorithm='md5'):
    """Calculates the checksum of a file."""
    hash_func = hashlib.new(algorithm)
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_func.update(chunk)
    return hash_func.hexdigest()

def compress_file(filepath, compression='gzip'):
    """Compresses a file."""
    if compression == 'gzip':
        compressed_filepath = f"{filepath}.gz"
        run_command(['gzip', '-f', filepath])
    elif compression == 'zstd':
        compressed_filepath = f"{filepath}.zst"
        run_command(['zstd', '-f', filepath])
    else:
        return filepath
    return compressed_filepath

def encrypt_file(filepath, gpg_key_path):
    """Encrypts a file using GPG."""
    gpg = gnupg.GPG()
    # Import the key
    with open(gpg_key_path, 'r') as f:
        key_data = f.read()
    import_result = gpg.import_keys(key_data)
    if not import_result.results:
        logging.error(f"Failed to import GPG key from {gpg_key_path}")
        return None

    key_fingerprint = import_result.results[0]['fingerprint']

    with open(filepath, 'rb') as f:
        status = gpg.encrypt_file(f, recipients=[key_fingerprint], output=f"{filepath}.gpg", always_trust=True)
    if not status.ok:
        logging.error(f"GPG encryption failed: {status.stderr}")
        return None
    os.remove(filepath)
    return f"{filepath}.gpg"

def apply_retention(backup_dir, retention_policy):
    """Applies the retention policy to backups."""
    if not os.path.exists(backup_dir):
        return

    files = sorted(
        [os.path.join(backup_dir, f) for f in os.listdir(backup_dir)],
        key=os.path.getmtime,
        reverse=True
    )

    if 'keep_last' in retention_policy:
        files_to_delete = files[retention_policy['keep_last']:]
    elif 'days' in retention_policy:
        cutoff = datetime.now().timestamp() - (retention_policy['days'] * 86400)
        files_to_delete = [f for f in files if os.path.getmtime(f) < cutoff]
    else:
        return

    for f in files_to_delete:
        logging.info(f"Deleting old backup: {f}")
        os.remove(f)

def report_status(backend_url, backup_name, status, size, duration, checksum):
    """Reports the backup status to the backend."""
    try:
        requests.post(f"{backend_url}/api/backups/history/{backup_name}", json={
            "status": status,
            "size": size,
            "duration": duration,
            "checksum": checksum,
            "timestamp": datetime.now().isoformat()
        })
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to report status to backend: {e}")

def run_backup(name, config):
    """Runs a single backup job."""
    logging.info(f"Starting backup for {name}")
    start_time = time.time()
    backup_dir = config['storage']['path']
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')

    # Run backup command
    if config['type'] == 'postgres':
        filename = f"{name}-{timestamp}.sql"
        filepath = os.path.join(backup_dir, filename)
        os.environ['PGPASSWORD'] = config['password']
        command = [
            'pg_dump',
            '-h', config['host'],
            '-p', str(config['port']),
            '-U', config['user'],
            '-d', config['database'],
            '-f', filepath
        ]
        run_command(command)
    elif config['type'] == 'mongo':
        filename = f"{name}-{timestamp}.dump"
        filepath = os.path.join(backup_dir, filename)
        command = [
            'mongodump',
            '--uri', config['uri'],
            '--archive=' + filepath
        ]
        run_command(command)
    else:
        logging.error(f"Unknown backup type: {config['type']}")
        return

    if not os.path.exists(filepath):
        logging.error("Backup file was not created.")
        report_status(os.environ.get("BACKEND_URL"), name, "failed", 0, time.time() - start_time, None)
        return

    # Compress
    if 'compression' in config:
        filepath = compress_file(filepath, config['compression'])

    # Encrypt
    if config.get('encrypt'):
        filepath = encrypt_file(filepath, config['encrypt_key'])

    # Checksum
    checksum = calculate_checksum(filepath, config.get('checksum', 'md5'))

    # Retention
    if 'retention' in config:
        apply_retention(backup_dir, config['retention'])

    # Report status
    duration = time.time() - start_time
    size = os.path.getsize(filepath)
    report_status(os.environ.get("BACKEND_URL"), name, "success", size, duration, checksum)
    logging.info(f"Backup for {name} completed successfully.")

def main():
    """Main function to run a single backup."""
    parser = argparse.ArgumentParser(description="Run a single backup job.")
    parser.add_argument("backup_name", help="The name of the backup to run.")
    args = parser.parse_args()

    config = get_config()
    if not config:
        return

    backup_config = next((b for b in config.get('backups', []) if b['name'] == args.backup_name), None)
    if not backup_config:
        logging.error(f"Backup '{args.backup_name}' not found in config.")
        return

    run_backup(backup_config['name'], backup_config)

if __name__ == "__main__":
    main()
