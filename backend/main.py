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
import subprocess
from sqlalchemy import text

import models
import database
from database import engine

# Global state for IO tracking
last_net_io = None
last_net_time = None
last_disk_io = None
last_disk_time = None

PROTECTED_PORTS = {22, 53, 80, 443, 111, 631, 5432, 8000, 8080, 3306}
PROTECTED_PROCESSES = ["language_server", "docker", "containerd", "systemd", "sshd"]

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
    global last_net_io, last_net_time, last_disk_io, last_disk_time
    current_time = time.time()
    
    net_io = psutil.net_io_counters()
    net_sent_gb = round(net_io.bytes_sent / (1024**3), 2)
    net_recv_gb = round(net_io.bytes_recv / (1024**3), 2)
    
    net_speed_sent_mb = 0.0
    net_speed_recv_mb = 0.0
    if last_net_io and last_net_time and current_time > last_net_time:
        dt = current_time - last_net_time
        net_speed_sent_mb = (net_io.bytes_sent - last_net_io.bytes_sent) / dt / (1024*1024)
        net_speed_recv_mb = (net_io.bytes_recv - last_net_io.bytes_recv) / dt / (1024*1024)
    last_net_io = net_io
    last_net_time = current_time
    
    try:
        users_count = len(psutil.users())
    except:
        users_count = 0
        
    try:
        partitions_count = len(psutil.disk_partitions())
    except:
        partitions_count = 0
        
    try:
        boot_time_str = datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M")
    except:
        boot_time_str = "Unknown"
    
    disk_usage = psutil.disk_usage('/')
    disk_total_gb = round(disk_usage.total / (1024**3), 1)
    disk_free_gb = round(disk_usage.free / (1024**3), 1)
    
    disk_io = psutil.disk_io_counters()
    disk_speed_read_mb = 0.0
    disk_speed_write_mb = 0.0
    if last_disk_io and last_disk_time and current_time > last_disk_time:
        dt = current_time - last_disk_time
        disk_speed_read_mb = (disk_io.read_bytes - last_disk_io.read_bytes) / dt / (1024*1024)
        disk_speed_write_mb = (disk_io.write_bytes - last_disk_io.write_bytes) / dt / (1024*1024)
    last_disk_io = disk_io
    last_disk_time = current_time
    
    # Hardware Temperature
    cpu_temp = "N/A"
    if hasattr(psutil, "sensors_temperatures"):
        temps = psutil.sensors_temperatures()
        if 'coretemp' in temps and temps['coretemp']:
            for entry in temps['coretemp']:
                if 'Package' in entry.label:
                    cpu_temp = f"{entry.current}°C"
                    break
            if cpu_temp == "N/A":
                cpu_temp = f"{temps['coretemp'][0].current}°C"
                
    # Top Processes by Memory
    procs = []
    for p in psutil.process_iter(['pid', 'name', 'memory_percent']):
        try:
            info = p.info
            if info['name'] and info['memory_percent'] is not None:
                procs.append({
                    'pid': info['pid'],
                    'name': info['name'],
                    'mem': info['memory_percent']
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    top_procs = sorted(procs, key=lambda x: x['mem'], reverse=True)[:5]
    for p in top_procs:
        p['mem'] = round(p['mem'], 1)
    
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
        "disk_speed_read_mb": round(disk_speed_read_mb, 2),
        "disk_speed_write_mb": round(disk_speed_write_mb, 2),
        "net_speed_sent_mb": round(net_speed_sent_mb, 2),
        "net_speed_recv_mb": round(net_speed_recv_mb, 2),
        "cpu_temp": cpu_temp,
        "top_processes": top_procs,
        "sys_load": sys_load,
        "containers_running": 0,
        "containers_stopped": 0,
        "container_details": [],
        "db_engine": "Unknown",
        "db_version": "Unknown",
        "k8s_status": "Offline",
        "active_ports": [],
        "logged_in_users": users_count,
        "disk_partitions": partitions_count,
        "boot_time": boot_time_str,
        "error": None
    }
    
    # 1. Check Docker Containers
    try:
        client = docker.from_env()
        containers = client.containers.list(all=True)
        running = 0
        stopped = 0
        container_details = []
        for c in containers:
            if c.status == 'running':
                running += 1
            else:
                stopped += 1
            container_details.append({
                "id": c.short_id,
                "name": c.name,
                "image": c.image.tags[0] if c.image.tags else c.image.id[:10],
                "status": c.status
            })
        infra_data["containers_running"] = running
        infra_data["containers_stopped"] = stopped
        infra_data["container_details"] = container_details
    except Exception as e:
        if not infra_data["error"]:
            infra_data["error"] = f"Docker connection failed: {str(e)}"
            
    # 1.5 Fetch ALL Host Ports using psutil
    try:
        conns = psutil.net_connections(kind='inet')
        listening = [c for c in conns if c.status == 'LISTEN']
        active_ports = []
        seen_ports = set()
        for c in listening:
            port = c.laddr.port
            if port not in seen_ports:
                seen_ports.add(port)
                proc_name = "Unknown"
                if c.pid:
                    try:
                        proc_name = psutil.Process(c.pid).name()
                    except psutil.NoSuchProcess:
                        pass
                is_proc_protected = any(p in proc_name.lower() for p in PROTECTED_PROCESSES)
                active_ports.append({
                    "port": str(port),
                    "service": proc_name,
                    "pid": c.pid,
                    "is_protected": (port in PROTECTED_PORTS) or is_proc_protected
                })
        infra_data["active_ports"] = sorted(active_ports, key=lambda x: int(x["port"]))
    except Exception as e:
        if not infra_data["error"]:
            infra_data["error"] = f"Host ports read failed: {str(e)}"
        
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

@app.post("/api/ports/{port}/kill")
def kill_port(port: int):
    if port in PROTECTED_PORTS:
        return {"status": "error", "message": f"Action Denied: Port {port} is a critical system port and cannot be killed."}
    try:
        conns = psutil.net_connections(kind='inet')
        for c in conns:
            if c.laddr.port == port and c.status == 'LISTEN':
                if c.pid:
                    proc = psutil.Process(c.pid)
                    proc_name = proc.name()
                    if any(p in proc_name.lower() for p in PROTECTED_PROCESSES):
                        return {"status": "error", "message": f"Action Denied: Process '{proc_name}' is a critical system process and cannot be killed."}
                    proc.terminate()
                    return {"status": "success", "message": f"Killed process {proc_name} (PID: {c.pid}) on port {port}"}
        return {"status": "error", "message": f"No process found listening on port {port}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/logs")
def get_system_logs():
    try:
        # Fetch kernel ring buffer logs
        result = subprocess.run(['dmesg', '-T'], capture_output=True, text=True, timeout=2)
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')[-50:]
            return {"logs": lines}
        else:
            # Fallback to simple simulated backend log if dmesg requires root and we don't have it
            return {"logs": ["Failed to read dmesg. Insufficient permissions."]}
    except Exception as e:
        return {"logs": [f"Error fetching logs: {str(e)}"]}
