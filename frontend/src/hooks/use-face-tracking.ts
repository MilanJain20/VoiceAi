/**
 * useFaceTracking — tracks user's face position from webcam video.
 *
 * Uses Chrome/Edge built-in FaceDetector API (Shape Detection API).
 * Falls back to simple canvas-based motion detection if unavailable.
 *
 * Returns normalized face position (-1 to 1) and whether the user
 * appears to be talking (mouth region activity).
 *
 * Zero external dependencies — uses browser-native APIs only.
 */

import { useCallback, useEffect, useRef, useState } from "react";

// TypeScript declarations for the Shape Detection API
declare global {
  interface FaceDetectorOptions {
    maxDetectedFaces?: number;
    fastMode?: boolean;
  }

  interface DetectedFace {
    boundingBox: DOMRectReadOnly;
    landmarks: Array<{
      type: "eye" | "mouth" | "nose";
      locations: Array<{ x: number; y: number }>;
    }>;
  }

  class FaceDetector {
    constructor(options?: FaceDetectorOptions);
    detect(image: ImageBitmapSource): Promise<DetectedFace[]>;
  }
}

export interface FaceTrackingData {
  /** Is a face currently detected? */
  faceDetected: boolean;
  /** Face center X position normalized to -1 (left) to 1 (right) */
  faceX: number;
  /** Face center Y position normalized to -1 (top) to 1 (bottom) */
  faceY: number;
  /** Rough face size relative to frame (0–1) — closer = bigger */
  faceSize: number;
  /** Is the user's mouth area showing activity (talking)? */
  isTalking: boolean;
  /** Estimated mouth openness 0–1 */
  mouthOpen: number;
}

const DEFAULT_DATA: FaceTrackingData = {
  faceDetected: false,
  faceX: 0,
  faceY: 0,
  faceSize: 0,
  isTalking: false,
  mouthOpen: 0,
};

export function useFaceTracking(
  videoRef: React.RefObject<HTMLVideoElement | null>,
  enabled: boolean = true
) {
  const [data, setData] = useState<FaceTrackingData>(DEFAULT_DATA);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const prevMouthPixelsRef = useRef<Uint8ClampedArray | null>(null);
  const detectorRef = useRef<FaceDetector | null>(null);
  const rafRef = useRef<number>(0);
  const lastDetectRef = useRef<number>(0);

  // Smoothing refs to avoid jitter
  const smoothFaceX = useRef(0);
  const smoothFaceY = useRef(0);
  const smoothMouth = useRef(0);

  const lerp = (a: number, b: number, t: number) => a + (b - a) * t;

  const detectFace = useCallback(async () => {
    const video = videoRef.current;
    if (!video || video.readyState < 2 || video.videoWidth === 0) return;

    const now = performance.now();
    // Run detection at ~10 fps for performance
    if (now - lastDetectRef.current < 100) {
      rafRef.current = requestAnimationFrame(detectFace);
      return;
    }
    lastDetectRef.current = now;

    const vw = video.videoWidth;
    const vh = video.videoHeight;

    // Ensure canvas exists
    if (!canvasRef.current) {
      canvasRef.current = document.createElement("canvas");
    }
    const canvas = canvasRef.current;
    canvas.width = vw;
    canvas.height = vh;
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    if (!ctx) return;

    ctx.drawImage(video, 0, 0, vw, vh);

    let newData: Partial<FaceTrackingData> = {};

    // Try FaceDetector API first (Chrome/Edge)
    if ("FaceDetector" in window) {
      try {
        if (!detectorRef.current) {
          detectorRef.current = new FaceDetector({
            maxDetectedFaces: 1,
            fastMode: true,
          });
        }
        const faces = await detectorRef.current.detect(canvas);

        if (faces.length > 0) {
          const face = faces[0];
          const box = face.boundingBox;

          // Normalize face center to -1..1
          const cx = (box.x + box.width / 2) / vw;
          const cy = (box.y + box.height / 2) / vh;
          // Mirror X because webcam is mirrored
          const rawX = -(cx * 2 - 1);
          const rawY = cy * 2 - 1;

          smoothFaceX.current = lerp(smoothFaceX.current, rawX, 0.3);
          smoothFaceY.current = lerp(smoothFaceY.current, rawY, 0.3);

          const faceSize = (box.width * box.height) / (vw * vh);

          // Analyze mouth region for talking detection
          let mouthOpen = 0;
          const mouthLandmark = face.landmarks?.find(
            (l) => l.type === "mouth"
          );
          if (mouthLandmark && mouthLandmark.locations.length > 0) {
            // Mouth region analysis via pixel changes
            const mx = mouthLandmark.locations[0].x;
            const my = mouthLandmark.locations[0].y;
            const mouthRegionSize = box.width * 0.4;
            const sx = Math.max(0, Math.floor(mx - mouthRegionSize / 2));
            const sy = Math.max(0, Math.floor(my - mouthRegionSize / 4));
            const sw = Math.min(Math.floor(mouthRegionSize), vw - sx);
            const sh = Math.min(Math.floor(mouthRegionSize / 2), vh - sy);

            if (sw > 0 && sh > 0) {
              const mouthPixels = ctx.getImageData(sx, sy, sw, sh).data;

              if (prevMouthPixelsRef.current?.length === mouthPixels.length) {
                let diff = 0;
                for (let i = 0; i < mouthPixels.length; i += 4) {
                  diff += Math.abs(
                    mouthPixels[i] - prevMouthPixelsRef.current[i]
                  );
                }
                const avgDiff = diff / (mouthPixels.length / 4);
                mouthOpen = Math.min(avgDiff / 30, 1);
              }
              prevMouthPixelsRef.current = new Uint8ClampedArray(mouthPixels);
            }
          }

          smoothMouth.current = lerp(smoothMouth.current, mouthOpen, 0.4);

          newData = {
            faceDetected: true,
            faceX: smoothFaceX.current,
            faceY: smoothFaceY.current,
            faceSize,
            isTalking: smoothMouth.current > 0.15,
            mouthOpen: smoothMouth.current,
          };
        } else {
          newData = {
            faceDetected: false,
            faceX: lerp(smoothFaceX.current, 0, 0.05),
            faceY: lerp(smoothFaceY.current, 0, 0.05),
            faceSize: 0,
            isTalking: false,
            mouthOpen: 0,
          };
          smoothFaceX.current = newData.faceX!;
          smoothFaceY.current = newData.faceY!;
        }
      } catch {
        // FaceDetector failed, use fallback
        newData = fallbackMotionDetect(ctx, vw, vh);
      }
    } else {
      // Fallback: simple motion-based detection
      newData = fallbackMotionDetect(ctx, vw, vh);
    }

    setData((prev) => ({ ...prev, ...newData }));

    if (enabled) {
      rafRef.current = requestAnimationFrame(detectFace);
    }
  }, [videoRef, enabled]);

  // Simple fallback when FaceDetector API is unavailable
  function fallbackMotionDetect(
    ctx: CanvasRenderingContext2D,
    vw: number,
    vh: number
  ): Partial<FaceTrackingData> {
    // Assume face is roughly centered, track overall motion for talking
    const centerRegion = ctx.getImageData(
      Math.floor(vw * 0.3),
      Math.floor(vh * 0.5),
      Math.floor(vw * 0.4),
      Math.floor(vh * 0.3)
    ).data;

    let mouthOpen = 0;
    if (prevMouthPixelsRef.current?.length === centerRegion.length) {
      let diff = 0;
      for (let i = 0; i < centerRegion.length; i += 16) {
        diff += Math.abs(centerRegion[i] - prevMouthPixelsRef.current[i]);
      }
      const avgDiff = diff / (centerRegion.length / 16);
      mouthOpen = Math.min(avgDiff / 25, 1);
    }
    prevMouthPixelsRef.current = new Uint8ClampedArray(centerRegion);
    smoothMouth.current = lerp(smoothMouth.current, mouthOpen, 0.4);

    return {
      faceDetected: true, // Assume face is present since camera is on
      faceX: 0,
      faceY: 0,
      faceSize: 0.2,
      isTalking: smoothMouth.current > 0.15,
      mouthOpen: smoothMouth.current,
    };
  }

  useEffect(() => {
    if (enabled && videoRef.current) {
      rafRef.current = requestAnimationFrame(detectFace);
    }
    return () => {
      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current);
      }
    };
  }, [enabled, detectFace]);

  return data;
}
