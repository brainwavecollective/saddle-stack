import React, { useState, useEffect } from 'react';

interface DisplayMessage {
  text: string;
  type: 'system' | 'human' | 'ai' | 'error';
  name?: string;
  data?: string;
}

interface VideoPlayerProps {
  messages: DisplayMessage[];
  indexId: string;
  onVideoLoaded?: () => void;
}

interface VideoMessage {
  name: string;
  args: {
    clips: Array<{
      index_id: string;
      video_id: string;
      start: number;
      end: number;
    }>;
    output_filename: string;
    index_id: string;
  };
  type: string;
  output: string;
}



const VideoPlayer: React.FC<VideoPlayerProps> = ({ messages, indexId, onVideoLoaded }) => {
  const [videoPath, setVideoPath] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isVideoReady, setIsVideoReady] = useState(false);
  const [retryCount, setRetryCount] = useState(0);
  const MAX_RETRIES = 30;

  const checkVideoReady = async (url: string) => {
    try {
      const response = await fetch(url, {
        method: 'GET',
        headers: {
          'Range': 'bytes=0-0'
        }
      });
      return response.status === 206 || response.status === 200;
    } catch (error) {
      console.log('Video not ready yet:', error);
      return false;
    }
  };

  useEffect(() => {

    const videoMessage = messages.find((msg: DisplayMessage) => msg.name === 'video-ready');
    if (!videoMessage?.data) return;

    let videoData: VideoMessage[];
    try {
      // Parse the video data
      videoData = JSON.parse(videoMessage.data);
    } catch (error) {
      console.error('[VideoPlayer] Failed to parse video data:', error);
      setError('Invalid video data received');
      return;
    }

    // Validate the video data structure
    const combineClipsData = videoData?.[0];
    if (!combineClipsData?.args?.output_filename) {
      console.error('[VideoPlayer] Missing required video data:', combineClipsData);
      setError('Invalid video data structure');
      return;
    }

    // Make sure it's a combine-clips message
    if (combineClipsData.name !== 'combine-clips') {
      console.error('[VideoPlayer] Unexpected message type:', combineClipsData.name);
      return;
    }

    // Construct and set the video URL
    const videoUrl = `/api/jockey/video/${indexId}/${combineClipsData.args.output_filename}`;
    console.log('[VideoPlayer] Setting video URL:', videoUrl);
    
    // Reset states
    setVideoPath(videoUrl);
    setIsLoading(true);
    setError(null);
    setRetryCount(0);
    setIsVideoReady(false);

  }, [messages, indexId]);

  useEffect(() => {
    if (!videoPath || isVideoReady || retryCount >= MAX_RETRIES) return;

    const pollVideo = async () => {
      const isReady = await checkVideoReady(videoPath);
      if (isReady) {
        console.log('[VideoPlayer] Video is ready to play');
        setIsVideoReady(true);
        setIsLoading(false);
      } else {
        setRetryCount(prev => prev + 1);
        if (retryCount >= MAX_RETRIES) {
          setError('Video generation timed out. Please try refreshing the page.');
        }
      }
    };

    const timer = setTimeout(pollVideo, 2000);
    return () => clearTimeout(timer);
  }, [videoPath, isVideoReady, retryCount]);

  const handleVideoLoaded = () => {
    console.log('[VideoPlayer] Video loaded and ready to play');
    onVideoLoaded?.();
  };

  if (!videoPath) return null;

  return (
    <div className="mt-4 bg-white shadow-xl rounded-lg overflow-hidden">
      <div className="p-4">
        <h2 className="text-lg font-semibold text-gray-900">
          {(!isVideoReady || isLoading) ? "Your Video is Loading..." : "Your Video"}
        </h2>
      </div>
      <div className="p-4">
        <div className="aspect-video relative rounded-lg overflow-hidden bg-gray-100">
          {error ? (
            <div className="absolute inset-0 flex items-center justify-center text-red-500">
              {error}
            </div>
          ) : (
            <>
              {isVideoReady ? (
                <video 
                  controls
                  className="w-full h-full"
                  autoPlay
                  onLoadedData={handleVideoLoaded}
                  onError={(e) => {
                    console.error('[VideoPlayer] Video playback error:', e);
                    setError('Error playing video. Please try refreshing the page.');
                  }}
                >
                  <source src={videoPath} type="video/mp4" />
                  Your browser does not support the video tag.
                </video>
              ) : (
                <div className="absolute inset-0 flex items-center justify-center bg-black bg-opacity-50">
                  <div className="text-white text-center">
                    <div className="w-8 h-8 border-4 border-t-blue-500 border-r-transparent border-b-transparent border-l-transparent rounded-full animate-spin mx-auto"></div>
                    <p className="mt-2">Loading video...</p>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default VideoPlayer;