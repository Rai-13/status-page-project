const express = require('express');
const app = express();

app.get('/health', (req, res) => {
    // Jittery latency between 50ms and 800ms
    const delay = Math.floor(Math.random() * 750) + 50;
    
    setTimeout(() => {
        res.json({
            status: 'ok',
            service: 'email',
            queue_depth: Math.floor(Math.random() * 100)
        });
    }, delay);
});

app.listen(8003, () => {
    console.log('Email service running on port 8003');
});
