/**
 * Brain Wave Collective  
 * https://brainwavecollective.ai
 * 
 *   Revolutionizing Video Creation with TwelveLabs Jockey and NVIDIA AI Workbench. 
 *   Jockbench is our submission to the Dell x NVIDIA HackAI Challenge
 *
 * File: index.ts
 * Created: 2024
 * Authors: Thienthanh Trinh & Daniel Ritchie
 *
 * Copyright (c) 2024 Brain Wave Collective
 */

// app/static/js/store/index.ts

import { create } from 'zustand';
import { AppState } from './types';

export const useStore = create<AppState>((set) => ({
    audio: {
        isPlaying: false,
        volume: 1,
        currentTime: 0,
        duration: 0
    },
    jockey: {
        threadId: null,
        status: 'idle',
        messages: [],
        toolCalls: [], 
        metadata: {}, 
        updateMetadata: (newMetadata) => set((state) => ({ 
            jockey: {
                ...state.jockey,
                metadata: {
                    ...state.jockey.metadata,
                    ...newMetadata
                }
            }
        }))
    }
}));