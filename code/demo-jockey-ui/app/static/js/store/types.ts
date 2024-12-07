/**
 * Brain Wave Collective  
 * https://brainwavecollective.ai
 * 
 *   Revolutionizing Video Creation with TwelveLabs Jockey and NVIDIA AI Workbench. 
 *   Saddle Stack (AKA Jockbench) is our submission to the Dell x NVIDIA HackAI Challenge
 *
 * File: types.ts
 * Created: 2024
 * Authors: Thienthanh Trinh & Daniel Ritchie
 *
 * Copyright (c) 2024 Brain Wave Collective
 */

// app/static/js/store/types.ts

export interface WebSocketOptions {
    endpoint: string;
    onMessage?: (data: any) => void;
    onError?: (error: string) => void;
    reconnectInterval?: number;
    maxReconnectAttempts?: number;
}

export interface ToolCall {
    name: string;
    args: Record<string, any>;
    id: string;
    type: string;
    output: any[];
}

export interface JockeyMetadata {
    next_worker?: string;
    made_plan?: boolean;
    active_plan?: string;
    [key: string]: any;
}

export interface JockeyMessage {
    content: string;
    type?: 'user' | 'assistant';
    response_metadata?: Record<string, any>;
}

export interface JockeyState {
    threadId: string | null;
    status: 'idle' | 'processing' | 'error';
    messages: JockeyMessage[];
    toolCalls: ToolCall[];
    metadata: JockeyMetadata;
    updateMetadata: (newMetadata: Partial<JockeyMetadata>) => void; 
}

export interface AppState {
    audio: AudioState;
    jockey: JockeyState;
}