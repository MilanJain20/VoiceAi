/**
 * Webcam feed — shows the user's camera in a styled container.
 *
 * Mirrors the video horizontally for a natural selfie-like experience.
 * Shows a placeholder when camera is off.
 */

"use client";

import { useEffect, useRef, useState, useCallback, forwardRef, useImperativeHandle } from "react";

interface WebcamFeedProps {
  isActive: boolean;
  className?: string;
}

export interface WebcamFeedHandle {
  getVideoElement: () => HTMLVideoElement | null;
}

export const WebcamFeed = forwardRef<WebcamFeedHandle, WebcamFeedProps>(
  function WebcamFeed({ isActive, className = "" }, ref) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [hasPermission, setHasPermission] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useImperativeHandle(ref, () => ({
    getVideoElement: () => videoRef.current,
  }));

  const startCamera = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: 640 },
          height: { ideal: 480 },
          facingMode: "user",
        },
      });
      streamRef.current = stream;
      setHasPermission(true);
      setError(null);
    } catch (err) {
      setError("Camera access denied");
      console.error("[Webcam] Failed:", err);
    }
  }, []);

  const stopCamera = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setHasPermission(false);
  }, []);

  // Attach stream to video element whenever stream or permission changes
  useEffect(() => {
    if (hasPermission && streamRef.current && videoRef.current) {
      videoRef.current.srcObject = streamRef.current;
    }
  }, [hasPermission]);

  useEffect(() => {
    if (isActive) {
      startCamera();
    } else {
      stopCamera();
    }
    return () => stopCamera();
  }, [isActive, startCamera, stopCamera]);

  return (
    <div
      className={`relative overflow-hidden rounded-2xl border-2 border-[var(--color-border)] bg-[var(--color-surface)] ${className}`}
    >
      {/* Label */}
      <div className="absolute top-3 left-3 z-10 flex items-center gap-2">
        <span className="text-xs font-medium text-white/80 bg-black/50 px-2 py-1 rounded-full backdrop-blur-sm">
          You
        </span>
        {isActive && hasPermission && (
          <span className="flex h-2 w-2">
            <span className="animate-ping absolute h-2 w-2 rounded-full bg-red-500 opacity-75" />
            <span className="relative h-2 w-2 rounded-full bg-red-500" />
          </span>
        )}
      </div>

      {/* Always render video so ref is available for stream assignment */}
      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted
        className={`h-full w-full object-cover ${
          isActive && hasPermission ? "block" : "hidden"
        }`}
        style={{ transform: "scaleX(-1)" }}
      />

      {!(isActive && hasPermission) && (
        <div className="flex h-full w-full flex-col items-center justify-center gap-3">
          {error ? (
            <p className="text-xs text-red-400">{error}</p>
          ) : (
            <>
              {/* User silhouette */}
              <svg
                width="64"
                height="64"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                className="text-[var(--color-text-dim)]"
              >
                <circle cx="12" cy="8" r="4" />
                <path d="M20 21a8 8 0 1 0-16 0" />
              </svg>
              <p className="text-xs text-[var(--color-text-dim)]">
                Camera activates on start
              </p>
            </>
          )}
        </div>
      )}
    </div>
  );
});
