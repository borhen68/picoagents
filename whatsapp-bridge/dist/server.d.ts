/**
 * WebSocket server for Python-Node.js bridge communication.
 * Security: binds to 127.0.0.1 only; optional BRIDGE_TOKEN auth.
 */
export declare class BridgeServer {
    private port;
    private authDir;
    private token?;
    private wss;
    private wa;
    private clients;
    constructor(port: number, authDir: string, token?: string | undefined);
    start(): Promise<void>;
    private setupClient;
    private handleCommand;
    private broadcast;
    stop(): Promise<void>;
}
