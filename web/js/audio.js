// Piano sound for the web page: Web Audio port of the sampler in
// assets/offline_piano/piano.js (without Qt). Samples are fetched from the
// repository itself; nothing leaves the page's origin.

const NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
const SAMPLE_LOW = 21;
const SAMPLE_HIGH = 108;
const SAMPLE_STEP = 3;
const MANUAL_VOICE_LIMIT = 64;
const TOTAL_VOICE_LIMIT = 160;
const PLAN_PREFIX = "plan:";
const MAX_STRENGTH = 0.85;
const REFERENCE_VELOCITY = 108;
const LOW_KEY = 36; // C2 and C7: the keys of the on-screen piano
const HIGH_KEY = 96;

// Nearest recorded pitch (recordings exist every 3 semitones from A0 to C8).
export function samplePitch(midi) {
  return Math.max(SAMPLE_LOW, Math.min(SAMPLE_HIGH, SAMPLE_LOW + Math.round((midi - SAMPLE_LOW) / SAMPLE_STEP) * SAMPLE_STEP));
}

export function sampleFileName(pitch, layer) {
  return `${NOTE_NAMES[pitch % 12]}${Math.floor(pitch / 12) - 1}v${layer}.mp3`;
}

// Recorded pitches needed to play every key in [low, high] (after any shift).
export function pitchesForRange(low, high) {
  const set = new Set();
  for (let midi = Math.max(low, SAMPLE_LOW); midi <= Math.min(high, SAMPLE_HIGH); midi++) set.add(samplePitch(midi));
  return [...set].sort((a, b) => a - b);
}

// Velocity layers of the recordings, as "Hit" in the original piano: soft v3, normal v8, bright v13.
export const LAYERS = { soft: 3, normal: 8, bright: 13 };
const LAYER_VALUES = Object.values(LAYERS);
const REVERB_PRESETS = ["off", "room", "hall"];
const DEFAULT_REVERB = { preset: "room", amount: 20 };
const SHIFT_LIMIT = 12;
const REVERB_SWAP_MS = 30; // the wet channel fades out this long before the convolver buffer is replaced

// Recordings needed for the keys C2..C7 when the sound is shifted by `shift` semitones.
export function pitchesForShift(shift = 0) {
  return pitchesForRange(LOW_KEY + shift, HIGH_KEY + shift);
}

// Noise impulse response, as in assets/offline_piano/piano.js. `colored` low-passes the noise (host mode).
export function impulse(context, seconds, colored = false) {
  const buffer = context.createBuffer(2, Math.floor(context.sampleRate * seconds), context.sampleRate);
  let seed = 13579;
  for (let channel = 0; channel < 2; channel++) {
    const data = buffer.getChannelData(channel);
    let filtered = 0;
    for (let i = 0; i < data.length; i++) {
      seed = (1664525 * seed + 1013904223) >>> 0;
      const noise = seed / 2147483648 - 1;
      filtered = filtered * 0.45 + noise * 0.55;
      data[i] = (colored ? filtered : noise) * Math.pow(1 - i / data.length, 3.5);
    }
  }
  return buffer;
}

export function reverbSeconds(preset) {
  return preset === "hall" ? 2.6 : 0.75;
}

// Wet/dry gains for a preset and an amount of 0..100 (off is fully dry).
export function reverbMix(preset, amount) {
  const share = preset === "off" ? 0 : Math.max(0, Math.min(100, Number(amount))) / 100;
  return { wet: share, dry: 1 - share };
}

function decode(context, bytes) {
  return new Promise((resolve, reject) => {
    const result = context.decodeAudioData(bytes, resolve, reject);
    if (result && typeof result.catch === "function") result.catch(reject);
  });
}

function strengthFor(velocity) {
  return Math.max(0.02, Math.min(1, MAX_STRENGTH * velocity / REFERENCE_VELOCITY));
}

export class PianoAudio {
  constructor({ baseUrl = "assets/offline_piano/samples/", layer = 8 } = {}) {
    this.baseUrl = baseUrl;
    this.layer = LAYER_VALUES.includes(layer) ? layer : LAYERS.normal; // layer that sounds now
    this.wantedLayer = this.layer; // layer being loaded, if the user picked another one
    this.reverb = { ...DEFAULT_REVERB };
    this.context = null;
    this.graph = null;
    this.layerBuffers = new Map(); // layer -> Map(pitch -> AudioBuffer)
    this.impulses = new Map(); // preset -> AudioBuffer (built once per context)
    this.loading = new Map(); // "layer:pitch" -> Promise
    this.voices = new Map();
    this.held = new Map();
    this.nextId = 0;
    this.sustain = false;
    this.shift = 0;
    this.volume = 65;
    this._state = "idle";
    this.lastError = null;
  }

  get state() {
    return this._state;
  }

  // Decoded recordings of one layer (default: the layer that sounds now).
  get buffers() {
    return this._buffersOf(this.layer);
  }

  _buffersOf(layer) {
    if (!this.layerBuffers.has(layer)) this.layerBuffers.set(layer, new Map());
    return this.layerBuffers.get(layer);
  }

  _impulseFor(preset) {
    const key = preset === "hall" ? "hall" : "room";
    if (!this.impulses.has(key)) this.impulses.set(key, impulse(this.context, reverbSeconds(key), true));
    return this.impulses.get(key);
  }

  _ensureContext() {
    if (this.context) return this.context;
    const Ctor = window.AudioContext || window.webkitAudioContext;
    if (!Ctor) throw new Error("Web Audio is not supported");
    const context = new Ctor({ latencyHint: "interactive" });
    const input = context.createGain();
    const dry = context.createGain();
    const wet = context.createGain();
    const volume = context.createGain();
    const compressor = context.createDynamicsCompressor();
    const convolver = context.createConvolver();
    compressor.threshold.value = -6;
    compressor.knee.value = 4;
    compressor.ratio.value = 12;
    compressor.attack.value = 0.003;
    compressor.release.value = 0.12;
    this.context = context;
    convolver.buffer = this._impulseFor(this.reverb.preset);
    const mix = reverbMix(this.reverb.preset, this.reverb.amount);
    wet.gain.value = mix.wet;
    dry.gain.value = mix.dry;
    volume.gain.value = this.volume / 100;
    input.connect(dry);
    dry.connect(volume);
    input.connect(convolver);
    convolver.connect(wet);
    wet.connect(volume);
    volume.connect(compressor);
    compressor.connect(context.destination);
    this.graph = { input, volume, wet, dry, convolver, impulseKey: this.reverb.preset === "hall" ? "hall" : "room", swapTimer: null };
    return context;
  }

  // Reverb as in the original piano's host mode: room 0.75 s or hall 2.6 s with coloured noise,
  // amount 0..100 % is the wet share (the dry signal gets the rest).
  setReverb(preset, amount) {
    if (!REVERB_PRESETS.includes(preset) || !Number.isFinite(Number(amount))) return;
    this.reverb = { preset, amount: Math.max(0, Math.min(100, Number(amount))) };
    if (!this.graph) return;
    const graph = this.graph;
    const key = preset === "hall" ? "hall" : "room";
    // The convolution buffer changes only with the preset: setting a buffer (even the same one) cuts the
    // reverb tail, which clicks while the amount slider is dragged. A swap goes through a silent wet channel.
    if (preset !== "off" && graph.impulseKey !== key && !graph.swapTimer) {
      graph.wet.gain.setTargetAtTime(0, this.context.currentTime, 0.008);
      graph.swapTimer = setTimeout(() => {
        graph.swapTimer = null;
        if (this.graph !== graph) return;
        const wanted = this.reverb.preset === "hall" ? "hall" : "room";
        if (this.reverb.preset !== "off" && graph.impulseKey !== wanted) {
          graph.convolver.buffer = this._impulseFor(wanted);
          graph.impulseKey = wanted;
        }
        this._applyMix();
      }, REVERB_SWAP_MS);
    }
    if (!graph.swapTimer) this._applyMix();
  }

  _applyMix() {
    const mix = reverbMix(this.reverb.preset, this.reverb.amount);
    const now = this.context.currentTime;
    this.graph.wet.gain.setTargetAtTime(mix.wet, now, 0.03);
    this.graph.dry.gain.setTargetAtTime(mix.dry, now, 0.03);
  }

  // Loads the recordings for the keys in midiRange (default C2..C7 under the current shift: 21 files).
  // Resolves when every needed file is decoded; rejects if one fails (call again to retry).
  async load(onProgress, midiRange = [LOW_KEY + this.shift, HIGH_KEY + this.shift]) {
    this._state = "loading";
    this.lastError = null;
    try {
      this._ensureContext();
      await this._fetchPitches(pitchesForRange(midiRange[0], midiRange[1]), onProgress);
      this._state = "ready";
    } catch (error) {
      this._state = "error";
      this.lastError = error;
      throw error;
    }
  }

  async _fetchPitches(pitches, onProgress, layer = this.layer) {
    const total = pitches.length;
    const have = this._buffersOf(layer);
    let done = pitches.filter((pitch) => have.has(pitch)).length;
    if (onProgress) onProgress(done, total);
    const queue = pitches.filter((pitch) => !have.has(pitch));
    let failure = null;
    const worker = async () => {
      while (queue.length && !failure) {
        const pitch = queue.shift();
        try {
          await this._fetchOne(pitch, layer);
          done++;
          if (onProgress) onProgress(done, total);
        } catch (error) {
          failure = failure || error;
        }
      }
    };
    await Promise.all(Array.from({ length: 4 }, worker));
    if (failure) throw failure;
  }

  _fetchOne(pitch, layer) {
    const have = this._buffersOf(layer);
    if (have.has(pitch)) return Promise.resolve();
    const key = `${layer}:${pitch}`;
    if (this.loading.has(key)) return this.loading.get(key);
    // Names contain "#": the URL must be escaped.
    const url = this.baseUrl + encodeURIComponent(sampleFileName(pitch, layer));
    const promise = (async () => {
      const response = await fetch(url);
      if (!response.ok) throw new Error(`HTTP ${response.status}: ${url}`);
      const bytes = await response.arrayBuffer();
      have.set(pitch, await decode(this._ensureContext(), bytes));
    })();
    this.loading.set(key, promise);
    const clear = () => this.loading.delete(key);
    promise.then(clear, clear);
    return promise;
  }

  // Loads extra recordings for keys (after shift) or sounding pitches that are not loaded yet.
  // Every layer in use (the sounding one and one that is loading) gets them.
  async ensure(midis, { shifted = false } = {}) {
    const pitches = [...new Set(midis.map((midi) => samplePitch(midi + (shifted ? this.shift : 0))))];
    const layers = new Set([this.layer, this.wantedLayer]);
    await Promise.all([...layers].map((layer) => this._fetchPitches(pitches, null, layer)));
  }

  // Picks the velocity layer ("Hit"). Its recordings load first (for the current shift); until they are
  // ready the previous layer keeps sounding. Resolves when the new layer sounds; rejects if loading fails.
  async setLayer(layer, onProgress) {
    if (!LAYER_VALUES.includes(layer)) return;
    this.wantedLayer = layer;
    if (layer === this.layer) return;
    const have = this._buffersOf(layer);
    try {
      for (;;) {
        await this._fetchPitches(pitchesForShift(this.shift), onProgress, layer);
        if (this.wantedLayer !== layer) return; // the user chose another layer meanwhile
        // A shift change during loading may need more recordings: loop until the current need is met.
        if (pitchesForShift(this.shift).every((pitch) => have.has(pitch))) break;
      }
    } catch (error) {
      if (this.wantedLayer === layer) this.wantedLayer = this.layer;
      throw error;
    }
    this.layer = layer;
    // Free the recordings of layers that are neither sounding nor wanted (about 100 MB per layer).
    for (const other of [...this.layerBuffers.keys()]) {
      if (other !== this.layer && other !== this.wantedLayer) this.layerBuffers.delete(other);
    }
  }

  // Resume the context from a user gesture (also unlocks iOS Safari).
  async unlock() {
    try {
      if (navigator.audioSession) navigator.audioSession.type = "playback";
    } catch (error) { /* optional API */ }
    const context = this._ensureContext();
    if (context.state !== "running") {
      try {
        const silent = context.createBuffer(1, 1, 22050);
        const source = context.createBufferSource();
        source.buffer = silent;
        source.connect(context.destination);
        source.start(0);
      } catch (error) { /* the resume below is what matters */ }
      try { await context.resume(); } catch (error) { /* no gesture yet */ }
    }
  }

  get unlocked() {
    return Boolean(this.context) && this.context.state === "running";
  }

  setVolume(value) {
    this.volume = Math.max(0, Math.min(100, Number(value)));
    if (this.graph) this.graph.volume.gain.setTargetAtTime(this.volume / 100, this.context.currentTime, 0.015);
  }

  // Shifts the sound (not the keys) by -12..+12 semitones. Loads missing recordings.
  setShift(semitones) {
    if (!Number.isInteger(semitones) || Math.abs(semitones) > SHIFT_LIMIT) return Promise.resolve();
    this.panic();
    this.shift = semitones;
    return this.ensure(pitchesForShift(semitones), { shifted: false });
  }

  hasSample(midi) {
    const sounding = midi + this.shift;
    if (sounding < SAMPLE_LOW || sounding > SAMPLE_HIGH) return false;
    return this.buffers.has(samplePitch(sounding));
  }

  // midi is the key; the sound is shifted by setShift. Plan tokens ("plan:") ignore the pedal and the shift.
  // Returns true when a voice was started. `when` is an AudioContext time (default: now).
  noteOn(midi, velocity = REFERENCE_VELOCITY, token = "manual", when) {
    if (!this.context || this.context.state === "closed") return false;
    const plan = token.startsWith(PLAN_PREFIX);
    const sounding = plan ? midi : midi + this.shift;
    if (sounding < SAMPLE_LOW || sounding > SAMPLE_HIGH) return false;
    const pitch = samplePitch(sounding);
    const buffer = this.buffers.get(pitch);
    if (!buffer) return false;
    const context = this.context;
    if (context.state !== "running") context.resume().catch(() => {});
    const start = when === undefined ? context.currentTime : Math.max(when, context.currentTime);
    if (!plan) {
      const old = this.held.get(token);
      if (old !== undefined) this._release(this.voices.get(old), context.currentTime, 0.025);
    }
    if (this.voices.size >= TOTAL_VOICE_LIMIT) {
      if (plan) return false;
      this._stealOldestManual();
    } else if (!plan && this._manualCount() >= MANUAL_VOICE_LIMIT) {
      this._stealOldestManual();
    }
    const id = ++this.nextId;
    const strength = strengthFor(velocity);
    const source = context.createBufferSource();
    const gain = context.createGain();
    source.buffer = buffer;
    source.playbackRate.value = 2 ** ((sounding - pitch) / 12);
    gain.gain.setValueAtTime(0, start);
    gain.gain.linearRampToValueAtTime(strength, start + 0.003);
    source.connect(gain);
    gain.connect(this.graph.input);
    source.start(start);
    const voice = { id, token, midi, source, gain, strength, when: start, plan, released: false, held: !plan, stopAt: Infinity };
    this.voices.set(id, voice);
    if (!plan) this.held.set(token, id);
    source.onended = () => {
      this.voices.delete(id);
      if (this.held.get(token) === id) this.held.delete(token);
      source.disconnect();
      gain.disconnect();
    };
    return true;
  }

  // Releases the voice of `token`. With the pedal down, manual voices keep ringing until it is lifted.
  noteOff(midi, token = "manual", when) {
    const context = this.context;
    if (!context) return;
    const now = context.currentTime;
    const time = when === undefined ? now : Math.max(when, now);
    if (token.startsWith(PLAN_PREFIX)) {
      for (const voice of this.voices.values()) {
        if (voice.token === token && voice.midi === midi && !voice.released) this._release(voice, time);
      }
      return;
    }
    const id = this.held.get(token);
    this.held.delete(token);
    const voice = this.voices.get(id);
    if (!voice) return;
    voice.held = false;
    if (!this.sustain) this._release(voice, time);
  }

  setSustain(on) {
    this.sustain = Boolean(on);
    if (this.sustain || !this.context) return;
    for (const voice of this.voices.values()) {
      if (!voice.plan && !voice.held && !voice.released) this._release(voice, this.context.currentTime);
    }
  }

  // Releases voices whose token starts with `prefix` (default: all). Used by Player and panic.
  releaseTokens(prefix = "", fade = 0.025) {
    if (!this.context) return;
    for (const voice of this.voices.values()) {
      if (voice.token.startsWith(prefix) && !voice.released) this._release(voice, this.context.currentTime, fade);
    }
  }

  panic() {
    this.sustain = false;
    this.held.clear();
    this.releaseTokens("");
  }

  _manualCount() {
    let count = 0;
    for (const voice of this.voices.values()) if (!voice.plan) count++;
    return count;
  }

  _stealOldestManual() {
    for (const voice of this.voices.values()) {
      if (!voice.plan) {
        this._release(voice, this.context.currentTime, 0.02);
        if (this.held.get(voice.token) === voice.id) this.held.delete(voice.token);
        return;
      }
    }
  }

  _release(voice, when, duration = 0.18) {
    if (!voice) return;
    const now = this.context ? this.context.currentTime : 0;
    // A decay that already started is never restarted or shortened: restarting jumps the gain back up (a click).
    if (voice.released && voice.releaseAt <= now) return;
    if (voice.released && voice.stopAt <= when + duration + 0.01) return;
    voice.released = true;
    voice.releaseAt = when;
    voice.stopAt = when + duration + 0.01;
    voice.gain.gain.cancelScheduledValues(when);
    voice.gain.gain.setValueAtTime(when > voice.when ? voice.strength : voice.gain.gain.value, when);
    voice.gain.gain.linearRampToValueAtTime(0, when + duration);
    try { voice.source.stop(when + duration + 0.01); } catch (error) { /* already stopped */ }
  }
}

// Plays a Plan {duration, notes: [{midi, start, end, velocity?, token?}]} (seconds) through PianoAudio.
const LOOKAHEAD = 0.1;
const TICK_MS = 20;

export class Player {
  constructor(audio) {
    this.audio = audio;
    this._plan = null;
    this._speed = 1;
    this._position = 0;
    this._origin = 0;
    this._timer = null;
    this._playing = false;
    this._paused = false;
    this._run = 0;
    this._queue = [];
    this._visual = [];
    this._active = new Map();
    this._onNote = null;
    this._onEnd = null;
    this._resolve = null;
    this._sequence = 0;
  }

  get playing() {
    return this._playing;
  }

  get paused() {
    return this._paused;
  }

  // Plan seconds already played.
  get position() {
    return this._playing ? this._now() : this._position;
  }

  _now() {
    return Math.min(this._plan ? this._plan.duration : 0, Math.max(0, (this.audio.context.currentTime - this._origin) * this._speed));
  }

  // Starts a plan from the beginning. Resolves true when it ends by itself, false when stopped.
  async play(plan, { speed = 1, onNote = null, onEnd = null } = {}) {
    this.stop();
    const run = ++this._run;
    this._plan = {
      duration: plan.duration,
      notes: [...plan.notes].sort((a, b) => a.start - b.start)
    };
    this._speed = Math.max(0.1, speed);
    this._position = 0;
    this._onNote = onNote;
    this._onEnd = onEnd;
    const completion = new Promise((resolve) => { this._resolve = resolve; });
    this._paused = false;
    this._playing = false;
    await this.audio.unlock();
    await this.audio.ensure([...new Set(this._plan.notes.map((note) => note.midi))]);
    if (run !== this._run) return completion;
    this._start(0);
    return completion;
  }

  _start(position) {
    const context = this.audio.context;
    this._position = position;
    this._origin = context.currentTime - position / this._speed;
    this._queue = this._plan.notes.filter((note) => note.end > position);
    this._visual = [];
    this._active.clear();
    this._playing = true;
    this._paused = false;
    this._tick();
    this._timer = setInterval(() => this._tick(), TICK_MS);
  }

  _tick() {
    if (!this._playing) return;
    const context = this.audio.context;
    const at = (context.currentTime - this._origin) * this._speed;
    const horizon = at + LOOKAHEAD * this._speed;
    while (this._queue.length && this._queue[0].start <= horizon) {
      const note = this._queue.shift();
      const start = Math.max(note.start, this._position);
      const token = `${PLAN_PREFIX}${++this._sequence}`;
      const on = this._origin + start / this._speed;
      const off = this._origin + note.end / this._speed;
      this.audio.noteOn(note.midi, note.velocity === undefined ? REFERENCE_VELOCITY : note.velocity, token, on);
      this.audio.noteOff(note.midi, token, off);
      this._visual.push({ time: start, midi: note.midi, on: true, token, note });
      this._visual.push({ time: note.end, midi: note.midi, on: false, token, note });
    }
    this._visual.sort((a, b) => a.time - b.time);
    while (this._visual.length && this._visual[0].time <= at) this._fire(this._visual.shift());
    if (at >= this._plan.duration && !this._queue.length) {
      while (this._visual.length) this._fire(this._visual.shift());
      this._finish(true);
    }
  }

  _fire(event) {
    if (event.on) this._active.set(event.token, event);
    else this._active.delete(event.token);
    if (this._onNote) this._onNote(event.midi, event.on, event.note.token);
  }

  _silence() {
    clearInterval(this._timer);
    this._timer = null;
    this.audio.releaseTokens(PLAN_PREFIX);
    for (const event of [...this._active.values()]) this._fire({ ...event, on: false });
    this._active.clear();
    this._visual = [];
    this._queue = [];
  }

  _finish(completed) {
    this._silence();
    this._playing = false;
    this._paused = false;
    this._position = 0;
    const resolve = this._resolve;
    const onEnd = this._onEnd;
    this._resolve = null;
    this._run++;
    if (onEnd) onEnd(completed);
    if (resolve) resolve(completed);
  }

  pause() {
    if (!this._playing) return;
    this._position = this._now();
    this._silence();
    this._playing = false;
    this._paused = true;
  }

  resume() {
    if (!this._paused || !this._plan) return;
    this._start(this._position);
  }

  stop() {
    if (!this._plan || (!this._playing && !this._paused && !this._resolve)) return;
    this._finish(false);
  }

  setSpeed(x) {
    const next = Math.max(0.1, x);
    if (this._playing) {
      this.pause();
      this._speed = next;
      this.resume();
    } else {
      this._speed = next;
    }
  }
}
