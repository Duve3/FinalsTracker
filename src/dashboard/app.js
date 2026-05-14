class FinalsDashboard {
    constructor() {
        this.ws = null;
        this.reconnectTimer = null;
        this.connect();
        document.getElementById('btn-force-ingame').addEventListener('click', () => {
            this.send({ action: 'force_ingame' });
            document.getElementById('midgame-notification').style.display = 'none';
        });
    }

    connect() {
        if (this.ws) return;
        const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${location.host}/ws`;
        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
            document.getElementById('status-badge').textContent = 'connected';
            document.getElementById('status-badge').className = 'status-badge connected';
        };

        this.ws.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);
                this.handleMessage(msg);
            } catch (e) {
                console.error('Failed to parse message:', e);
            }
        };

        this.ws.onclose = () => {
            document.getElementById('status-badge').textContent = 'disconnected';
            document.getElementById('status-badge').className = 'status-badge';
            this.ws = null;
            this.reconnectTimer = setTimeout(() => this.connect(), 3000);
        };

        this.ws.onerror = () => {
            this.ws.close();
        };
    }

    send(data) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(data));
        }
    }

    handleMessage(msg) {
        switch (msg.type) {
            case 'match_update':
                this.updateLiveMatch(msg.data);
                break;
            case 'session_summary':
                this.updateSessionSummary(msg.data);
                break;
            case 'match_history':
                this.updateMatchHistory(msg.data);
                break;
            case 'state_change':
                this.updateState(msg.data.state);
                if (msg.data.state === 'ingame') {
                    this.dismissNotification('Tracking');
                }
                break;
            case 'career_stats':
                this.updateCareerStats(msg.data);
                break;
            case 'game_detected':
                this.showNotification('Game HUD detected. Confirm to start tracking?');
                break;
        }
    }

    showNotification(text) {
        const el = document.getElementById('midgame-notification');
        if (!el) return;
        const span = el.querySelector('span');
        if (span) span.textContent = text;
        el.style.display = 'flex';
    }

    dismissNotification(text) {
        const el = document.getElementById('midgame-notification');
        if (!el) return;
        const span = el.querySelector('span');
        if (span) span.textContent = text || 'Tracking';
        document.getElementById('btn-force-ingame').textContent = 'Dismiss';
    }

    updateLiveMatch(data) {
        const fields = {
            'stat-kills': data.kills,
            'stat-deaths': data.deaths,
            'stat-assists': data.assists,
            'stat-combat': this.fmtNum(data.combat_score),
            'stat-support': this.fmtNum(data.support_score),
            'stat-objective': this.fmtNum(data.objective_score),
            'stat-revives': data.revives,
            'stat-cash': data.team_cash != null ? `$${this.fmtNum(data.team_cash)}` : '-',
        };
        for (const [id, val] of Object.entries(fields)) {
            const el = document.getElementById(id);
            if (el && val != null) el.textContent = val;
        }
    }

    updateSessionSummary(summary) {
        if (!summary || !summary.matches_played) {
            document.getElementById('session-stats').innerHTML =
                '<p>No matches recorded yet</p>';
            return;
        }
        const rows = [
            ['Matches', summary.matches_played],
            ['Wins', summary.wins],
            ['Losses', summary.losses],
            ['Win Rate', `${summary.win_rate}%`],
            ['Total Kills', summary.total_kills],
            ['Avg Kills', summary.avg_kills],
            ['Avg Deaths', summary.avg_deaths],
            ['Avg Combat', summary.avg_combat_score],
            ['Avg Support', summary.avg_support_score],
            ['Avg Objective', summary.avg_objective_score],
            ['Session', `${summary.session_duration_h}h`],
        ];
        const html = rows.map(([label, value]) =>
            `<div class="stat-row"><span class="label">${label}</span><span class="value">${value}</span></div>`
        ).join('');
        document.getElementById('session-stats').innerHTML = html;
    }

    updateMatchHistory(matches) {
        const tbody = document.getElementById('history-body');
        if (!matches || matches.length === 0) {
            tbody.innerHTML = '<tr><td colspan="9">No matches yet</td></tr>';
            return;
        }
        const rows = matches.map(m => {
            const resultClass = m.result === 'win' ? 'result-win' :
                                m.result === 'loss' ? 'result-loss' : '';
            const time = this.fmtTime(m.timestamp);
            const duration = m.duration_sec ? `${Math.round(m.duration_sec / 60)}m` : '-';
            return `<tr>
                <td>${time}</td>
                <td class="${resultClass}">${m.result || '-'}</td>
                <td>${m.kills ?? '-'}</td>
                <td>${m.deaths ?? '-'}</td>
                <td>${m.assists ?? '-'}</td>
                <td>${this.fmtNum(m.combat_score)}</td>
                <td>${this.fmtNum(m.support_score)}</td>
                <td>${this.fmtNum(m.objective_score)}</td>
                <td>${duration}</td>
            </tr>`;
        }).join('');
        tbody.innerHTML = rows;
    }

    updateState(state) {
        const el = document.getElementById('state-text');
        const dot = document.querySelector('.dot');
        if (el) el.textContent = `State: ${state}`;
        if (dot) {
            dot.className = 'dot';
            if (['ingame', 'scoreboard'].includes(state)) dot.classList.add(state);
        }
    }

    updateCareerStats(stats) {
        // career stats are shown in a future feature expansion
    }

    fmtNum(n) {
        if (n == null) return '-';
        return Number(n).toLocaleString();
    }

    fmtTime(ts) {
        if (!ts) return '-';
        const d = new Date(ts * 1000);
        return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }
}

new FinalsDashboard();
