/* ============================================================
   useStreamingSession Hook
   ============================================================
   Manages the lifecycle of a streaming audio session:

   IDLE → RECORDING → PROCESSING → (repeat chunks) → COMPLETE

   Uses MediaRecorder for browser microphone capture and
   the streaming API to upload chunks incrementally.

   IMPORTANT:
   - This captures microphone audio only
   - It does NOT capture the remote side of a phone call
   - The UI must clearly communicate what is being recorded
   ============================================================ */

import { useState, useCallback, useRef, useEffect } from 'react';
import {
  startStream,
  uploadStreamChunk,
  finishStream,
  abortStream,
  startMicrophoneCapture,
  stopCapture,
} from '@/lib/api/stream';
import type { StreamingState } from '@/types/incident';

const INITIAL_STATE: StreamingState = {
  status: 'IDLE',
  sessionId: null,
  isRecording: false,
  totalChunks: 0,
  totalSegments: 0,
  totalObservations: 0,
  error: null,
  lastChunkAt: null,
};

// How often to send a chunk (milliseconds)
const CHUNK_INTERVAL_MS = 3000; // 3 seconds

export function useStreamingSession(incidentId: string) {
  const [state, setState] = useState<StreamingState>(INITIAL_STATE);

  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunkTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const sequenceRef = useRef(0);
  const chunkDataRef = useRef<Blob[]>([]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (chunkTimerRef.current) {
        clearInterval(chunkTimerRef.current);
      }
      if (recorderRef.current && streamRef.current) {
        stopCapture(recorderRef.current, streamRef.current);
      }
    };
  }, []);

  // Start recording
  const startRecording = useCallback(async () => {
    setState((prev) => ({ ...prev, error: null }));

    try {
      // 1. Start streaming session on server
      const startResponse = await startStream(incidentId);
      const sessionId = startResponse.session_id;

      // 2. Start browser microphone capture
      const { recorder, stream } = await startMicrophoneCapture();
      recorderRef.current = recorder;
      streamRef.current = stream;
      sequenceRef.current = 0;
      chunkDataRef.current = [];

      // 3. Set up data available handler
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunkDataRef.current.push(event.data);
        }
      };

      // 4. Start recording with timeslice for chunked data
      recorder.start(CHUNK_INTERVAL_MS);

      setState({
        status: 'CAPTURING',
        sessionId,
        isRecording: true,
        totalChunks: 0,
        totalSegments: 0,
        totalObservations: 0,
        error: null,
        lastChunkAt: Date.now(),
      });

      // 5. Set up periodic chunk upload
      chunkTimerRef.current = setInterval(async () => {
        if (chunkDataRef.current.length === 0) return;

        // Collect all pending chunk data into one blob
        const blob = new Blob(chunkDataRef.current, {
          type: recorder.mimeType || 'audio/webm',
        });
        chunkDataRef.current = [];

        const seq = sequenceRef.current++;
        const mediaType = recorder.mimeType || 'audio/webm';

        try {
          setState((prev) => ({ ...prev, status: 'PROCESSING' }));

          const result = await uploadStreamChunk(
            incidentId,
            sessionId,
            blob,
            seq,
            mediaType,
          );

          setState((prev) => ({
            ...prev,
            status: 'CAPTURING',
            totalChunks: prev.totalChunks + 1,
            totalSegments: result.total_segments ?? prev.totalSegments,
            totalObservations: result.total_observations ?? prev.totalObservations,
            lastChunkAt: Date.now(),
          }));
        } catch (err) {
          const message = err instanceof Error ? err.message : 'Chunk upload failed';
          setState((prev) => ({
            ...prev,
            status: 'ERROR',
            error: message,
          }));
        }
      }, CHUNK_INTERVAL_MS);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to start recording';
      setState((prev) => ({
        ...prev,
        status: 'ERROR',
        error: message,
      }));
    }
  }, [incidentId]);

  // Stop recording
  const stopRecording = useCallback(async () => {
    if (!state.sessionId) return;

    // Stop the periodic chunk upload
    if (chunkTimerRef.current) {
      clearInterval(chunkTimerRef.current);
      chunkTimerRef.current = null;
    }

    // Send any remaining chunk data
    if (recorderRef.current && chunkDataRef.current.length > 0) {
      const blob = new Blob(chunkDataRef.current, {
        type: recorderRef.current.mimeType || 'audio/webm',
      });
      chunkDataRef.current = [];

      const seq = sequenceRef.current++;
      try {
        await uploadStreamChunk(
          incidentId,
          state.sessionId,
          blob,
          seq,
          recorderRef.current.mimeType || 'audio/webm',
        );
      } catch {
        // Best effort — the finish call will handle errors
      }
    }

    // Stop the MediaRecorder and release tracks
    if (recorderRef.current && streamRef.current) {
      stopCapture(recorderRef.current, streamRef.current);
      recorderRef.current = null;
      streamRef.current = null;
    }

    setState((prev) => ({ ...prev, isRecording: false, status: 'PROCESSING' }));

    // Finish the streaming session
    try {
      const result = await finishStream(incidentId, state.sessionId);
      setState({
        status: 'COMPLETE',
        sessionId: result.session_id,
        isRecording: false,
        totalChunks: result.total_chunks,
        totalSegments: result.total_segments,
        totalObservations: result.total_observations,
        error: null,
        lastChunkAt: null,
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to finish session';
      setState((prev) => ({
        ...prev,
        status: 'ERROR',
        error: message,
      }));
    }
  }, [incidentId, state.sessionId]);

  // Abort recording
  const abortRecording = useCallback(async () => {
    if (!state.sessionId) return;

    if (chunkTimerRef.current) {
      clearInterval(chunkTimerRef.current);
      chunkTimerRef.current = null;
    }

    if (recorderRef.current && streamRef.current) {
      stopCapture(recorderRef.current, streamRef.current);
      recorderRef.current = null;
      streamRef.current = null;
    }

    try {
      await abortStream(incidentId, state.sessionId);
    } catch {
      // Best effort
    }

    setState(INITIAL_STATE);
  }, [incidentId, state.sessionId]);

  // Reset state
  const reset = useCallback(() => {
    setState(INITIAL_STATE);
  }, []);

  return {
    state,
    startRecording,
    stopRecording,
    abortRecording,
    reset,
  };
}
