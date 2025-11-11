from flask import Flask, jsonify
import subprocess

app = Flask(__name__)

@app.route('/run/<backup_name>', methods=['POST'])
def run_backup(backup_name):
    """Triggers an on-demand backup."""
    try:
        subprocess.Popen(['python', '/usr/src/app/runner.py', backup_name])
        return jsonify({'status': 'Backup started'}), 202
    except Exception as e:
        return jsonify({'status': 'Error', 'message': str(e)}), 500

@app.route('/reload', methods=['POST'])
def reload_config():
    """Triggers a configuration reload by re-running the scheduler."""
    try:
        subprocess.Popen(['python', '/usr/src/app/scheduler.py'])
        return jsonify({'status': 'Configuration reloaded'}), 202
    except Exception as e:
        return jsonify({'status': 'Error', 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
