/**
 * WhatsApp client wrapper using Baileys.
 * Based on OpenClaw's working implementation.
 */
export interface InboundMessage {
    id: string;
    sender: string;
    pn: string;
    content: string;
    timestamp: number;
    isGroup: boolean;
}
export interface WhatsAppClientOptions {
    authDir: string;
    onMessage: (msg: InboundMessage) => void;
    onQR: (qr: string) => void;
    onStatus: (status: string) => void;
}
export declare class WhatsAppClient {
    private sock;
    private options;
    private reconnecting;
    constructor(options: WhatsAppClientOptions);
    connect(): Promise<void>;
    private extractMessageContent;
    sendMessage(to: string, text: string): Promise<void>;
    disconnect(): Promise<void>;
}
