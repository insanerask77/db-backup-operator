import os
import yaml
import subprocess
import hashlib
import gnupg
from datetime import datetime
import logging
import argparse
import time
import sqlite3

# Configure logging
log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=log_level, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Database Setup ---
DB_FILE = "/data/backups.db"

# --- Helper Functions ---
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

    stdout_decoded = stdout.decode('utf-8').strip()
    stderr_decoded = stderr.decode('utf-8').strip()

    if stdout_decoded:
        logging.info(f"Command stdout: {stdout_decoded}")
    if stderr_decoded:
        logging.warning(f"Command stderr: {stderr_decoded}")

    if process.returncode != 0:
        logging.error(f"Error executing command: {stderr_decoded}")
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

def decompress_file(filepath):
    """Decompresses a file."""
    if filepath.endswith('.gz'):
        decompressed_filepath = filepath[:-3]
        run_command(['gunzip', '-f', filepath])
    elif filepath.endswith('.zst'):
        decompressed_filepath = filepath[:-4]
        run_command(['zstd', '-d', '-f', filepath])
    else:
        return filepath
    return decompressed_filepath

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

def decrypt_file(filepath, gpg_key_path):
    """Decrypts a file using GPG."""
    gpg = gnupg.GPG()
    # Import the key
    with open(gpg_key_path, 'r') as f:
        key_data = f.read()
    import_result = gpg.import_keys(key_data)
    if not import_result.results:
        logging.error(f"Failed to import GPG key from {gpg_key_path}")
        return None

    decrypted_filepath = filepath[:-4]
    with open(filepath, 'rb') as f:
        status = gpg.decrypt_file(f, output=decrypted_filepath)
    if not status.ok:
        logging.error(f"GPG decryption failed: {status.stderr}")
        return None
    return decrypted_filepath

def apply_retention(backup_dir, retention_policy):
    """Applies the retention policy to backups."""
    if not os.path.exists(backup_dir):
        logging.info(f"Backup directory {backup_dir} does not exist. Skipping retention.")
        return

    logging.info(f"Applying retention policy for {backup_dir}")
    files = sorted(
        [os.path.join(backup_dir, f) for f in os.listdir(backup_dir)],
        key=os.path.getmtime,
        reverse=True
    )
    logging.info(f"Found {len(files)} backups in {backup_dir}.")

    if 'keep_last' in retention_policy:
        keep_last = retention_policy['keep_last']
        logging.info(f"Retention policy: keep_last = {keep_last}")
        files_to_delete = files[keep_last:]
    elif 'days' in retention_policy:
        days = retention_policy['days']
        logging.info(f"Retention policy: days = {days}")
        cutoff = datetime.now().timestamp() - (days * 86400)
        files_to_delete = [f for f in files if os.path.getmtime(f) < cutoff]
    else:
        logging.info("No retention policy specified.")
        return

    logging.info(f"Found {len(files_to_delete)} backups to delete.")
    for f in files_to_delete:
        logging.info(f"Deleting old backup: {f}")
        os.remove(f)

def report_status(backup_name, status, size, duration, checksum):
    """Reports the backup status to the database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO backup_history (name, timestamp, status, size, duration, checksum) VALUES (?, ?, ?, ?, ?, ?)",
        (backup_name, datetime.now().isoformat(), status, size, duration, checksum)
    )
    conn.commit()
    conn.close()

def run_backup(name, config):
    """Runs a single backup job."""
    logging.info(f"Starting backup for {name}")
    start_time = time.time()
    backup_dir = os.path.join(config['storage']['path'], name)
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
            '-vv',
            '--uri', config['uri'],
            '--archive=' + filepath
        ]
        run_command(command)
    else:
        logging.error(f"Unknown backup type: {config['type']}")
        return

    if not os.path.exists(filepath):
        logging.error("Backup file was not created.")
        report_status(name, "failed", 0, time.time() - start_time, None)
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
    report_status(name, "success", size, duration, checksum)
    logging.info(f"Backup for {name} completed successfully.")

def run_restore(name, config, filepath):
    """Runs a single restore job."""
    logging.info(f"Starting restore for {name} from {filepath}")

    # Decrypt
    if config.get('encrypt'):
        filepath = decrypt_file(filepath, config['encrypt_key'])

    # Decompress
    if 'compression' in config:
        filepath = decompress_file(filepath)

    # Run restore command
    if config['type'] == 'postgres':
        os.environ['PGPASSWORD'] = config['password']
        command = [
            'pg_restore',
            '-h', config['host'],
            '-p', str(config['port']),
            '-U', config['user'],
            '-d', config['database'],
            '--clean',
            '--if-exists',
            filepath
        ]
        run_command(command)
    elif config['type'] == 'mongo':
        command = [
            'mongorestore',
            '--uri', config['uri'],
            '--archive=' + filepath,
            '--drop'
        ]
        run_command(command)
    else:
        logging.error(f"Unknown backup type: {config['type']}")
        return

    logging.info(f"Restore for {name} completed successfully.")

def main():
    """Main function to run a single backup or restore."""
    parser = argparse.ArgumentParser(description="Run a single backup or restore job.")
    parser.add_argument("action", choices=['backup', 'restore'], help="The action to perform.")
    parser.add_argument("backup_name", help="The name of the backup config to use.")
    parser.add_argument("--file", help="The file to restore from (for restore action only).")
    args = parser.parse_args()

    config = get_config()
    if not config:
        return

    backup_config = next((b for b in config.get('backups', []) if b['name'] == args.backup_name), None)
    if not backup_config:
        logging.error(f"Backup '{args.backup_name}' not found in config.")
        return

    if args.action == 'backup':
        run_backup(backup_config['name'], backup_config)
    elif args.action == 'restore':
        if not args.file:
            logging.error("The --file argument is required for the restore action.")
            return
        run_restore(backup_config['name'], backup_config, args.file)

if __name__ == "__main__":
    main()
