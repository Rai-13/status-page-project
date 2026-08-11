from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timedelta
import docker
import platform
import psutil
import time
import os
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
                "timestamp": latest.timestamp.isoformat() + "Z",
                "error_message": latest.error_message
            })
            
    # Add dummy CDN mock for local dev if empty
    if not results:
        results = [
            {"service_name": "auth-service", "status": "up", "response_time_ms": 45, "timestamp": datetime.utcnow().isoformat() + "Z"},
            {"service_name": "payments-service", "status": "up", "response_time_ms": 120, "timestamp": datetime.utcnow().isoformat() + "Z"},
            {"service_name": "email-service", "status": "degraded", "response_time_ms": 850, "timestamp": datetime.utcnow().isoformat() + "Z"},
            {"service_name": "database-proxy", "status": "up", "response_time_ms": 20, "timestamp": datetime.utcnow().isoformat() + "Z"},
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
            "timestamp": row.timestamp.isoformat() + "Z"
        })
        
    return {"history": grouped}

@app.get("/api/infrastructure")
def get_infrastructure(db: Session = Depends(database.get_db)):
    """Get detailed infrastructure status"""
    
    # OS Info (since we run in Docker, this gets docker container's OS info, 
    # but psutil will get host hardware info)
    os_info = f"{platform.system()} {platform.release()}"
    cpu_cores = psutil.cpu_count(logical=True)
    total_ram_gb = round(psutil.virtual_memory().total / (1024**3), 2)
    uptime_seconds = time.time() - psutil.boot_time()
    uptime_hours = round(uptime_seconds / 3600, 1)
    
    architecture = platform.machine()
    
    cpu_freq_info = psutil.cpu_freq()
    cpu_freq_mhz = int(cpu_freq_info.current) if cpu_freq_info else 0
    
    swap_memory_gb = round(psutil.swap_memory().total / (1024**3), 2)
    active_processes = len(psutil.pids())

    # Deep Telemetry
    net_io = psutil.net_io_counters()
    net_sent_gb = round(net_io.bytes_sent / (1024**3), 2)
    net_recv_gb = round(net_io.bytes_recv / (1024**3), 2)
    
    disk_usage = psutil.disk_usage('/')
    disk_total_gb = round(disk_usage.total / (1024**3), 1)
    disk_free_gb = round(disk_usage.free / (1024**3), 1)
    
    try:
        load1, load5, load15 = os.getloadavg()
        sys_load = f"{load1:.2f}, {load5:.2f}, {load15:.2f}"
    except AttributeError:
        sys_load = "N/A"

    infra_data = {
        "os_info": os_info,
        "cpu_cores": cpu_cores,
        "total_ram_gb": total_ram_gb,
        "uptime_hours": uptime_hours,
        "architecture": architecture,
        "cpu_freq_mhz": cpu_freq_mhz,
        "swap_memory_gb": swap_memory_gb,
        "active_processes": active_processes,
        "net_sent_gb": net_sent_gb,
        "net_recv_gb": net_recv_gb,
        "disk_total_gb": disk_total_gb,
        "disk_free_gb": disk_free_gb,
        "sys_load": sys_load,
        "containers_running": 0,
        "containers_stopped": 0,
        "db_engine": "Unknown",
        "db_version": "Unknown",
        "k8s_status": "Offline",
        "active_ports": [],
        "error": None
    }
    
    # 1. Check Docker Containers
    try:
        client = docker.from_env()
        containers = client.containers.list(all=True)
        running = 0
        stopped = 0
        active_ports = []
        seen_ports = set()
        for c in containers:
            if c.status == 'running':
                running += 1
                if c.ports:
                    for container_port, host_bindings in c.ports.items():
                        if host_bindings:
                            for binding in host_bindings:
                                host_port = binding.get('HostPort')
                                if host_port and host_port not in seen_ports:
                                    seen_ports.add(host_port)
                                    active_ports.append({
                                        "port": host_port,
                                        "service": c.name
                                    })
            else:
                stopped += 1
                
        infra_data["containers_running"] = running
        infra_data["containers_stopped"] = stopped
        infra_data["active_ports"] = active_ports
    except Exception as e:
        infra_data["error"] = f"Docker connection failed: {str(e)}"
        
    # 2. Check Database Version
    try:
        result = db.execute(text("SELECT version();")).scalar()
        if result:
            parts = result.split()
            if len(parts) > 1:
                infra_data["db_engine"] = parts[0]
                infra_data["db_version"] = parts[1]
    except Exception as e:
        if not infra_data["error"]:
            infra_data["error"] = f"DB version query failed: {str(e)}"
            
    return infra_data

