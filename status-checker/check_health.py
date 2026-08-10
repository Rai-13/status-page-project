import os
import time
import psycopg2
import psutil
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL")

def init_db():
    if not DATABASE_URL:
        print("DATABASE_URL environment variable is missing. Will not log to database.")
        return None
    
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        # Ensure the table is ready (reusing existing schema)
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

def save_result(conn, name, usage_percent):
    if not conn:
        return
        
    status = "up"
    if usage_percent >= 95:
        status = "down"
    elif usage_percent >= 80:
        status = "degraded"
        
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO check_results (service_name, url, status, response_time_ms, error_message, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            name,
            "system",
            status,
            int(usage_percent),
            None,
            datetime.utcnow()
        ))
        conn.commit()
        print(f"Logged {name}: {usage_percent}% ({status})")
    except Exception as e:
        print(f"Failed to save result to database: {e}")
        conn.rollback()

def main():
    print(f"Starting system metrics check at {datetime.utcnow().isoformat()}...")
    
    conn = init_db()
    
    # Get system metrics
    cpu_usage = psutil.cpu_percent(interval=1)
    ram_usage = psutil.virtual_memory().percent
    disk_usage = psutil.disk_usage('/').percent
    
    save_result(conn, "CPU_Usage", cpu_usage)
    save_result(conn, "RAM_Usage", ram_usage)
    save_result(conn, "Disk_Usage", disk_usage)
        
    if conn:
        conn.close()
        
    print("System metrics checks completed.")

if __name__ == "__main__":
    main()
