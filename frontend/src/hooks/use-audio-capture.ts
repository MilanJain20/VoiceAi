/**
 * useAudioCapture — React hook for browser microphone capture.
 *
 * Manages the full audio capture lifecycle:
 * 1. Request mic permission
 * 2. Create AudioContext + AudioWorklet
 * 3. Stream PCM16 chunks via callback
 * 4. Track amplitude for visualization
 * 5. Clean up on stop
 *
 * Uses AudioWorklet (not deprecated ScriptProcessorNode)
 * for jank-free audio processing in a separate thread.
 */

"use client";

import { useCallback, useRef, useState } from "react";

export interface AudioChunk {
  pcm16: ArrayBuffer;
  amplitude: number;
  sampleRate: number;
  samples: number;
}

interface UseAudioCaptureOptions {
  sampleRate?: number;
  chunkDurationMs?: number;
  onAudioChunk: (chunk: AudioChunk) => void;
  onAmplitude?: (amplitude: number) => void;
  onError?: (error: Error) => void;
}

interface UseAudioCaptureReturn {
  isCapturing: boolean;
  start: () => Promise<void>;
  stop: () => void;
  amplitude: number;
}

export function useAudioCapture({
  sampleRate = 16000,
  chunkDurationMs = 100,
  onAudioChunk,
  onAmplitude,
  onError,
}: UseAudioCaptureOptions): UseAudioCaptureReturn {
  const [isCapturing, setIsCapturing] = useState(false);
  const [amplitude, setAmplitude] = useState(0);

  const audioContextRef = useRef<AudioContext | null>(null);
  const workletNodeRef = useRef<AudioWorkletNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);

  const start = useCallback(async () => {
    try {
      // Request microphone access
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: { ideal: 48000 },
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      streamRef.current = stream;

      // Create AudioContext
      const audioContext = new AudioContext({ sampleRate: 48000 });
      audioContextRef.current = audioContext;

      // Load the AudioWorklet processor
      await audioContext.audioWorklet.addModule("/audio-worklet-processor.js");

      // Create worklet node
      const workletNode = new AudioWorkletNode(audioContext, "audio-capture-processor", {
        processorOptions: {
          targetSampleRate: sampleRate,
          chunkDurationMs,
        },
      });
      workletNodeRef.current = workletNode;

      // Handle messages from the worklet (audio chunks)
      workletNode.port.onmessage = (event) => {
        const data = event.data;
        if (data.type === "audio") {
          const chunk: AudioChunk = {
            pcm16: data.pcm16,
            amplitude: data.amplitude,
            sampleRate: data.sampleRate,
            samples: data.samples,
          };
          onAudioChunk(chunk);

          // Update amplitude for visualization
          const amp = Math.min(1, data.amplitude * 5); // Amplify for visual
          setAmplitude(amp);
          onAmplitude?.(amp);
        }
      };

      // Connect: mic → worklet (no output — we don't want to play mic audio back)
      const source = audioContext.createMediaStreamSource(stream);
      sourceRef.current = source;
      source.connect(workletNode);
      // Don't connect workletNode to destination (no playback of mic)

      setIsCapturing(true);
    } catch (err) {
      const error = err instanceof Error ? err : new Error(String(err));
      console.error("[AudioCapture] Failed to start:", error);
      onError?.(error);
    }
  }, [sampleRate, chunkDurationMs, onAudioChunk, onAmplitude, onError]);

  const stop = useCallback(() => {
    // Disconnect worklet
    if (sourceRef.current) {
      sourceRef.current.disconnect();
      sourceRef.current = null;
    }

    if (workletNodeRef.current) {
      workletNodeRef.current.disconnect();
      workletNodeRef.current = null;
    }

    // Close AudioContext
    if (audioContextRef.current) {
      audioContextRef.current.close().catch(() => {});
      audioContextRef.current = null;
    }

    // Stop all mic tracks
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }

    setIsCapturing(false);
    setAmplitude(0);
  }, []);

  return { isCapturing, start, stop, amplitude };
}
