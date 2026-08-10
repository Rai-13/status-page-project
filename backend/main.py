from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timedelta
import docker
from sqlalchemy import text

import models
import database
from database import engine

# Create the database tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Status Page API")

# Allow frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/status")
def get_current_status(db: Session = Depends(database.get_db)):
    """Get the most recent check result for each service"""
    # Subquery to get latest timestamp per service
    services_query = db.query(models.CheckResult.service_name).distinct().all()
    services = [s[0] for s in services_query]
    
    results = []
    for service in services:
        latest = db.query(models.CheckResult)\
            .filter(models.CheckResult.service_name == service)\
            .order_by(models.CheckResult.timestamp.desc())\
            .first()
        if latest:
            results.append({
                "service_name": latest.service_name,
                "status": latest.status,
                "response_time_ms": latest.response_time_ms,
                "timestamp": latest.timestamp.isoformat(),
                "error_message": latest.error_message
            })
            
    # Add dummy CDN mock for local dev if empty
    if not results:
        results = [
            {"service_name": "auth-service", "status": "up", "response_time_ms": 45, "timestamp": datetime.utcnow().isoformat()},
            {"service_name": "payments-service", "status": "up", "response_time_ms": 120, "timestamp": datetime.utcnow().isoformat()},
            {"service_name": "email-service", "status": "degraded", "response_time_ms": 850, "timestamp": datetime.utcnow().isoformat()},
            {"service_name": "database-proxy", "status": "up", "response_time_ms": 20, "timestamp": datetime.utcnow().isoformat()},
        ]
        
    return {"services": results}

@app.get("/api/history")
def get_history(db: Session = Depends(database.get_db)):
    """Get history for the last 24 hours to draw uptime graphs"""
    time_threshold = datetime.utcnow() - timedelta(hours=24)
    
    # In a real app we'd aggregate this (e.g. hourly buckets), but for the demo we'll fetch all or limit
    history = db.query(models.CheckResult)\
        .filter(models.CheckResult.timestamp >= time_threshold)\
        .order_by(models.CheckResult.timestamp.asc())\
        .limit(1000)\
        .all()
        
    # Group by service
    grouped = {}
    for row in history:
        if row.service_name not in grouped:
            grouped[row.service_name] = []
        grouped[row.service_name].append({
            "status": row.status,
            "response_time_ms": row.response_time_ms,
            "timestamp": row.timestamp.isoformat()
        })
        
    return {"history": grouped}

@app.get("/api/infrastructure")
def get_infrastructure(db: Session = Depends(database.get_db)):
    """Get the infrastructure status using docker socket and db connection"""
    infra_data = {
        "containers_running": 0,
        "containers_stopped": 0,
        "db_engine": "Unknown",
        "db_version": "Unknown",
        "error": None
    }
    
    # 1. Check Docker Containers
    try:
        # Connect to the docker daemon (requires socket mount)
        client = docker.from_env()
        containers = client.containers.list(all=True)
        
        running = 0
        stopped = 0
        for c in containers:
            if c.status == 'running':
                running += 1
            else:
                stopped += 1
                
        infra_data["containers_running"] = running
        infra_data["containers_stopped"] = stopped
    except Exception as e:
        infra_data["error"] = f"Docker connection failed: {str(e)}"
        
    # 2. Check Database Version
    try:
        # Execute a raw SQL query to get the postgres version
        result = db.execute(text("SELECT version();")).scalar()
        if result:
            # PostgreSQL 15.3 (Debian 15.3-1.pgdg110+1) on x86_64-pc-linux-gnu ...
            parts = result.split()
            if len(parts) > 1:
                infra_data["db_engine"] = parts[0]
                infra_data["db_version"] = parts[1]
    except Exception as e:
        if not infra_data["error"]:
            infra_data["error"] = f"DB version query failed: {str(e)}"
            
    return infra_data

