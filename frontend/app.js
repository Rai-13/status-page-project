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
    
    for (let i = 0; i < 4; i++) {
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
    
    if (!services || services.length === 0) {
        grid.innerHTML = '<div class="loading">No system metrics found.</div>';
        return;
    }

    // Filter to only our system metrics
    const systemMetrics = services.filter(s => ['CPU_Usage', 'RAM_Usage', 'Disk_Usage', 'Battery'].includes(s.service_name));

    // Clear grid only if it contains skeletons or loading
    if (grid.querySelector('.skeleton') || grid.querySelector('.loading')) {
        grid.innerHTML = '';
    }

    systemMetrics.forEach((metric, index) => {
        let card = document.getElementById(`metric-${metric.service_name}`);
        let isNew = false;
        if (!card) {
            card = document.createElement('div');
            card.id = `metric-${metric.service_name}`;
            card.className = `metric-card stagger-enter`;
            card.style.animationDelay = `${index * 0.1}s`;
            isNew = true;
        }
        
        const usage = metric.response_time_ms;
        
        let colorClass = "healthy";
        let strokeColor = "#10b981"; // green
        
        if (metric.service_name === 'Battery') {
            if (usage <= 20) { colorClass = "critical"; strokeColor = "#ef4444"; }
            else if (usage <= 50) { colorClass = "warning"; strokeColor = "#f59e0b"; }
        } else {
            if (usage >= 80) { colorClass = "warning"; strokeColor = "#f59e0b"; }
            if (usage >= 95) { colorClass = "critical"; strokeColor = "#ef4444"; }
        }

        let nameDisplay = metric.service_name.replace("_", " ");
        if (metric.service_name === 'Battery' && metric.error_message) {
            nameDisplay += ` <span style="font-size:0.8rem; color:var(--text-secondary);">(${metric.error_message})</span>`;
        }
        
        const timeAgo = Math.floor((new Date() - new Date(metric.timestamp)) / 60000);
        const timeStr = timeAgo < 1 ? 'Just now' : `${timeAgo}m ago`;

        if (isNew) {
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
        } else {
            card.querySelector('.metric-title').innerHTML = nameDisplay;
            const fill = card.querySelector('.gauge-fill');
            fill.style.transition = 'stroke-dashoffset 0.5s ease-in-out, stroke 0.5s ease';
            fill.setAttribute('stroke', strokeColor);
            fill.setAttribute('stroke-dashoffset', 125.6 * (1 - usage/100));
            
            const gaugeValue = card.querySelector('.gauge-value');
            gaugeValue.className = `gauge-value ${colorClass}`;
            gaugeValue.textContent = `${usage}%`;
            
            card.querySelector('.metric-footer').textContent = `Last updated: ${timeStr}`;
        }
    });
}

function renderInfrastructure(infraData) {
    const hostGrid = document.getElementById('host-grid');
    const ecoGrid = document.getElementById('ecosystem-grid');

    if (!infraData) {
        hostGrid.innerHTML = '<div class="infra-card"><div class="infra-label">Error</div><div class="infra-value error">Unable to load data</div></div>';
        return;
    }

    if (hostGrid.querySelector('.skeleton') || hostGrid.querySelector('.loading')) {
        hostGrid.innerHTML = '';
    }
    if (ecoGrid.querySelector('.skeleton') || ecoGrid.querySelector('.loading')) {
        ecoGrid.innerHTML = '';
    }

    if (infraData.error && infraData.error.includes("Docker")) {
        ecoGrid.innerHTML = `<div class="infra-card"><div class="infra-label">Docker Error</div><div class="infra-value error" style="font-size: 0.9rem">${infraData.error}</div></div>`;
    } else {
        const ecoCards = [
            { id: 'eco-containers', label: 'Active Containers', value: infraData.containers_running, subtext: `${infraData.containers_stopped} stopped` },
            { id: 'eco-db', label: 'Database Engine', value: infraData.db_engine, subtext: `v${infraData.db_version.split('.')[0]}` },
            { id: 'eco-k8s', label: 'Kubernetes Status', value: infraData.k8s_status, subtext: 'Cluster not reachable' }
        ];
        ecoCards.forEach((c, index) => {
            let div = document.getElementById(c.id);
            if (!div) {
                div = document.createElement('div');
                div.id = c.id;
                div.className = 'infra-card stagger-enter';
                div.style.animationDelay = `${0.5 + index * 0.1}s`;
                div.innerHTML = `
                    <div class="infra-label">${c.label}</div>
                    <div class="infra-value"><span>${c.value}</span> <span class="infra-subtext" style="${c.label === 'Kubernetes Status' ? 'color: var(--text-secondary)' : ''}">${c.subtext}</span></div>
                `;
                ecoGrid.appendChild(div);
            } else {
                div.querySelector('.infra-value span').textContent = c.value;
                div.querySelector('.infra-subtext').textContent = c.subtext;
            }
        });

        let portsDiv = document.getElementById('eco-ports');
        if (infraData.active_ports && infraData.active_ports.length > 0) {
            let portsHtml = '<div class="infra-label">Active Network Ports</div><div class="ports-list">';
            infraData.active_ports.forEach(p => {
                const svcName = p.service.replace('status-page-project-', '').replace('-1', '');
                portsHtml += `<div class="port-item"><span class="port-badge">${p.port}</span><span class="port-name">${svcName}</span></div>`;
            });
            portsHtml += '</div>';

            if (!portsDiv) {
                portsDiv = document.createElement('div');
                portsDiv.id = 'eco-ports';
                portsDiv.className = 'infra-card stagger-enter ports-card';
                portsDiv.style.animationDelay = `${0.5 + ecoCards.length * 0.1}s`;
                portsDiv.innerHTML = portsHtml;
                ecoGrid.appendChild(portsDiv);
            } else {
                portsDiv.innerHTML = portsHtml;
            }
        } else if (portsDiv) {
            portsDiv.remove();
        }
    }

    const hostCards = [
        { id: 'host-os', label: 'Operating System', value: infraData.os_info.split(' ')[0], subtext: infraData.os_info.split(' ')[1] || '' },
        { id: 'host-arch', label: 'Architecture', value: infraData.architecture, subtext: 'System' },
        { id: 'host-load', label: 'System Load', value: infraData.sys_load, subtext: '1m, 5m, 15m' },
        { id: 'host-netsent', label: 'Network Sent', value: `${infraData.net_sent_gb} GB`, subtext: 'Total Upload' },
        { id: 'host-netrecv', label: 'Network Recv', value: `${infraData.net_recv_gb} GB`, subtext: 'Total Download' },
        { id: 'host-disktotal', label: 'Disk Capacity', value: `${infraData.disk_total_gb} GB`, subtext: 'Total Space' },
        { id: 'host-diskfree', label: 'Disk Free', value: `${infraData.disk_free_gb} GB`, subtext: 'Available' },
        { id: 'host-cpucores', label: 'CPU Cores', value: infraData.cpu_cores, subtext: 'Logical' },
        { id: 'host-cpufreq', label: 'CPU Frequency', value: `${infraData.cpu_freq_mhz} MHz`, subtext: 'Current' },
        { id: 'host-ram', label: 'Total RAM', value: `${infraData.total_ram_gb} GB`, subtext: 'Physical' },
        { id: 'host-swap', label: 'Swap Memory', value: `${infraData.swap_memory_gb} GB`, subtext: 'Virtual' },
        { id: 'host-procs', label: 'Active Processes', value: infraData.active_processes, subtext: 'Running' },
        { id: 'host-uptime', label: 'Host Uptime', value: `${infraData.uptime_hours}h`, subtext: 'Continuous' }
    ];

    hostCards.forEach((c, index) => {
        let div = document.getElementById(c.id);
        if (!div) {
            div = document.createElement('div');
            div.id = c.id;
            div.className = 'infra-card stagger-enter';
            div.style.animationDelay = `${index * 0.08}s`;
            div.innerHTML = `
                <div class="infra-label">${c.label}</div>
                <div class="infra-value"><span>${c.value}</span> <span class="infra-subtext">${c.subtext}</span></div>
            `;
            hostGrid.appendChild(div);
        } else {
            div.querySelector('.infra-value span').textContent = c.value;
            div.querySelector('.infra-subtext').textContent = c.subtext;
        }
    });
}

function initTheme() {
    const themeToggle = document.getElementById('theme-toggle');
    if (!themeToggle) return;
    
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'light') {
        document.body.classList.add('light-mode');
        themeToggle.checked = true;
    }

    themeToggle.addEventListener('change', (e) => {
        if (e.target.checked) {
            document.body.classList.add('light-mode');
            localStorage.setItem('theme', 'light');
        } else {
            document.body.classList.remove('light-mode');
            localStorage.setItem('theme', 'dark');
        }
    });
}

async function refreshData() {
    const [statusData, infraData] = await Promise.all([
        fetchStatus(),
        fetchInfrastructure()
    ]);
    
    renderInfrastructure(infraData);

    if (statusData && statusData.services) {
        updateGlobalStatus(statusData.services);
        renderServices(statusData.services);
    }
}

async function init() {
    renderSkeletons();
    await new Promise(r => setTimeout(r, 600));
    await refreshData();
}

document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    init();
});

setInterval(refreshData, 5000);
