/**
 * WebSocket client for real-time progress updates.
 */
const WS = {
    _ws: null,
    _handlers: [],
    _reconnectDelay: 1000,

    connect() {
        const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
        this._ws = new WebSocket(`${proto}//${location.host}/ws/progress`);

        this._ws.onmessage = (e) => {
            try {
                const data = JSON.parse(e.data);
                for (const fn of this._handlers) fn(data);
            } catch(err) { console.error('WS parse error:', err); }
        };

        this._ws.onclose = () => {
            setTimeout(() => this.connect(), this._reconnectDelay);
        };

        this._ws.onerror = () => this._ws.close();
    },

    onMessage(fn) { this._handlers.push(fn); },
};
