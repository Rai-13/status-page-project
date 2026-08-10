from flask import Flask, jsonify
import random
import time

app = Flask(__name__)

@app.route('/health')
def health_check():
    # Occasionally slow (2s) to simulate degraded performance
    if random.random() < 0.2:
        time.sleep(2)
    return jsonify({"status": "ok", "service": "search"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8005)
