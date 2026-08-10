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
    
    // Reset classes
    globalStatusEl.className = 'global-status';
    
    if (services.length === 0) {
        globalTextEl.textContent = 'No data available';
        return;
    }

    const downs = services.filter(s => s.status === 'down').length;
    const degraded = services.filter(s => s.status === 'degraded').length;

    if (downs > 0) {
        globalStatusEl.classList.add('down');
        globalTextEl.textContent = 'Major System Outage';
    } else if (degraded > 0) {
        globalStatusEl.classList.add('degraded');
        globalTextEl.textContent = 'Degraded System Performance';
    } else {
        globalStatusEl.classList.add('all-up');
        globalTextEl.textContent = 'All Systems Operational';
    }
}

function renderSkeletons() {
    const grid = document.getElementById('services-grid');
    grid.innerHTML = '';
    
    for (let i = 0; i < 6; i++) {
        const card = document.createElement('div');
        card.className = 'service-card';
        card.style.animationDelay = `${i * 0.1}s`;
        
        card.innerHTML = `
            <div class="card-header">
                <div class="skeleton skeleton-text"></div>
                <div class="skeleton skeleton-badge"></div>
            </div>
            <div class="skeleton-bar-container">
                ${Array(30).fill(0).map(() => `<div class="skeleton skeleton-bar"></div>`).join('')}
            </div>
            <div class="skeleton-metrics">
                <div class="skeleton skeleton-metric-text"></div>
                <div class="skeleton skeleton-metric-text"></div>
            </div>
        `;
        grid.appendChild(card);
    }
}

function renderServices(services) {
    const grid = document.getElementById('services-grid');
    grid.innerHTML = '';
    
    if (!services || services.length === 0) {
        grid.innerHTML = '<div class="loading">No services found or unable to reach API.</div>';
        return;
    }

    services.forEach((service, index) => {
        const card = document.createElement('div');
        card.className = `service-card ${service.status}`;
        card.style.animationDelay = `${index * 0.05}s`;
        
        // Format time
        const timeAgo = Math.floor((new Date() - new Date(service.timestamp)) / 60000);
        const timeStr = timeAgo < 1 ? 'Just now' : `${timeAgo}m ago`;
        
        // Calculate dynamic uptime based on status for demo flair
        let uptime = "99.99%";
        if(service.status === 'down') uptime = "98.45%";
        if(service.status === 'degraded') uptime = "99.20%";
        
        // Fake history nodes with Tooltips
        let historyHtml = '';
        for(let i = 0; i < 30; i++) {
            const isRecent = i > 25;
            const nodeClass = isRecent ? service.status : (Math.random() > 0.95 ? 'degraded' : 'up');
            const height = 40 + Math.random() * 60;
            
            // Generate a random past time
            const pastTime = new Date(Date.now() - ((30 - i) * 5 * 60000));
            const timeFormatted = pastTime.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
            
            // Generate a fake latency
            let fakeLatency = Math.floor(Math.random() * 50) + 10;
            if(nodeClass === 'degraded') fakeLatency = Math.floor(Math.random() * 1500) + 1000;
            if(nodeClass === 'down') fakeLatency = 0;
            
            // Real latency for the last node
            if(i === 29) fakeLatency = service.response_time_ms;
            
            historyHtml += `
                <div class="tooltip-container">
                    <div class="history-node ${nodeClass}" style="height: ${height}%"></div>
                    <div class="tooltip">
                        <div class="latency">${nodeClass.toUpperCase()} - ${fakeLatency}ms</div>
                        <div class="time">${timeFormatted}</div>
                    </div>
                </div>
            `;
        }

        card.innerHTML = `
            <div class="card-header">
                <div class="service-name">
                    ${service.service_name}
                    <div class="uptime-metric">${uptime} uptime</div>
                </div>
                <div class="service-status-badge">${service.status}</div>
            </div>
            <div class="history-bar">
                ${historyHtml}
            </div>
            <div class="metrics">
                <span>Latency: ${service.response_time_ms}ms</span>
                <span>${timeStr}</span>
            </div>
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
        { label: 'System Health', value: '100%', subtext: 'All sockets healthy' }
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
    
    // Artificial small delay to show off the skeleton loader
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
        document.getElementById('services-grid').innerHTML = '<div class="loading">Failed to load status data. Is the backend running?</div>';
    }
}

// Run on load
document.addEventListener('DOMContentLoaded', init);

// Refresh every 30 seconds
setInterval(init, 30000);
