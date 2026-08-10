import json
import os
import time
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL")
CONFIG_PATH = os.getenv("CONFIG_PATH", "config.json")

def init_db():
    if not DATABASE_URL:
        print("DATABASE_URL environment variable is missing. Will not log to database.")
        return None
    
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        # Create table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS check_results (
                id SERIAL PRIMARY KEY,
                service_name VARCHAR(100) NOT NULL,
                url VARCHAR(255) NOT NULL,
                status VARCHAR(50) NOT NULL,
                response_time_ms INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                error_message TEXT
            )
        """)
        conn.commit()
        return conn
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return None

def check_service(service):
    name = service.get("name")
    url = service.get("url")
    
    print(f"Checking {name} at {url}...")
    
    start_time = time.time()
    try:
        response = requests.get(url, timeout=10)
        response_time_ms = int((time.time() - start_time) * 1000)
        
        status = "up"
        if response.status_code >= 500:
            status = "down"
        elif response.status_code >= 400:
            status = "degraded"
            
        # Consider it degraded if it takes longer than 1 second
        if response_time_ms > 1000 and status == "up":
            status = "degraded"
            
        print(f"[{status.upper()}] {name} - {response.status_code} - {response_time_ms}ms")
        
        return {
            "service_name": name,
            "url": url,
            "status": status,
            "response_time_ms": response_time_ms,
            "error_message": None
        }
    except requests.exceptions.RequestException as e:
        response_time_ms = int((time.time() - start_time) * 1000)
        print(f"[DOWN] {name} - Request failed: {e}")
        
        return {
            "service_name": name,
            "url": url,
            "status": "down",
            "response_time_ms": response_time_ms,
            "error_message": str(e)
        }

def save_result(conn, result):
    if not conn:
        return
        
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO check_results (service_name, url, status, response_time_ms, error_message, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            result["service_name"],
            result["url"],
            result["status"],
            result["response_time_ms"],
            result["error_message"],
            datetime.utcnow()
        ))
        conn.commit()
    except Exception as e:
        print(f"Failed to save result to database: {e}")
        conn.rollback()

def main():
    print(f"Starting health checks at {datetime.utcnow().isoformat()}...")
    
    try:
        with open(CONFIG_PATH, 'r') as f:
            config = json.load(f)
    except Exception as e:
        print(f"Failed to load config from {CONFIG_PATH}: {e}")
        return

    services = config.get("services", [])
    if not services:
        print("No services configured to check.")
        return

    conn = init_db()
    
    for service in services:
        result = check_service(service)
        save_result(conn, result)
        
    if conn:
        conn.close()
        
    print("Health checks completed.")

if __name__ == "__main__":
    main()
