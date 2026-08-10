const API_BASE_URL = 'http://localhost:8000/api';

async function fetchStatus() {
    try {
        const response = await fetch(`${API_BASE_URL}/status`);
        if (!response.ok) throw new Error('Network response was not ok');
        return await response.json();
    } catch (error) {
        console.error('Error fetching status:', error);
        return null;
    }
}

async function fetchInfrastructure() {
    try {
        const response = await fetch(`${API_BASE_URL}/infrastructure`);
        if (!response.ok) throw new Error('Network response was not ok');
        return await response.json();
    } catch (error) {
        console.error('Error fetching infra:', error);
        return null;
    }
}

function updateGlobalStatus(services) {
    const globalStatusEl = document.getElementById('global-status');
    const globalTextEl = globalStatusEl.querySelector('.status-text');
    
    globalStatusEl.className = 'global-status';
    
    if (services.length === 0) {
        globalTextEl.textContent = 'No data available';
        return;
    }

    const downs = services.filter(s => s.status === 'down').length;
    const degraded = services.filter(s => s.status === 'degraded').length;

    if (downs > 0) {
        globalStatusEl.classList.add('down');
        globalTextEl.textContent = 'Critical Resource Exhaustion';
    } else if (degraded > 0) {
        globalStatusEl.classList.add('degraded');
        globalTextEl.textContent = 'High Resource Usage Detected';
    } else {
        globalStatusEl.classList.add('all-up');
        globalTextEl.textContent = 'System Healthy';
    }
}

function renderSkeletons() {
    const grid = document.getElementById('metrics-grid');
    grid.innerHTML = '';
    
    for (let i = 0; i < 3; i++) {
        const card = document.createElement('div');
        card.className = 'metric-card';
        card.innerHTML = `
            <div class="skeleton skeleton-text" style="width: 50%; margin-bottom: 2rem;"></div>
            <div class="skeleton" style="width: 150px; height: 150px; border-radius: 50%; margin: 0 auto;"></div>
        `;
        grid.appendChild(card);
    }
}

function renderServices(services) {
    const grid = document.getElementById('metrics-grid');
    grid.innerHTML = '';
    
    if (!services || services.length === 0) {
        grid.innerHTML = '<div class="loading">No system metrics found.</div>';
        return;
    }

    // Filter to only our system metrics
    const systemMetrics = services.filter(s => ['CPU_Usage', 'RAM_Usage', 'Disk_Usage'].includes(s.service_name));

    systemMetrics.forEach((metric, index) => {
        const card = document.createElement('div');
        card.className = `metric-card`;
        
        // usage is packed in response_time_ms
        const usage = metric.response_time_ms;
        
        let colorClass = "healthy";
        let strokeColor = "#10b981"; // green
        if (usage >= 80) {
            colorClass = "warning";
            strokeColor = "#f59e0b"; // yellow
        }
        if (usage >= 95) {
            colorClass = "critical";
            strokeColor = "#ef4444"; // red
        }

        const nameDisplay = metric.service_name.replace("_", " ");
        const timeAgo = Math.floor((new Date() - new Date(metric.timestamp)) / 60000);
        const timeStr = timeAgo < 1 ? 'Just now' : `${timeAgo}m ago`;

        card.innerHTML = `
            <div class="metric-title">${nameDisplay}</div>
            <div class="gauge-container">
                <svg viewBox="0 0 100 50" class="gauge">
                    <path class="gauge-bg" d="M 10,50 A 40,40 0 0,1 90,50" />
                    <path class="gauge-fill" stroke="${strokeColor}" stroke-dasharray="125.6" stroke-dashoffset="${125.6 * (1 - usage/100)}" d="M 10,50 A 40,40 0 0,1 90,50" />
                </svg>
                <div class="gauge-value ${colorClass}">${usage}%</div>
            </div>
            <div class="metric-footer">Last updated: ${timeStr}</div>
        `;
        
        grid.appendChild(card);
    });
}

function renderInfrastructure(infraData) {
    const grid = document.getElementById('infra-grid');
    grid.innerHTML = '';

    if (!infraData) {
        grid.innerHTML = '<div class="infra-card"><div class="infra-label">Error</div><div class="infra-value error">Unable to load data</div></div>';
        return;
    }

    if (infraData.error) {
        grid.innerHTML = `<div class="infra-card"><div class="infra-label">Docker/DB Error</div><div class="infra-value error" style="font-size: 0.9rem">${infraData.error}</div></div>`;
        return;
    }

    const cards = [
        { label: 'Active Containers', value: infraData.containers_running, subtext: `${infraData.containers_stopped} stopped` },
        { label: 'Database Engine', value: infraData.db_engine, subtext: `v${infraData.db_version.split('.')[0]}` },
        { label: 'Monitoring Agent', value: 'Active', subtext: 'PID: host' }
    ];

    cards.forEach(c => {
        const div = document.createElement('div');
        div.className = 'infra-card';
        div.innerHTML = `
            <div class="infra-label">${c.label}</div>
            <div class="infra-value">${c.value} <span class="infra-subtext">${c.subtext}</span></div>
        `;
        grid.appendChild(div);
    });
}

async function init() {
    renderSkeletons();
    
    await new Promise(r => setTimeout(r, 600));
    
    const [statusData, infraData] = await Promise.all([
        fetchStatus(),
        fetchInfrastructure()
    ]);
    
    renderInfrastructure(infraData);

    if (statusData && statusData.services) {
        updateGlobalStatus(statusData.services);
        renderServices(statusData.services);
    } else {
        updateGlobalStatus([]);
        document.getElementById('metrics-grid').innerHTML = '<div class="loading">Failed to load system metrics.</div>';
    }
}

document.addEventListener('DOMContentLoaded', init);
setInterval(init, 30000);
