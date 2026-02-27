/**
 * WebSocket server for Python-Node.js bridge communication.
 * Security: binds to 127.0.0.1 only; optional BRIDGE_TOKEN auth.
 */
import { WebSocketServer, WebSocket } from 'ws';
import { WhatsAppClient } from './whatsapp.js';
export class BridgeServer {
    port;
    authDir;
    token;
    wss = null;
    wa = null;
    clients = new Set();
    constructor(port, authDir, token) {
        this.port = port;
        this.authDir = authDir;
        this.token = token;
    }
    async start() {
        // Bind to localhost only — never expose to external network
        this.wss = new WebSocketServer({ host: '127.0.0.1', port: this.port });
        console.log(`🌉 Bridge server listening on ws://127.0.0.1:${this.port}`);
        if (this.token)
            console.log('🔒 Token authentication enabled');
        // Initialize WhatsApp client
        this.wa = new WhatsAppClient({
            authDir: this.authDir,
            onMessage: (msg) => this.broadcast({ type: 'message', ...msg }),
            onQR: (qr) => this.broadcast({ type: 'qr', qr }),
            onStatus: (status) => this.broadcast({ type: 'status', status }),
        });
        // Handle WebSocket connections
        this.wss.on('connection', (ws) => {
            if (this.token) {
                // Require auth handshake as first message
                const timeout = setTimeout(() => ws.close(4001, 'Auth timeout'), 5000);
                ws.once('message', (data) => {
                    clearTimeout(timeout);
                    try {
                        const msg = JSON.parse(data.toString());
                        if (msg.type === 'auth' && msg.token === this.token) {
                            console.log('🔗 Python client authenticated');
                            this.setupClient(ws);
                        }
                        else {
                            ws.close(4003, 'Invalid token');
                        }
                    }
                    catch {
                        ws.close(4003, 'Invalid auth message');
                    }
                });
            }
            else {
                console.log('🔗 Python client connected');
                this.setupClient(ws);
            }
        });
        // Connect to WhatsApp
        await this.wa.connect();
    }
    setupClient(ws) {
        this.clients.add(ws);
        ws.on('message', async (data) => {
            try {
                const cmd = JSON.parse(data.toString());
                await this.handleCommand(cmd);
                ws.send(JSON.stringify({ type: 'sent', to: cmd.to }));
            }
            catch (error) {
                console.error('Error handling command:', error);
                ws.send(JSON.stringify({ type: 'error', error: String(error) }));
            }
        });
        ws.on('close', () => {
            console.log('🔌 Python client disconnected');
            this.clients.delete(ws);
        });
        ws.on('error', (error) => {
            console.error('WebSocket error:', error);
            this.clients.delete(ws);
        });
    }
    async handleCommand(cmd) {
        if (cmd.type === 'send' && this.wa) {
            await this.wa.sendMessage(cmd.to, cmd.text);
        }
    }
    broadcast(msg) {
        const data = JSON.stringify(msg);
        for (const client of this.clients) {
            if (client.readyState === WebSocket.OPEN) {
                client.send(data);
            }
        }
    }
    async stop() {
        // Close all client connections
        for (const client of this.clients) {
            client.close();
        }
        this.clients.clear();
        // Close WebSocket server
        if (this.wss) {
            this.wss.close();
            this.wss = null;
        }
        // Disconnect WhatsApp
        if (this.wa) {
            await this.wa.disconnect();
            this.wa = null;
        }
    }
}
