/**
 * Plays TTS audio as it arrives.
 *
 * WAV chunks from the fake provider are each a complete file and decode immediately.
 * MP3 fragments from Edge TTS append to a MediaSource when the browser allows it,
 * and otherwise wait until the sentence ends before decodeAudioData.
 * Sentences play in sequence order. stop() drops everything still queued.
 */

export type AudioCodec = "wav" | "mp3";

export interface AudioFrame {
  seq: number;
  last: boolean;
  codec: AudioCodec;
  payload: ArrayBuffer;
}

export function parseAudioFrame(buf: ArrayBuffer): AudioFrame | null {
  if (buf.byteLength < 4) return null;
  const view = new DataView(buf);
  if (view.getUint8(0) !== 1) return null;
  const flags = view.getUint8(1);
  return {
    seq: view.getUint16(2),
    last: (flags & 0x01) !== 0,
    codec: flags & 0x02 ? "mp3" : "wav",
    payload: buf.slice(4),
  };
}

interface Sentence {
  seq: number;
  codec: AudioCodec;
  parts: ArrayBuffer[];
  closed: boolean;
  started: boolean;
}

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
  private sentences = new Map<number, Sentence>();
  private nextSeq = 0;
  private htmlAudio: HTMLAudioElement[] = [];

  set onPlaybackEnd(cb: (() => void) | null) {
    this._onPlaybackEnd = cb;
  }

  set onPlaybackStart(cb: (() => void) | null) {
    this._onPlaybackStart = cb;
  }

  resetRound(): void {
    this._hasStartedCurrent = false;
    this.nextSeq = 0;
    this.sentences.clear();
  }

  beginSentence(seq: number, codec: AudioCodec): void {
    this.sentences.set(seq, { seq, codec, parts: [], closed: false, started: false });
  }

  endSentence(seq: number): void {
    const sentence = this.sentences.get(seq);
    if (sentence) sentence.closed = true;
    void this.pump();
  }

  pushFrame(frame: AudioFrame): void {
    let sentence = this.sentences.get(frame.seq);
    if (!sentence) {
      sentence = { seq: frame.seq, codec: frame.codec, parts: [], closed: false, started: false };
      this.sentences.set(frame.seq, sentence);
    }
    sentence.codec = frame.codec;
    sentence.parts.push(frame.payload);
    if (frame.last) sentence.closed = true;
    void this.pump();
  }

  /** Legacy path: one complete MP3 buffer. */
  async enqueue(mp3Data: ArrayBuffer): Promise<void> {
    await this.decodeAndQueue(mp3Data);
  }

  private async pump(): Promise<void> {
    const sentence = this.sentences.get(this.nextSeq);
    if (!sentence || sentence.started) return;

    if (sentence.codec === "wav") {
      if (sentence.parts.length === 0) {
        if (sentence.closed) {
          this.sentences.delete(sentence.seq);
          this.nextSeq += 1;
          await this.pump();
        }
        return;
      }
      sentence.started = true;
      const parts = sentence.parts.splice(0, sentence.parts.length);
      for (const part of parts) {
        await this.decodeAndQueue(part);
      }
      if (sentence.closed && sentence.parts.length === 0) {
        this.sentences.delete(sentence.seq);
        this.nextSeq += 1;
        await this.pump();
      } else {
        sentence.started = false;
      }
      return;
    }

    if (!sentence.closed) {
      this.tryMediaSource(sentence);
      return;
    }
    sentence.started = true;
    const merged = concat(sentence.parts);
    this.sentences.delete(sentence.seq);
    this.nextSeq += 1;
    await this.decodeAndQueue(merged);
    await this.pump();
  }

  private tryMediaSource(sentence: Sentence): void {
    if (sentence.started || sentence.parts.length === 0) return;
    if (typeof MediaSource === "undefined" || !MediaSource.isTypeSupported("audio/mpeg")) return;
    sentence.started = true;
    const mediaSource = new MediaSource();
    const audio = new Audio();
    audio.src = URL.createObjectURL(mediaSource);
    this.htmlAudio.push(audio);
    const parts = sentence.parts.splice(0, sentence.parts.length);
    mediaSource.addEventListener("sourceopen", () => {
      const buffer = mediaSource.addSourceBuffer("audio/mpeg");
      const queue = [...parts];
      const append = () => {
        if (buffer.updating) return;
        const next = queue.shift();
        if (next) buffer.appendBuffer(next);
      };
      buffer.addEventListener("updateend", append);
      append();
    });
    audio.onplay = () => this.markStarted();
    audio.onended = () => {
      this.sentences.delete(sentence.seq);
      this.nextSeq += 1;
      void this.pump();
    };
    void audio.play().catch(() => {
      sentence.started = false;
    });
  }

  private async decodeAndQueue(data: ArrayBuffer): Promise<void> {
    try {
      const ctx = this.getContext();
      const audioBuffer = await ctx.decodeAudioData(data.slice(0));
      this.queue.push(audioBuffer);
      this.scheduleNext();
    } catch (err) {
      console.debug("[AudioPlayer] Decode skip:", err);
    }
  }

  private getContext(): AudioContext {
    if (!this.audioContext) {
      this.audioContext = new AudioContext({ sampleRate: 48000 });
      this.gainNode = this.audioContext.createGain();
      this.gainNode.gain.value = 1.0;
      this.gainNode.connect(this.audioContext.destination);
    }
    if (this.audioContext.state === "suspended") {
      void this.audioContext.resume();
    }
    return this.audioContext;
  }

  private markStarted(): void {
    if (!this._hasStartedCurrent) {
      this._hasStartedCurrent = true;
      this._onPlaybackStart?.();
    }
  }

  private scheduleNext(): void {
    if (this.queue.length === 0) return;
    const ctx = this.getContext();
    const buffer = this.queue.shift();
    if (!buffer) return;
    const source = ctx.createBufferSource();
    source.buffer = buffer;
    source.connect(this.gainNode || ctx.destination);
    const now = ctx.currentTime;
    const startTime = Math.max(now, this.nextStartTime);
    source.start(startTime);
    this.nextStartTime = startTime + buffer.duration;
    this.isPlaying = true;
    this.currentSource = source;
    this._activeSources++;
    this.markStarted();
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

  stop(): void {
    this.queue = [];
    this.sentences.clear();
    this.nextSeq = 0;
    for (const audio of this.htmlAudio) {
      audio.pause();
      audio.src = "";
    }
    this.htmlAudio = [];
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
      void this.audioContext.close();
      this.audioContext = null;
    }
  }
}

function concat(parts: ArrayBuffer[]): ArrayBuffer {
  const size = parts.reduce((sum, part) => sum + part.byteLength, 0);
  const out = new Uint8Array(size);
  let offset = 0;
  for (const part of parts) {
    out.set(new Uint8Array(part), offset);
    offset += part.byteLength;
  }
  return out.buffer;
}

export const audioPlayer = new AudioPlayer();
