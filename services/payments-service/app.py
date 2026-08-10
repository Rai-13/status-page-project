from flask import Flask, jsonify
import random

app = Flask(__name__)

is_outage = False

@app.route('/health')
def health_check():
    global is_outage
    if is_outage:
        return jsonify({"error": "Service Unavailable"}), 503
        
    # Simulate random 500 error 5% of the time
    if random.random() < 0.05:
        return jsonify({"error": "Internal Server Error"}), 500
        
    return jsonify({"status": "ok", "service": "payments"}), 200

@app.route('/toggle-outage')
def toggle_outage():
    global is_outage
    is_outage = not is_outage
    return jsonify({"outage_active": is_outage})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8002)
