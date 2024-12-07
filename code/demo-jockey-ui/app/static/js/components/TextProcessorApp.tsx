/**
 * Brain Wave Collective  
 * https://brainwavecollective.ai
 * 
 *   Revolutionizing Video Creation with TwelveLabs Jockey and NVIDIA AI Workbench. 
 *   Jockbench is our submission to the Dell x NVIDIA HackAI Challenge
 *
 * File: TextProcessorApp.tsx
 * Created: 2024
 * Authors: Thienthanh Trinh & Daniel Ritchie
 *
 * Copyright (c) 2024 Brain Wave Collective
 */

// app/static/js/components/TextProcessorApp.tsx

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Play, Pause, Square, Loader } from 'lucide-react';
import { useStore } from '../store';
import VideoPlayer from './VideoPlayer';

interface Window {
  AudioContext: typeof AudioContext;
  webkitAudioContext: typeof AudioContext;
}

interface DisplayMessage {
  text: string;
  type: 'system' | 'human' | 'ai' | 'error';
  name?: string;
  data?: string; 
}

interface ToolCall {
  name: string;
  args: Record<string, any>;
  id: string;
  type: string;
  output: any[];
}

const AUDIO_ASSETS_PATH = '/assets/audio';
const backgroundFiles = [
  `${AUDIO_ASSETS_PATH}/bg1.mp3`,
  `${AUDIO_ASSETS_PATH}/bg2.mp3`,
  `${AUDIO_ASSETS_PATH}/bg3.mp3`
];

const useAudioPlayer = () => {
  const audioContextRef = useRef<AudioContext | null>(null);
  const musicRef = useRef<HTMLAudioElement | null>(null);
  
  const [isAudioInitialized, setIsAudioInitialized] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [musicVolume, setmusicVolume] = useState(0.03);
  
  const fadeTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const initializeAudioContext = async () => {
    try {
      if (!audioContextRef.current) {
        audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)();
      }

      if (audioContextRef.current.state === 'suspended') {
        await audioContextRef.current.resume();
      }

      setIsAudioInitialized(true);
    } catch (error) {
      console.error('[Audio] Failed to initialize AudioContext:', error);
    }
  };

  const playMusic = useCallback(async (musicUrl: string) => {
    try {
      await initializeAudioContext();

      if (musicRef.current) {
        musicRef.current.pause();
        musicRef.current.currentTime = 0;
      }

      musicRef.current = new Audio(musicUrl);
      musicRef.current.loop = true;
      musicRef.current.volume = musicVolume;

      await musicRef.current.play();
      setIsPlaying(true);
    } catch (error) {
      console.error('[Music] Error during playback:', error);
    }
  }, [musicVolume]);

  const stopMusic = useCallback(() => {
    if (musicRef.current) {
      musicRef.current.pause();
      musicRef.current.currentTime = 0;
    }
    setIsPlaying(false);
  }, []);

  const updateMusicVolume = useCallback((volume: number) => {
    setmusicVolume(volume);
    if (musicRef.current) {
      musicRef.current.volume = volume;
    }
  }, []);
  
  const fadeOutMusic = useCallback((delaySeconds: number = 0.1, fadeSeconds: number = 2) => {
    if (musicRef.current) {
      if (fadeTimeoutRef.current) {
        clearTimeout(fadeTimeoutRef.current);
      }

      fadeTimeoutRef.current = setTimeout(() => {
        if (!musicRef.current) return;
        
        const originalVolume = musicRef.current.volume;
        const startTime = Date.now();
        const fadeInterval = 225;
        
        const fadeStep = () => {
          const elapsedTime = (Date.now() - startTime) / 1000;
          if (elapsedTime >= fadeSeconds) {
            if (musicRef.current) {
              musicRef.current.pause();
              musicRef.current.currentTime = 0;
              musicRef.current.volume = originalVolume;
            }
            setIsPlaying(false);
            return;
          }
          
          if (musicRef.current) {
            const newVolume = originalVolume * (1 - (elapsedTime / fadeSeconds));
            musicRef.current.volume = Math.max(0, newVolume);
            requestAnimationFrame(fadeStep);
          }
        };
        
        requestAnimationFrame(fadeStep);
      }, delaySeconds * 1000);
    }
  }, []);
  
  useEffect(() => {
    return () => {
      if (fadeTimeoutRef.current) {
        clearTimeout(fadeTimeoutRef.current);
      }
      if (audioContextRef.current) {
        audioContextRef.current.close();
      }
      if (musicRef.current) {
        musicRef.current.pause();
      }
    };
  }, []);

  return {
    playMusic,
    stopMusic,
    fadeOutMusic,
    updateMusicVolume,
    isAudioInitialized,
    isPlaying,
    musicVolume,
  };
};

export const TextProcessorApp: React.FC = () => {
  const [text, setText] = useState('');
  const [threadId, setThreadId] = useState<string | null>(null); 
  const [indexId, setIndexId] = useState(import.meta.env.VITE_TWELVE_LABS_INDEX_ID);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [toolCalls, setToolCalls] = useState<ToolCall[]>([]);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const updateJockeyMetadata = useStore((state) => state.jockey.updateMetadata);
  // Music Audio 
  const { 
		playMusic, 
		stopMusic, 
		fadeOutMusic, 
		updateMusicVolume,
		musicVolume,
		isMusicPlaying 
  } = useAudioPlayer();



 
  // Add refs to track active connections
  const eventSourceRef = useRef<EventSource | null>(null);
  const wsConnectionRef = useRef<WebSocket | null>(null);

  // Add cleanup function
  const cleanupConnections = useCallback(() => {
  
	// Make sure music is quiet.
    fadeOutMusic(1, 3);

    // Close WebSocket if open
    if (wsConnectionRef.current?.readyState === WebSocket.OPEN) {
      wsConnectionRef.current.close();
      wsConnectionRef.current = null;
    }
    
    // Close EventSource if active
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    
    // Reset processing state
    setIsProcessing(false);
  }, []);

  // Add cleanup effect
  useEffect(() => {
    return () => {
      cleanupConnections();
      stopMusic();
    };
  }, [cleanupConnections, stopMusic]);

  const handleVideoLoaded = useCallback(() => {
	  console.log('[App] Video loaded, starting music fade out');
	  fadeOutMusic(1, 3);
	  
		// Close WebSocket properly
		if (wsConnectionRef.current?.readyState === WebSocket.OPEN) {
		
			// Close the WebSocket connection
			wsConnectionRef.current.close(1000, 'Video loaded');
		}
  }, [fadeOutMusic, threadId]);

  const handleSubmit = async () => {
    if (!text.trim() || isProcessing) return;
    if (!indexId.trim()) {
      setError('Index ID is required');
      return;
    }

    // Reset states at start
    setError(null);
    setIsProcessing(true);
    setMessages([]);
    setToolCalls([]);

    try {
      // Stop current music
      console.log('[App] Stopping current background music...');
      stopMusic();
      
      // Play new background music
      const randomIndex = Math.floor(Math.random() * backgroundFiles.length);
      const selectedMusicFile = backgroundFiles[randomIndex];
      console.log('[App] Playing new background music...');
      await playMusic(selectedMusicFile);

      // Initialize thread
      console.log('[App] Initializing thread...');
      const initResponse = await fetch('/api/process/init', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });

      if (!initResponse.ok) {
        throw new Error(`Thread initialization failed: ${initResponse.status}`);
      }

      const initData = await initResponse.json();
      const threadId = initData.thread_id;
	  setThreadId(threadId);
      console.log('[App] Thread initialized with ID:', threadId);

      // Set up EventSource
      console.log('[App] Starting Jockey updates...');
      eventSourceRef.current = new EventSource(`/api/stream?thread_id=${threadId}`);

      eventSourceRef.current.onerror = (error) => {
        console.error('[SSE] EventSource error:', error);
        setError('Connection error occurred');
        cleanupConnections();
      };
	  
	  eventSourceRef.current.onmessage = (event) => {
		  console.log('[SSE] Raw event data received:', event.data);
		  try {
			const parsed = JSON.parse(event.data);
			console.log('[SSE] Parsed message:', parsed);
			
			// If we have a message with text, add it to messages
			if (parsed && parsed.text) {
				setMessages(prev => [...prev, {
				  text: parsed.text,
				  type: parsed.type,
				  name: parsed.name,
				  data: parsed.data 
				}]);
			}
		  } catch (error) {
			console.error('[SSE] Failed to parse event data:', error);
		  }
	  };

      // Process text
      console.log('[App] Processing text...');
      const processResponse = await fetch('/api/process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: text.trim(),
          thread_id: threadId,
          index_id: indexId.trim(),
        }),
      });

      if (!processResponse.ok) {
        const errorData = await processResponse.json().catch(() => ({}));
        throw new Error(errorData.detail || `Processing failed: ${processResponse.status}`);
      }

      const processData = await processResponse.json();
      console.log('[App] Processing complete:', processData);

    } catch (error) {
      console.error('[App] Error:', error);
      setError('Failed to process text. Please try again.');
    } finally {
      cleanupConnections();
    }
  };

  const handleMusicVolumeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
		const volume = parseFloat(e.target.value);
		updateMusicVolume(volume);
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="min-h-screen bg-gray-100 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-2xl mx-auto">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Lights... Camera... JOCKEY!</h1>
          <p className="mt-2 text-sm text-gray-600">
            Enter your request below to generate a new video from your existing video library.
          </p>
        </div>

        <div className="bg-white shadow-xl rounded-lg overflow-hidden">
          <div className="p-6">
            {error && (
              <div className="mb-4 p-4 bg-red-50 text-red-700 rounded-md">
                {error}
              </div>
            )}
            
            <div className="flex flex-col gap-4">
              <textarea
                ref={inputRef}
                value={text}
                onChange={(e) => setText(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="e.g. 'create a video of puppies and a beach...'"
                disabled={isProcessing}
                rows={3}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 resize-none"
              />
              <input
                type="text"
                value={indexId}
                onChange={(e) => setIndexId(e.target.value)}
                placeholder="Enter Index ID"
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
              <div className="flex items-center gap-4">
                <label htmlFor="volumeSlider" className="text-gray-700 text-sm">
                  Wait Music Volume
                </label>
                <input
                  id="volumeSlider"
                  type="range"
                  min="0"
                  max="1"
                  step="0.01"
                  value={musicVolume}
                  onChange={handleMusicVolumeChange}
                  className="w-full"
                />
              </div>
              <button
                onClick={handleSubmit}
                disabled={isProcessing || !text.trim()}
                className={`w-full px-6 py-3 rounded-lg text-white font-medium transition-colors duration-200
                  ${isProcessing || !text.trim()
                    ? 'bg-gray-400 cursor-not-allowed'
                    : 'bg-blue-500 hover:bg-blue-600'
                  }`}
              >
                {isProcessing ? 'Processing...' : 'Create'}
              </button>
            </div>
          </div>
        </div>

        <VideoPlayer 
          messages={messages} 
          indexId={indexId} 
          onVideoLoaded={handleVideoLoaded}
        />

        {(messages.length > 0 || toolCalls.length > 0) && (
          <div className="mt-4 bg-white shadow-xl rounded-lg overflow-hidden">
            <div className="p-6">
              <div className="space-y-4 max-h-96 overflow-y-auto">
                {messages.map((message, index) => (
                  <div
                    key={index}
                    className={`p-4 rounded-lg ${
                      message.type === 'human' ? 'bg-blue-50' :
                      message.type === 'ai' ? 'bg-green-50' :
                      message.type === 'error' ? 'bg-red-50' :
                      'bg-gray-50'
                    }`}
                  >
                    {message.name && (
                      <div className="text-xs text-gray-500 mb-1">
                        {message.name}
                      </div>
                    )}
                    <div className="text-sm text-gray-700 whitespace-pre-wrap">
                      {message.text}
                    </div>
                  </div>
                ))}
                {toolCalls.map((tool, index) => (
                  <div key={`tool-${index}`} className="p-4 bg-yellow-50 rounded-lg">
                    <div className="text-xs text-gray-500 mb-1">Tool Call: {tool.name}</div>
                    <div className="text-sm text-gray-700">
                      <pre className="whitespace-pre-wrap">
                        {JSON.stringify(tool.args, null, 2)}
                      </pre>
                      {tool.output && tool.output.length > 0 && (
                        <div className="mt-2">
                          <div className="text-xs text-gray-500">Output:</div>
                          <pre className="whitespace-pre-wrap">
                            {JSON.stringify(tool.output, null, 2)}
                          </pre>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default TextProcessorApp;