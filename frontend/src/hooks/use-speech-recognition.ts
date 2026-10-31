/**
 * useSpeechRecognition — browser-native STT using the Web Speech API.
 *
 * Uses SpeechRecognition (Chrome/Edge) for real-time transcription
 * directly in the browser. No external API calls, no proxy issues.
 *
 * Falls back gracefully if the browser doesn't support the API.
 */

import { useCallback, useEffect, useRef, useState } from "react";

// Extend Window for vendor-prefixed API
declare global {
  interface Window {
    SpeechRecognition: any;
    webkitSpeechRecognition: any;
  }
}

interface UseSpeechRecognitionOptions {
  /** Called with interim (partial) transcript text */
  onInterimTranscript?: (text: string) => void;
  /** Called with final transcript text when the user finishes a phrase */
  onFinalTranscript?: (text: string) => void;
  /** Called on recognition error */
  onError?: (error: string) => void;
  /** Language for recognition (default: en-US) */
  language?: string;
  /** Continuous recognition (default: true) */
  continuous?: boolean;
  /**
   * Milliseconds of silence after interim text before auto-finalizing.
   * When the user stops talking and the API hasn't emitted isFinal,
   * we send whatever interim text we have after this timeout. (default: 1500)
   */
  silenceTimeoutMs?: number;
}

export function useSpeechRecognition(options: UseSpeechRecognitionOptions = {}) {
  const {
    onInterimTranscript,
    onFinalTranscript,
    onError,
    language = "en-US",
    continuous = true,
    silenceTimeoutMs = 1500,
  } = options;

  const [isListening, setIsListening] = useState(false);
  const [isSupported, setIsSupported] = useState(false);
  const recognitionRef = useRef<any>(null);
  const shouldRestartRef = useRef(false);

  // Silence-timeout refs
  const silenceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastInterimRef = useRef<string>("");

  // Store latest callbacks in refs to avoid re-creating recognition
  const onInterimRef = useRef(onInterimTranscript);
  const onFinalRef = useRef(onFinalTranscript);
  const onErrorRef = useRef(onError);

  useEffect(() => {
    onInterimRef.current = onInterimTranscript;
    onFinalRef.current = onFinalTranscript;
    onErrorRef.current = onError;
  }, [onInterimTranscript, onFinalTranscript, onError]);

  // Check browser support on mount
  useEffect(() => {
    const SpeechRecognitionAPI =
      window.SpeechRecognition || window.webkitSpeechRecognition;
    setIsSupported(!!SpeechRecognitionAPI);
  }, []);

  const start = useCallback(() => {
    const SpeechRecognitionAPI =
      window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognitionAPI) {
      onErrorRef.current?.("Speech recognition not supported in this browser");
      return;
    }

    // Don't start if already running
    if (recognitionRef.current) {
      return;
    }

    const recognition = new SpeechRecognitionAPI();
    recognition.lang = language;
    recognition.continuous = continuous;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;

    recognition.onstart = () => {
      setIsListening(true);
      shouldRestartRef.current = true;
    };

    recognition.onresult = (event: any) => {
      let interimText = "";
      let finalText = "";

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        const transcript = result[0].transcript;

        if (result.isFinal) {
          finalText += transcript;
        } else {
          interimText += transcript;
        }
      }

      // ── Silence timeout: auto-finalize if user stops talking ──
      // Clear any previous timer
      if (silenceTimerRef.current) {
        clearTimeout(silenceTimerRef.current);
        silenceTimerRef.current = null;
      }

      if (finalText) {
        // Browser gave us a final result — use it and clear interim
        lastInterimRef.current = "";
        onFinalRef.current?.(finalText);
      }

      if (interimText) {
        lastInterimRef.current = interimText;
        onInterimRef.current?.(interimText);

        // Start silence timer — if no new speech/result arrives within
        // silenceTimeoutMs, treat the interim text as final.
        silenceTimerRef.current = setTimeout(() => {
          const pending = lastInterimRef.current.trim();
          if (pending) {
            lastInterimRef.current = "";
            onFinalRef.current?.(pending);
          }
          silenceTimerRef.current = null;
        }, silenceTimeoutMs);
      }
    };

    recognition.onerror = (event: any) => {
      const error = event?.error ?? "unknown";

      // Common transient states during continuous listening.
      if (error === "no-speech" || error === "aborted") {
        return;
      }

      // A browser/network issue often means the speech service is unavailable,
      // the microphone is blocked, or the page is in an environment that does not
      // provide a working speech engine. Do not keep auto-restarting endlessly.
      shouldRestartRef.current = false;
      recognitionRef.current = null;
      setIsListening(false);

      if (error === "network") {
        const msg = "Speech recognition service unavailable. Check your connection and microphone permissions.";
        console.warn("[SpeechRecognition] Network error:", msg);
        onErrorRef.current?.(msg);
        return;
      }

      if (error === "not-allowed" || error === "service-not-allowed") {
        const msg = "Microphone access was denied. Allow microphone permission and try again.";
        console.warn("[SpeechRecognition] Permission denied:", msg);
        onErrorRef.current?.(msg);
        return;
      }

      console.error("[SpeechRecognition] Error:", error);
      onErrorRef.current?.(error);
    };

    recognition.onend = () => {
      // When the browser auto-stops (e.g. silence detected), flush any
      // pending interim text before restarting.
      const pending = lastInterimRef.current.trim();
      if (pending) {
        lastInterimRef.current = "";
        if (silenceTimerRef.current) {
          clearTimeout(silenceTimerRef.current);
          silenceTimerRef.current = null;
        }
        onFinalRef.current?.(pending);
      }

      // Auto-restart for continuous recognition only when the browser is still
      // allowed to keep listening. Network and permission failures disable this.
      if (shouldRestartRef.current) {
        try {
          recognition.start();
        } catch {
          // May throw if already started
          setIsListening(false);
          recognitionRef.current = null;
        }
        return;
      }
      setIsListening(false);
      recognitionRef.current = null;
    };

    try {
      recognition.start();
      recognitionRef.current = recognition;
    } catch (e) {
      console.error("[SpeechRecognition] Failed to start:", e);
      onErrorRef.current?.("Failed to start speech recognition");
    }
  }, [language, continuous]);

  const stop = useCallback(() => {
    shouldRestartRef.current = false;

    // Clear silence timer
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }

    // If there's pending interim text, finalize it before stopping
    const pending = lastInterimRef.current.trim();
    if (pending) {
      lastInterimRef.current = "";
      onFinalRef.current?.(pending);
    }

    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {
        // May throw if not started
      }
      recognitionRef.current = null;
      setIsListening(false);
    }
  }, []);

  return { isListening, isSupported, start, stop };
}
