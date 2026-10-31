/**
 * WebSocket client — manages the voice session connection.
 *
 * Responsibilities:
 * - Connect/disconnect with automatic reconnection
 * - Send typed messages and binary audio chunks
 * - Heartbeat (ping/pong) to detect stale connections
 * - Event callbacks for message routing
 * - Binary/text frame multiplexing
 *
 * Architecture:
 * - Browser sends binary frames (audio) and JSON frames (control)
 * - Server responds with binary frames (TTS audio) and JSON frames (events)
 */

import type { WSMessage } from "@/types/voice";

export type WSEventHandler = (message: WSMessage) => void;
export type WSBinaryHandler = (data: ArrayBuffer) => void;
export type WSStateHandler = (state: "connecting" | "connected" | "disconnected" | "error") => void;

interface WebSocketClientConfig {
  url: string;
  onMessage?: WSEventHandler;
  onBinary?: WSBinaryHandler;
  onStateChange?: WSStateHandler;
  reconnect?: boolean;
  maxReconnectAttempts?: number;
  reconnectIntervalMs?: number;
  heartbeatIntervalMs?: number;
}

export class WebSocketClient {
  private ws: WebSocket | null = null;
  private config: Required<WebSocketClientConfig>;
  private reconnectAttempts = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  private _sessionId: string | null = null;

  constructor(config: WebSocketClientConfig) {
    this.config = {
      reconnect: true,
      maxReconnectAttempts: 5,
      reconnectIntervalMs: 2000,
      heartbeatIntervalMs: 10000,
      onMessage: () => {},
      onBinary: () => {},
      onStateChange: () => {},
      ...config,
    };
  }

  get sessionId(): string | null {
    return this._sessionId;
  }

  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN) return;

    this.config.onStateChange("connecting");

    try {
      this.ws = new WebSocket(this.config.url);
      this.ws.binaryType = "arraybuffer";

      // Receive binary frames as ArrayBuffer (not Blob)
      this.ws.binaryType = "arraybuffer";

      this.ws.onopen = () => {
        this.reconnectAttempts = 0;
        this.config.onStateChange("connected");
        this.startHeartbeat();
      };

      this.ws.onmessage = (event: MessageEvent) => {
        if (event.data instanceof ArrayBuffer) {
          // Binary frame — TTS audio from server
          this.config.onBinary(event.data);
          return;
        }

        if (event.data instanceof Blob) {
          // Fallback: convert Blob to ArrayBuffer
          event.data.arrayBuffer().then((buf) => this.config.onBinary(buf));
          return;
        }

        // Text frame — JSON control message
        try {
          const message: WSMessage = JSON.parse(event.data);

          // Track session ID from server
          if (message.session_id) {
            this._sessionId = message.session_id;
          }

          this.config.onMessage(message);
        } catch (e) {
          console.error("[WS] Failed to parse message:", e);
        }
      };

      this.ws.onclose = (event) => {
        this.stopHeartbeat();
        this.config.onStateChange("disconnected");

        if (this.config.reconnect && !event.wasClean) {
          this.scheduleReconnect();
        }
      };

      this.ws.onerror = () => {
        this.config.onStateChange("error");
      };
    } catch (error) {
      console.error("[WS] Connection failed:", error);
      this.config.onStateChange("error");
      this.scheduleReconnect();
    }
  }

  disconnect(): void {
    this.config.reconnect = false;
    this.stopHeartbeat();
    this.clearReconnectTimer();

    if (this.ws) {
      // Send end_session before closing
      this.sendJSON({
        type: "end_session",
        session_id: this._sessionId || "",
        data: {},
      });

      this.ws.close(1000, "client_disconnect");
      this.ws = null;
    }

    this._sessionId = null;
    this.config.onStateChange("disconnected");
  }

  /**
   * Send a JSON control message.
   */
  sendJSON(message: WSMessage): void {
    if (!this.isConnected || !this.ws) return;
    this.ws.send(JSON.stringify(message));
  }

  /**
   * Send binary audio data.
   */
  sendAudio(audioData: ArrayBuffer): void {
    if (!this.isConnected || !this.ws) return;
    this.ws.send(audioData);
  }

  // ---- Heartbeat ----

  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.heartbeatTimer = setInterval(() => {
      if (this.isConnected) {
        this.sendJSON({
          type: "ping",
          session_id: this._sessionId || "",
          data: { client_time: Date.now() },
        });
      }
    }, this.config.heartbeatIntervalMs);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  // ---- Reconnection ----

  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.config.maxReconnectAttempts) {
      console.error("[WS] Max reconnect attempts reached");
      this.config.onStateChange("error");
      return;
    }

    const delay = this.config.reconnectIntervalMs * Math.pow(2, this.reconnectAttempts);
    this.reconnectAttempts++;

    console.log(`[WS] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);

    this.reconnectTimer = setTimeout(() => {
      this.connect();
    }, delay);
  }

  private clearReconnectTimer(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }
}
