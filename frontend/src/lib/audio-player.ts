/**
 * Audio playback engine — plays MP3 from TTS via Web Audio API.
 *
 * Receives complete MP3 sentences from the WebSocket, decodes them
 * using AudioContext.decodeAudioData(), and queues playback with
 * seamless scheduling for gapless, clean audio.
 *
 * Key design: each enqueue() call gets a complete, valid MP3 so
 * decodeAudioData never chokes on partial data.
 */

export class AudioPlayer {
  private audioContext: AudioContext | null = null;
  private gainNode: GainNode | null = null;
  private queue: AudioBuffer[] = [];
  private isPlaying = false;
  private nextStartTime = 0;
  private currentSource: AudioBufferSourceNode | null = null;
  private _onPlaybackEnd: (() => void) | null = null;
  private _onPlaybackStart: (() => void) | null = null;
  private _activeSources = 0;
  private _hasStartedCurrent = false;

  constructor() {}

  set onPlaybackEnd(cb: (() => void) | null) {
    this._onPlaybackEnd = cb;
  }

  set onPlaybackStart(cb: (() => void) | null) {
    this._onPlaybackStart = cb;
  }

  /**
   * Reset the "started" flag so the next enqueue triggers onPlaybackStart.
   * Call this when a new AI response round begins.
   */
  resetRound(): void {
    this._hasStartedCurrent = false;
  }

  private getContext(): AudioContext {
    if (!this.audioContext) {
      // Use 48 kHz to match most default output devices and avoid
      // resampling artifacts when decoding 24 kHz edge-tts MP3.
      this.audioContext = new AudioContext({ sampleRate: 48000 });
      this.gainNode = this.audioContext.createGain();
      this.gainNode.gain.value = 1.0;
      this.gainNode.connect(this.audioContext.destination);
    }
    if (this.audioContext.state === "suspended") {
      this.audioContext.resume();
    }
    return this.audioContext;
  }

  /**
   * Enqueue an MP3 audio chunk for playback.
   * Decodes the MP3 and schedules it for seamless playback.
   */
  async enqueue(mp3Data: ArrayBuffer): Promise<void> {
    try {
      const ctx = this.getContext();
      // decodeAudioData needs a copy since it detaches the buffer
      const copy = mp3Data.slice(0);
      const audioBuffer = await ctx.decodeAudioData(copy);
      this.queue.push(audioBuffer);
      this.scheduleNext();
    } catch (err) {
      // Some chunks may be too small to decode — skip silently
      console.debug("[AudioPlayer] Decode skip:", err);
    }
  }

  private scheduleNext(): void {
    if (this.queue.length === 0) {
      return;
    }

    const ctx = this.getContext();
    const buffer = this.queue.shift()!;

    const source = ctx.createBufferSource();
    source.buffer = buffer;
    source.connect(this.gainNode || ctx.destination);

    // Schedule for seamless playback
    const now = ctx.currentTime;
    const startTime = Math.max(now, this.nextStartTime);
    source.start(startTime);
    this.nextStartTime = startTime + buffer.duration;

    this.isPlaying = true;
    this.currentSource = source;
    this._activeSources++;

    // Fire once per response round when the first chunk actually starts
    if (!this._hasStartedCurrent) {
      this._hasStartedCurrent = true;
      this._onPlaybackStart?.();
    }

    source.onended = () => {
      this._activeSources--;
      if (this.queue.length > 0) {
        this.scheduleNext();
      } else if (this._activeSources <= 0) {
        this.isPlaying = false;
        this.currentSource = null;
        this._activeSources = 0;
        this._onPlaybackEnd?.();
      }
    };
  }

  /**
   * Stop all playback and clear the queue.
   */
  stop(): void {
    this.queue = [];
    if (this.currentSource) {
      try {
        this.currentSource.stop();
      } catch {
        // Already stopped
      }
      this.currentSource = null;
    }
    this.isPlaying = false;
    this.nextStartTime = 0;
    this._activeSources = 0;
    this._hasStartedCurrent = false;
  }

  /**
   * Set playback volume (0.0 to 1.0).
   */
  setVolume(volume: number): void {
    if (this.gainNode) {
      this.gainNode.gain.value = Math.max(0, Math.min(1, volume));
    }
  }

  get playing(): boolean {
    return this.isPlaying;
  }

  dispose(): void {
    this.stop();
    if (this.audioContext) {
      this.audioContext.close();
      this.audioContext = null;
    }
  }
}

// Global singleton
export const audioPlayer = new AudioPlayer();
