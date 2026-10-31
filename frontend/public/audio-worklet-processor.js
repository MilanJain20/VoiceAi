/**
 * AudioWorklet processor — runs in a dedicated audio thread.
 *
 * Captures raw PCM audio from the microphone, resamples to 16kHz mono,
 * and sends 100ms chunks to the main thread via postMessage.
 *
 * This file runs in the AudioWorklet scope (not the main thread),
 * so it has no access to DOM, fetch, WebSocket, etc.
 * MUST be plain JS — no TypeScript syntax allowed.
 */

class AudioCaptureProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super();
    this.buffer = [];
    this.bufferLength = 0;
    this.targetSampleRate = (options && options.processorOptions && options.processorOptions.targetSampleRate) || 16000;
    this.chunkDurationMs = (options && options.processorOptions && options.processorOptions.chunkDurationMs) || 100;
  }

  process(inputs, outputs, parameters) {
    const input = inputs[0];
    if (!input || !input[0] || input[0].length === 0) {
      return true;
    }

    // Take first channel (mono)
    const channelData = input[0];

    // Accumulate samples
    this.buffer.push(new Float32Array(channelData));
    this.bufferLength += channelData.length;

    // Calculate how many input samples make up one chunk at target duration
    // AudioWorklet runs at the context's sample rate (usually 44100 or 48000)
    const samplesPerChunk = Math.floor((sampleRate * this.chunkDurationMs) / 1000);

    if (this.bufferLength >= samplesPerChunk) {
      // Concatenate buffered samples
      const fullBuffer = new Float32Array(this.bufferLength);
      let offset = 0;
      for (const chunk of this.buffer) {
        fullBuffer.set(chunk, offset);
        offset += chunk.length;
      }

      // Downsample to target rate
      const downsampled = this._downsample(fullBuffer, sampleRate, this.targetSampleRate);

      // Convert float32 [-1, 1] to int16 PCM
      const pcm16 = this._float32ToPCM16(downsampled);

      // Calculate RMS amplitude for visualization
      let sumSquares = 0;
      for (let i = 0; i < channelData.length; i++) {
        sumSquares += channelData[i] * channelData[i];
      }
      const rms = Math.sqrt(sumSquares / channelData.length);

      // Send to main thread
      this.port.postMessage(
        {
          type: "audio",
          pcm16: pcm16.buffer,
          amplitude: rms,
          sampleRate: this.targetSampleRate,
          samples: downsampled.length,
        },
        [pcm16.buffer] // Transfer ownership (zero-copy)
      );

      // Reset buffer
      this.buffer = [];
      this.bufferLength = 0;
    }

    return true; // Keep processor alive
  }

  /**
   * Simple linear interpolation downsampler.
   * Good enough for voice (not music).
   */
  _downsample(buffer, fromRate, toRate) {
    if (fromRate === toRate) return buffer;

    const ratio = fromRate / toRate;
    const newLength = Math.floor(buffer.length / ratio);
    const result = new Float32Array(newLength);

    for (let i = 0; i < newLength; i++) {
      const srcIndex = i * ratio;
      const srcFloor = Math.floor(srcIndex);
      const srcCeil = Math.min(srcFloor + 1, buffer.length - 1);
      const frac = srcIndex - srcFloor;
      result[i] = buffer[srcFloor] * (1 - frac) + buffer[srcCeil] * frac;
    }

    return result;
  }

  /**
   * Convert float32 audio [-1.0, 1.0] to signed 16-bit PCM.
   * This is the format Deepgram and most STT engines expect.
   */
  _float32ToPCM16(float32) {
    const pcm16 = new Int16Array(float32.length);
    for (let i = 0; i < float32.length; i++) {
      const s = Math.max(-1, Math.min(1, float32[i]));
      pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
    }
    return pcm16;
  }
}

registerProcessor("audio-capture-processor", AudioCaptureProcessor);
