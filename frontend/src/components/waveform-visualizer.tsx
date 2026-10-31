/**
 * Live waveform visualizer — canvas-based amplitude bars.
 *
 * Renders a real-time visualization of audio amplitude,
 * showing a smooth bar chart that responds to voice input.
 * Uses requestAnimationFrame for 60fps rendering.
 */

"use client";

import { useCallback, useEffect, useRef } from "react";

interface WaveformVisualizerProps {
  amplitude: number;
  isActive: boolean;
  barCount?: number;
  className?: string;
}

export function WaveformVisualizer({
  amplitude,
  isActive,
  barCount = 32,
  className = "",
}: WaveformVisualizerProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const barsRef = useRef<number[]>(new Array(barCount).fill(0));
  const animationRef = useRef<number>(0);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const { width, height } = canvas;
    const bars = barsRef.current;

    // Clear
    ctx.clearRect(0, 0, width, height);

    if (!isActive) {
      // Draw flat line when inactive
      ctx.fillStyle = "rgba(113, 113, 122, 0.3)";
      const y = height / 2;
      ctx.fillRect(0, y - 1, width, 2);
      return;
    }

    // Shift bars left and add new amplitude on the right
    for (let i = 0; i < bars.length - 1; i++) {
      bars[i] = bars[i + 1];
    }
    // Add some randomness for natural look
    const jitter = (Math.random() - 0.5) * 0.15;
    bars[bars.length - 1] = Math.max(0.03, Math.min(1, amplitude + jitter));

    const barWidth = width / bars.length;
    const gap = 2;

    for (let i = 0; i < bars.length; i++) {
      const barHeight = Math.max(2, bars[i] * height * 0.8);
      const x = i * barWidth + gap / 2;
      const y = (height - barHeight) / 2;

      // Gradient from primary to primary-hover based on amplitude
      const intensity = bars[i];
      const r = 99 + Math.floor(intensity * 30);
      const g = 102 + Math.floor(intensity * 29);
      const b = 241;
      const alpha = 0.4 + intensity * 0.6;

      ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${alpha})`;
      ctx.beginPath();
      ctx.roundRect(x, y, barWidth - gap, barHeight, 2);
      ctx.fill();
    }

    animationRef.current = requestAnimationFrame(draw);
  }, [amplitude, isActive, barCount]);

  useEffect(() => {
    // Set canvas resolution
    const canvas = canvasRef.current;
    if (canvas) {
      const dpr = window.devicePixelRatio || 1;
      const rect = canvas.getBoundingClientRect();
      canvas.width = rect.width * dpr;
      canvas.height = rect.height * dpr;
      const ctx = canvas.getContext("2d");
      if (ctx) ctx.scale(dpr, dpr);
    }

    animationRef.current = requestAnimationFrame(draw);

    return () => {
      cancelAnimationFrame(animationRef.current);
    };
  }, [draw]);

  return (
    <canvas
      ref={canvasRef}
      className={`h-16 w-full max-w-md ${className}`}
      style={{ width: "100%", height: "64px" }}
    />
  );
}
