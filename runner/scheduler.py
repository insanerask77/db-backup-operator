import yaml
import os
from crontab import CronTab
import logging

log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=log_level, format='%(asctime)s - %(levelname)s - %(message)s')

def get_config():
    """Reads and returns the YAML configuration."""
    config_path = os.environ.get("CONFIG_PATH", "/config/config.yaml")
    if not os.path.exists(config_path):
        logging.error(f"Configuration file not found at {config_path}")
        return None
    with open(config_path, "r") as f:
        return yaml.safe_load(f)

def main():
    """Creates cron jobs for each backup based on the config."""
    config = get_config()
    if not config:
        return

    cron = CronTab(user='root')
    cron.remove_all() # Clear existing jobs to avoid duplicates

    for backup in config.get('backups', []):
        command = f"/usr/local/bin/python /usr/src/app/runner.py {backup['name']} >> /var/log/cron.log 2>&1"
        job = cron.new(command=command, comment=backup['name'])
        job.setall(backup['schedule'])
        cron.write()
        logging.info(f"Scheduled backup for '{backup['name']}' with schedule: {backup['schedule']}")

if __name__ == "__main__":
    main()
