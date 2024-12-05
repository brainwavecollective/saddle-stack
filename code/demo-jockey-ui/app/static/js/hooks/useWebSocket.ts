// app/static/js/hooks/useWebSocket.ts
import { useRef, useState, useEffect, useCallback } from 'react';

export const useWebSocket = ({
    endpoint,
    onMessage,
    onError,
    reconnectInterval = 3000,
    maxReconnectAttempts = 5
}: WebSocketOptions) => {
    const wsRef = useRef<WebSocket | null>(null);
    const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
    const [status, setStatus] = useState<'connected' | 'disconnected' | 'error'>('disconnected');
    const [attempts, setAttempts] = useState(0);

    const connect = useCallback(() => {
        if (reconnectTimeoutRef.current) {
            clearTimeout(reconnectTimeoutRef.current);
            reconnectTimeoutRef.current = null;
        }

        if (wsRef.current?.readyState === WebSocket.OPEN) {
            console.log('[WebSocket] Already connected');
            return;
        }

        try {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const ws = new WebSocket(`${protocol}//${window.location.host}${endpoint}`);
            wsRef.current = ws;

            ws.onopen = () => {
                console.log('[WebSocket] Connected to:', endpoint);
                setStatus('connected');
                setAttempts(0);
            };

            ws.onmessage = (event) => {
                try {
                    // Handle binary data (audio chunks)
                    if (event.data instanceof Blob) {
                        console.log('[WebSocket] Received binary chunk:', event.data.size, 'bytes');
                        onMessage?.(event.data);
                        return;
                    }

                    // Handle text/JSON messages
                    if (typeof event.data === 'string') {
                        try {
                            const data = JSON.parse(event.data);
                            console.log('[WebSocket] Received message:', data);
                            onMessage?.(data);
                        } catch (err) {
                            console.error('[WebSocket] Failed to parse message:', err);
                        }
                        return;
                    }

                    console.warn('[WebSocket] Received unknown data type:', typeof event.data);
                } catch (err) {
                    console.error('[WebSocket] Error processing message:', err);
                    onError?.('Failed to process message');
                }
            };

            ws.onerror = (error) => {
                console.error('[WebSocket] Error:', error);
                setStatus('error');
                onError?.('WebSocket connection error');
            };

            ws.onclose = (event) => {
                console.log('[WebSocket] Closed with code:', event.code);
                setStatus('disconnected');
                wsRef.current = null;

                if (event.code === 1000) return;

                setAttempts((prev) => {
                    const newAttempts = prev + 1;
                    if (newAttempts < maxReconnectAttempts) {
                        const delay = Math.min(1000 * Math.pow(2, prev), reconnectInterval);
                        console.log(`[WebSocket] Reconnecting in ${delay}ms (attempt ${newAttempts})`);
                        reconnectTimeoutRef.current = setTimeout(connect, delay);
                    }
                    return newAttempts;
                });
            };
        } catch (error) {
            console.error('[WebSocket] Creation error:', error);
            onError?.('Failed to create connection');
        }
    }, [endpoint, onMessage, onError, reconnectInterval, maxReconnectAttempts]);

    useEffect(() => {
        connect();
        return () => {
            if (reconnectTimeoutRef.current) {
                clearTimeout(reconnectTimeoutRef.current);
            }
            if (wsRef.current) {
                wsRef.current.close();
            }
        };
    }, [connect]);

    return { wsRef, status, attempts };
};