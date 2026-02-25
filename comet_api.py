#!/usr/bin/env python3
"""
Comet API - Bridge extension sidebar to assigner/worker system
Runs on Pink Laptop as HTTP server for extension sidebar communication
"""

from flask import Flask, request, jsonify
import json
import subprocess
import sys
from datetime import datetime

app = Flask(__name__)

# Configuration
GAIA_SERVER = "100.112.58.92"
GAIA_USER = "jgirmay"
ASSIGNER_PATH = "/Users/jgirmay/Desktop/gitrepo/pyWork/architect/workers/assigner_worker.py"

class CometAPI:
    """Bridge between extension sidebar and Comet/GAIA"""

    def __init__(self):
        self.message_history = []
        self.max_history = 50

    def send_to_comet(self, prompt: str, priority: str = "medium") -> dict:
        """Send prompt to Comet via assigner on GAIA server"""
        try:
            # Build SSH command to call assigner on Mac Mini (GAIA server)
            priority_int = self._priority_to_int(priority)
            cmd = f"cd /Users/jgirmay/Desktop/gitrepo/pyWork/architect && python3 {ASSIGNER_PATH} --send \"{prompt}\" --priority {priority_int} --target comet"

            result = subprocess.run([
                "ssh",
                f"{GAIA_USER}@{GAIA_SERVER}",
                cmd
            ], capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                msg = {
                    "success": True,
                    "prompt": prompt,
                    "target": "comet",
                    "priority": priority,
                    "timestamp": datetime.now().isoformat(),
                    "status": "queued"
                }
                self.message_history.insert(0, msg)
                self.message_history = self.message_history[:self.max_history]
                return msg
            else:
                return {
                    "success": False,
                    "error": result.stderr if result.stderr else result.stdout,
                    "timestamp": datetime.now().isoformat()
                }
        except Exception as e:
            return {"success": False, "error": str(e), "timestamp": datetime.now().isoformat()}

    def _priority_to_int(self, priority: str) -> str:
        """Convert priority name to number"""
        priority_map = {
            "low": "1",
            "medium": "5",
            "high": "9"
        }
        return priority_map.get(priority, "5")

    def get_messages(self, limit: int = 10) -> list:
        """Get recent messages"""
        return self.message_history[:limit]

comet = CometAPI()

# API Routes

@app.route('/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({
        "status": "healthy",
        "service": "comet_api",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/send-to-comet', methods=['POST'])
def send_to_comet():
    """Send prompt to Comet"""
    data = request.json
    prompt = data.get('message') or data.get('prompt')
    priority = data.get('priority', 'medium')

    if not prompt:
        return jsonify({"error": "No message provided"}), 400

    result = comet.send_to_comet(prompt, priority)
    return jsonify(result), 200 if result.get('success') else 500

@app.route('/api/messages', methods=['GET'])
def get_messages():
    """Get message history"""
    limit = request.args.get('limit', 10, type=int)
    return jsonify(comet.get_messages(limit))

@app.route('/api/status', methods=['GET'])
def get_status():
    """Get API status"""
    return jsonify({
        "service": "comet_api",
        "status": "running",
        "gaia_server": GAIA_SERVER,
        "timestamp": datetime.now().isoformat()
    })

if __name__ == '__main__':
    print('🤖 Comet API starting...')
    print(f'   Endpoint: http://localhost:5555')
    print(f'   GAIA Server: {GAIA_SERVER}')
    print(f'   Assigner: {ASSIGNER_PATH}')
    app.run(host='127.0.0.1', port=5555, debug=False)
