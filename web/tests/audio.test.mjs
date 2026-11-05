import test from "node:test";
import assert from "node:assert/strict";
import { PianoAudio, LAYERS, impulse, reverbSeconds, reverbMix, pitchesForShift, samplePitch } from "../js/audio.js";

// ---- Minimal Web Audio and fetch stand-ins ----
function fakeGain() {
  return {
    gain: {
      value: 1,
      setTargetAtTime(value) { this.value = value; },
      setValueAtTime(value) { this.value = value; },
      linearRampToValueAtTime() {},
      cancelScheduledValues() {}
    },
    connect() {},
    disconnect() {}
  };
}

class FakeContext {
  constructor() {
    this.sampleRate = 48000;
    this.currentTime = 0;
    this.state = "running";
    this.destination = {};
  }
  createGain() { return fakeGain(); }
  createDynamicsCompressor() {
    return { threshold: {}, knee: {}, ratio: {}, attack: {}, release: {}, connect() {} };
  }
  createConvolver() { return { buffer: null, connect() {} }; }
  createBuffer(channels, length) {
    const data = Array.from({ length: channels }, () => new Float32Array(length));
    return { length, numberOfChannels: channels, getChannelData: (channel) => data[channel] };
  }
  decodeAudioData(bytes, resolve) { resolve({ decoded: true }); }
}

function installEnvironment({ gate = null } = {}) {
  const requested = [];
  globalThis.window = { AudioContext: FakeContext };
  globalThis.fetch = async (url) => {
    requested.push(url);
    if (gate) await gate;
    return { ok: true, arrayBuffer: async () => new ArrayBuffer(8) };
  };
  return requested;
}

const BASE = "assets/offline_piano/samples/";

test("layers are the three velocity layers of the original piano", () => {
  assert.deepEqual(LAYERS, { soft: 3, normal: 8, bright: 13 });
});

test("impulse: stereo noise of the requested length that fades out", () => {
  const context = new FakeContext();
  const buffer = impulse(context, 0.75, true);
  assert.equal(buffer.length, 36000);
  assert.equal(buffer.numberOfChannels, 2);
  const left = buffer.getChannelData(0);
  assert.ok(left.some((value) => Math.abs(value) > 0.05));
  assert.ok(Math.abs(left[left.length - 1]) < 1e-6);
  assert.notDeepEqual(Array.from(left.slice(0, 50)), Array.from(buffer.getChannelData(1).slice(0, 50)));
});

test("impulse: coloured noise differs from plain noise and is repeatable", () => {
  const context = new FakeContext();
  const plain = impulse(context, 0.1).getChannelData(0);
  const coloured = impulse(context, 0.1, true).getChannelData(0);
  const again = impulse(context, 0.1, true).getChannelData(0);
  assert.notDeepEqual(Array.from(plain.slice(0, 20)), Array.from(coloured.slice(0, 20)));
  assert.deepEqual(Array.from(coloured.slice(0, 20)), Array.from(again.slice(0, 20)));
  // The first sample of the coloured noise is 0.55 of the plain one (one-pole filter, first step).
  assert.ok(Math.abs(coloured[0] - plain[0] * 0.55) < 1e-6);
});

test("reverb presets: room 0.75 s, hall 2.6 s", () => {
  assert.equal(reverbSeconds("room"), 0.75);
  assert.equal(reverbSeconds("hall"), 2.6);
});

test("reverb mix: wet is the amount, dry is the rest, off is fully dry", () => {
  assert.deepEqual(reverbMix("room", 20), { wet: 0.2, dry: 0.8 });
  assert.deepEqual(reverbMix("hall", 100), { wet: 1, dry: 0 });
  assert.deepEqual(reverbMix("off", 70), { wet: 0, dry: 1 });
  assert.deepEqual(reverbMix("room", 250), { wet: 1, dry: 0 });
});

test("recordings needed for the keys C2..C7 follow the tonality shift", () => {
  const flat = pitchesForShift(0);
  assert.equal(flat.length, 21);
  assert.deepEqual([flat[0], flat[20]], [36, 96]);
  const up = pitchesForShift(12);
  assert.deepEqual([up[0], up[up.length - 1]], [48, 108]);
  const down = pitchesForShift(-12);
  assert.deepEqual([down[0], down[down.length - 1]], [24, 84]);
  assert.ok(pitchesForShift(5).every((pitch) => samplePitch(pitch) === pitch));
});

test("setShift accepts any semitone in -12..12 and ignores the rest", async () => {
  installEnvironment();
  const audio = new PianoAudio({ baseUrl: BASE });
  audio._ensureContext();
  await audio.setShift(5);
  assert.equal(audio.shift, 5);
  await audio.setShift(-12);
  assert.equal(audio.shift, -12);
  await audio.setShift(13);
  await audio.setShift(1.5);
  assert.equal(audio.shift, -12);
});

test("a shift loads the recordings it needs, with # escaped in the URL", async () => {
  const requested = installEnvironment();
  const audio = new PianoAudio({ baseUrl: BASE });
  audio._ensureContext();
  await audio.setShift(12);
  assert.equal(requested.length, 21);
  assert.ok(requested.every((url) => url.startsWith(BASE) && url.endsWith("v8.mp3")));
  assert.ok(requested.some((url) => url.includes("%23")));
  assert.ok(requested.every((url) => !url.includes("#")));
  assert.ok(requested.some((url) => url.endsWith("C3v8.mp3")));
  assert.ok(requested.some((url) => url.endsWith("C8v8.mp3")));
});

test("a heavier or lighter layer is loaded on demand; the old layer plays until it is ready", async () => {
  let open;
  const gate = new Promise((resolve) => { open = resolve; });
  const requested = installEnvironment({ gate });
  const audio = new PianoAudio({ baseUrl: BASE });
  audio._ensureContext();
  assert.equal(audio.layer, 8);
  const progress = [];
  const pending = audio.setLayer(13, (done, total) => progress.push([done, total]));
  await new Promise((resolve) => setTimeout(resolve, 5));
  assert.equal(audio.layer, 8, "still the old layer while loading");
  open();
  await pending;
  assert.equal(audio.layer, 13);
  assert.equal(requested.length, 21);
  assert.ok(requested.every((url) => url.endsWith("v13.mp3")));
  assert.deepEqual(progress[progress.length - 1], [21, 21]);
});

test("the layer is loaded for the current tonality", async () => {
  const requested = installEnvironment();
  const audio = new PianoAudio({ baseUrl: BASE });
  audio._ensureContext();
  audio.shift = 12;
  await audio.setLayer(3);
  assert.equal(audio.layer, 3);
  assert.ok(requested.some((url) => url.endsWith("C8v3.mp3")));
  assert.ok(requested.every((url) => url.endsWith("v3.mp3")));
});

test("an unknown layer is ignored", async () => {
  const requested = installEnvironment();
  const audio = new PianoAudio({ baseUrl: BASE });
  audio._ensureContext();
  await audio.setLayer(5);
  assert.equal(audio.layer, 8);
  assert.equal(requested.length, 0);
});

const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function countBufferSets(convolver) {
  const counter = { sets: 0 };
  let current = convolver.buffer;
  Object.defineProperty(convolver, "buffer", {
    get: () => current,
    set: (value) => { counter.sets++; current = value; }
  });
  return counter;
}

test("moving the amount slider with the same preset never touches the convolver buffer", () => {
  installEnvironment();
  const audio = new PianoAudio({ baseUrl: BASE });
  audio._ensureContext();
  const counter = countBufferSets(audio.graph.convolver);
  for (const amount of [10, 40, 75, 100, 0]) audio.setReverb("room", amount);
  assert.equal(counter.sets, 0);
  assert.equal(audio.graph.wet.gain.value, 0);
  assert.equal(audio.graph.dry.gain.value, 1);
  audio.setReverb("room", 60);
  assert.equal(audio.graph.wet.gain.value, 0.6);
});

test("a preset change fades the wet channel to silence first, then swaps the buffer and restores the mix", async () => {
  installEnvironment();
  const audio = new PianoAudio({ baseUrl: BASE });
  audio._ensureContext();
  const counter = countBufferSets(audio.graph.convolver);
  audio.setReverb("hall", 50);
  assert.equal(audio.graph.wet.gain.value, 0, "wet is silent while the buffer is still the old one");
  assert.equal(counter.sets, 0);
  audio.setReverb("hall", 70); // dragging during the swap must not start a second swap
  await pause(80);
  assert.equal(counter.sets, 1);
  assert.equal(audio.graph.convolver.buffer.length, 124800);
  assert.equal(audio.graph.wet.gain.value, 0.7);
  assert.ok(Math.abs(audio.graph.dry.gain.value - 0.3) < 1e-9);
});

test("after a successful layer change only the sounding and the wanted layers stay in memory", async () => {
  installEnvironment();
  const audio = new PianoAudio({ baseUrl: BASE });
  audio._ensureContext();
  await audio.setLayer(13);
  assert.deepEqual([...audio.layerBuffers.keys()], [13]);
  await audio.setLayer(3);
  assert.deepEqual([...audio.layerBuffers.keys()], [3]);
  assert.equal(audio.buffers.size, 21);
});

test("setReverb switches the impulse and the wet/dry mix", async () => {
  installEnvironment();
  const audio = new PianoAudio({ baseUrl: BASE });
  audio._ensureContext();
  assert.deepEqual(audio.reverb, { preset: "room", amount: 20 });
  assert.equal(audio.graph.convolver.buffer.length, 36000);
  assert.equal(audio.graph.wet.gain.value, 0.2);
  audio.setReverb("hall", 50);
  await pause(80);
  assert.equal(audio.graph.convolver.buffer.length, 124800);
  assert.equal(audio.graph.wet.gain.value, 0.5);
  assert.equal(audio.graph.dry.gain.value, 0.5);
  audio.setReverb("off", 80);
  assert.equal(audio.graph.wet.gain.value, 0);
  assert.equal(audio.graph.dry.gain.value, 1);
  audio.setReverb("cathedral", 10);
  assert.deepEqual(audio.reverb, { preset: "off", amount: 80 });
});

test("reverb chosen before the sound starts is used when the graph is built", () => {
  installEnvironment();
  const audio = new PianoAudio({ baseUrl: BASE });
  audio.setReverb("hall", 35);
  audio._ensureContext();
  assert.equal(audio.graph.convolver.buffer.length, 124800);
  assert.equal(audio.graph.wet.gain.value, 0.35);
});
