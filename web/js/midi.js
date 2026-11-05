// Standard MIDI File reader. Pure module (no DOM), tested with node.
// Line-by-line port of midi_import.py (read_midi, select_parts), midi_preview.py (preview_plan)
// and arrangement.py (score_clock). Time is kept in integer ticks so that simultaneous notes
// are grouped exactly; quarter notes (ticks / ppqn) are derived numbers.

export const MAX_BYTES = 16_000_000;
export const MAX_EVENTS = 200_000;
export const MAX_NOTES = 100_000;
export const MAX_MEASURES = 100_000;
export const MAX_QUARTERS = 1_000_000;
export const PREVIEW_SECONDS = 30;
export const SOUND_LOW = 21;
export const SOUND_HIGH = 108;

// code: not_midi | too_large | truncated | format2 | smpte | bad_header | bad_track | bad_vlq | bad_running
//       | bad_end | bad_tempo | bad_meter | bad_port | bad_data | system_event | too_many_events
//       | too_many_notes | too_many_parts | too_long | too_many_measures | trailing
//       | select_parts | no_notes | no_preview_notes
export class MidiError extends Error {
  constructor(code, message) {
    super(message || code);
    this.name = "MidiError";
    this.code = code;
  }
}

class Reader {
  constructor(data) {
    this.data = data;
    this.at = 0;
  }

  take(size) {
    if (size < 0 || this.at + size > this.data.length) throw new MidiError("truncated", "Truncated MIDI data");
    const value = this.data.subarray(this.at, this.at + size);
    this.at += size;
    return value;
  }

  byte() {
    return this.take(1)[0];
  }

  vlq() {
    let value = 0;
    for (let i = 0; i < 4; i++) {
      const byte = this.byte();
      value = value * 128 + (byte & 127);
      if (byte < 128) return value;
    }
    throw new MidiError("bad_vlq", "Invalid MIDI variable-length value");
  }
}

function big(bytes) {
  let value = 0;
  for (const byte of bytes) value = value * 256 + byte;
  return value;
}

function sameBytes(bytes, text) {
  if (bytes.length !== text.length) return false;
  for (let i = 0; i < text.length; i++) if (bytes[i] !== text.charCodeAt(i)) return false;
  return true;
}

function decodeName(raw) {
  let value;
  try {
    value = new TextDecoder("utf-8", { fatal: true }).decode(raw);
  } catch (error) {
    value = new TextDecoder("windows-1252").decode(raw);
  }
  return Array.from(value).filter((char) => char.codePointAt(0) >= 32).slice(0, 200).join("");
}

// Number of items <= value in a sorted array (bisect_right).
function bisectRight(sorted, value) {
  let low = 0;
  let high = sorted.length;
  while (low < high) {
    const middle = (low + high) >> 1;
    if (value < sorted[middle]) high = middle;
    else low = middle + 1;
  }
  return low;
}

const METER_UNITS = 32; // measure positions are kept in 1/32 ticks: every denominator 2^0..2^5 divides it

// Reads an ArrayBuffer / Uint8Array and returns the Score:
// {exact, warnings, parts, notes, tempos, measures, ppqn, duration, durationTicks}.
export function readMidi(input) {
  const data = input instanceof Uint8Array ? input : new Uint8Array(input);
  if (data.length > MAX_BYTES) throw new MidiError("too_large", "MIDI exceeds 16 MB");
  if (data.length < 4 || !sameBytes(data.subarray(0, 4), "MThd")) throw new MidiError("not_midi", "Not a Standard MIDI File");
  const reader = new Reader(data);
  reader.take(4);
  const header = new Reader(reader.take(big(reader.take(4))));
  const format = big(header.take(2));
  const trackCount = big(header.take(2));
  const ppqn = big(header.take(2));
  if (format !== 0 && format !== 1) throw new MidiError("format2", "Only MIDI format 0/1 is supported; format 2 is asynchronous");
  if (!(trackCount >= 1 && trackCount <= 1000) || (format === 0 && trackCount !== 1)) throw new MidiError("bad_header", "Invalid MIDI track count");
  if ((ppqn & 0x8000) || ppqn === 0) throw new MidiError("smpte", "SMPTE MIDI timing is not supported; use PPQN");

  const events = [];
  const names = new Map();
  const warnings = [];
  let exact = true;
  let end = 0;
  const warn = (message, uncertain = false) => {
    if (!warnings.includes(message)) warnings.push(message);
    if (uncertain) exact = false;
  };

  for (let track = 0; track < trackCount; track++) {
    if (reader.at + 4 > data.length) throw new MidiError("truncated", "Truncated MIDI data");
    if (!sameBytes(reader.take(4), "MTrk")) throw new MidiError("bad_track", "Missing MIDI track chunk");
    const chunk = new Reader(reader.take(big(reader.take(4))));
    let tick = 0;
    let running = null;
    let ended = false;
    let ordinal = 0;
    let port = 0;
    while (chunk.at < chunk.data.length) {
      tick += chunk.vlq();
      if (tick > 1e9) throw new MidiError("too_long", "MIDI timeline exceeds limit");
      let status = chunk.byte();
      if (status < 128) {
        if (running === null) throw new MidiError("bad_running", "MIDI running status has no channel message");
        chunk.at -= 1;
        status = running;
      }
      if (status === 0xff) {
        const kind = chunk.byte();
        const payload = chunk.take(chunk.vlq());
        running = null;
        if (kind === 0x2f) {
          const tail = chunk.data.subarray(chunk.at);
          // Narrow compatibility for legacy writers: one padding byte inside the track length.
          if (payload.length || !(tail.length === 0 || (tail.length === 1 && tail[0] === 0))) {
            throw new MidiError("bad_end", "Invalid MIDI end-of-track");
          }
          if (tail.length) warn("One zero padding byte after MIDI end-of-track ignored.");
          ended = true;
          break;
        }
        if (kind === 3) names.set(track, decodeName(payload));
        if (kind === 0x21) {
          if (payload.length !== 1 || payload[0] > 127) throw new MidiError("bad_port", "Invalid MIDI port metadata");
          port = payload[0];
        }
        if (kind === 0x51) {
          if (payload.length !== 3 || big(payload) === 0) throw new MidiError("bad_tempo", "Invalid MIDI tempo");
          events.push({ tick, track, ordinal, type: "tempo", value: big(payload) });
        }
        if (kind === 0x58) {
          if (payload.length !== 4 || payload[0] < 1 || payload[0] > 32 || payload[1] > 5) {
            throw new MidiError("bad_meter", "Unsupported MIDI time signature");
          }
          events.push({ tick, track, ordinal, type: "meter", value: [payload[0], 2 ** payload[1]] });
        }
      } else if (status === 0xf0 || status === 0xf7) {
        chunk.take(chunk.vlq());
        running = null;
        warn("MIDI SysEx sound commands are not applied.");
      } else if (status >= 0x80 && status <= 0xef) {
        running = status;
        const kind = status >> 4;
        const channel = status & 15;
        const payload = Array.from(chunk.take(kind === 0xc || kind === 0xd ? 1 : 2));
        if (payload.some((value) => value >= 128)) throw new MidiError("bad_data", "Invalid MIDI channel data");
        events.push({ tick, track, ordinal, type: "channel", value: { kind, port, channel, payload } });
      } else {
        throw new MidiError("system_event", "Unsupported MIDI system event");
      }
      ordinal++;
      if (ordinal > MAX_EVENTS || events.length > MAX_EVENTS) throw new MidiError("too_many_events", "Too many MIDI events");
    }
    if (!ended) warn("MIDI track has no end marker; trailing silence is unverified.", true);
    end = Math.max(end, tick);
  }
  if (reader.at !== data.length) throw new MidiError("trailing", "Unexpected trailing MIDI chunks");

  events.sort((a, b) => a.tick - b.tick || a.track - b.track || a.ordinal - b.ordinal);
  const tempos = new Map([[0, 500000]]);
  const meters = new Map([[0, [4, 4]]]);
  const tempoSeen = new Map();
  const meterSeen = new Map();
  const programs = new Map();
  const pedal = new Map();
  const active = new Map(); // "port|track|channel|pitch" -> {port, track, channel, pitch, queue: []}
  const sustained = new Map(); // "port,channel" -> notes held by the pedal
  const notes = [];
  const parts = new Map();

  const activeFor = (port, track, channel, pitch) => {
    const key = `${port}|${track}|${channel}|${pitch}`;
    if (!active.has(key)) active.set(key, { port, track, channel, pitch, queue: [] });
    return active.get(key);
  };
  const take = (map, stream) => {
    const value = map.get(stream) || [];
    map.delete(stream);
    return value;
  };
  const hold = (stream, note) => {
    if (!sustained.has(stream)) sustained.set(stream, []);
    sustained.get(stream).push(note);
  };
  const close = (note, tick) => {
    if (tick <= note.onsetTicks) {
      warn("Zero-length MIDI note omitted.");
      return;
    }
    note.durationTicks = tick - note.onsetTicks;
    notes.push(note);
    if (notes.length > MAX_NOTES) throw new MidiError("too_many_notes", "Too many MIDI notes");
  };

  for (const { tick, track, ordinal, type, value } of events) {
    if (type === "tempo" || type === "meter") {
      const seen = type === "tempo" ? tempoSeen : meterSeen;
      const target = type === "tempo" ? tempos : meters;
      const same = (a, b) => (Array.isArray(a) ? a[0] === b[0] && a[1] === b[1] : a === b);
      if (seen.has(tick) && !same(seen.get(tick), value)) warn("Conflicting MIDI tempo/meter events; last file-order event used.", true);
      seen.set(tick, value);
      target.set(tick, value);
      continue;
    }
    const { kind, port, channel, payload } = value;
    const stream = `${port},${channel}`;
    if (kind === 0xc) {
      programs.set(stream, payload[0]);
      continue;
    }
    if (kind === 0x9 && payload[1] > 0) {
      const [pitch, velocity] = payload;
      const program = programs.get(stream) || 0;
      const partId = `T${track + 1}O${port}C${channel + 1}P${program + 1}`;
      const name = names.get(track) || `Track ${track + 1}`;
      if (!parts.has(partId)) {
        parts.set(partId, {
          id: partId, name: `${name} · PORT ${port + 1} · CH ${channel + 1} · GM ${program + 1}`,
          midiTrack: track, midiPort: port, midiChannel: channel, midiProgram: program, percussion: channel === 9
        });
      }
      if (parts.size > 1000) throw new MidiError("too_many_parts", "Too many MIDI parts");
      if (channel === 9) {
        warn("Channel 10 percussion is not played by the piano.");
        continue;
      }
      const entry = activeFor(port, track, channel, pitch);
      if (entry.queue.length) warn("Overlapping same MIDI pitch in one track/channel matched FIFO.", true);
      entry.queue.push({ id: `${track}:${ordinal}`, partId, pitch, velocity, onsetTicks: tick });
    } else if (kind === 0x8 || (kind === 0x9 && payload[1] === 0)) {
      if (channel === 9) continue;
      let entry = activeFor(port, track, channel, payload[0]);
      if (!entry.queue.length) {
        // A note-off may live in another track; only a unique live note on this port/channel/pitch proves its target.
        const candidates = [...active.values()].filter((item) => item.queue.length && item.port === port && item.channel === channel && item.pitch === payload[0]);
        if (candidates.length !== 1 || candidates[0].queue.length !== 1) {
          warn("Unmatched or ambiguous cross-track MIDI note-off.", true);
          continue;
        }
        entry = candidates[0];
      }
      const note = entry.queue.shift();
      if (pedal.get(stream)) hold(stream, note);
      else close(note, tick);
    } else if (kind === 0xb) {
      const [controller, amount] = payload;
      if (controller === 64) {
        pedal.set(stream, amount >= 64);
        if (amount < 64) for (const note of take(sustained, stream)) close(note, tick);
      } else if (controller === 120 || controller === 123) {
        for (const entry of active.values()) {
          if (entry.port === port && entry.channel === channel) {
            while (entry.queue.length) {
              const note = entry.queue.shift();
              if (controller === 123 && pedal.get(stream)) hold(stream, note);
              else close(note, tick);
            }
          }
        }
        if (controller === 120 || !pedal.get(stream)) for (const note of take(sustained, stream)) close(note, tick);
      } else if (controller === 121) {
        pedal.set(stream, false);
        for (const note of take(sustained, stream)) close(note, tick);
      } else if (controller !== 0 && controller !== 32) {
        warn("MIDI controller sound/expression changes are not applied.");
      }
    } else if (kind === 0xe && !(payload[0] === 0 && payload[1] === 64)) {
      warn("MIDI pitch bend is unsupported; exact playback unavailable.", true);
    } else if (kind === 0xa || kind === 0xd) {
      warn("MIDI aftertouch is not applied.");
    }
  }
  if ([...active.values()].some((entry) => entry.queue.length) || [...sustained.values()].some((list) => list.length)) {
    warn("Unclosed MIDI notes/pedal-held notes omitted; no durations guessed.", true);
  }

  const durationTicks = Math.max(end, 1);
  if (durationTicks / ppqn > MAX_QUARTERS) throw new MidiError("too_long", "MIDI duration exceeds limit");

  // Measures. Positions are in 1/32 tick units so that odd meters (e.g. 3/8 with a small ppqn) stay exact.
  const totalUnits = durationTicks * METER_UNITS;
  const changeTicks = [...meters.keys()].sort((a, b) => a - b);
  const changeUnits = changeTicks.map((tick) => tick * METER_UNITS);
  const measureStarts = [];
  const measures = [];
  let position = 0;
  while (position < totalUnits) {
    const at = bisectRight(changeUnits, position) - 1;
    const [beats, beatType] = meters.get(changeTicks[at]);
    let finish = Math.min(totalUnits, position + beats * 4 * ppqn * (METER_UNITS / beatType));
    if (at + 1 < changeUnits.length) finish = Math.min(finish, changeUnits[at + 1]);
    measureStarts.push(position);
    measures.push({ number: measures.length + 1, start: position / (METER_UNITS * ppqn), beats, beatType });
    if (measures.length > MAX_MEASURES) throw new MidiError("too_many_measures", "Too many MIDI measures");
    position = finish;
  }
  for (const note of notes) {
    note.measure = bisectRight(measureStarts, note.onsetTicks * METER_UNITS);
    note.onset = note.onsetTicks / ppqn;
    note.duration = note.durationTicks / ppqn;
    note.end = (note.onsetTicks + note.durationTicks) / ppqn;
  }
  warn("MIDI parts use the local piano sound; original GM instrument timbres are not synthesized.");

  // Same order as Python: by onset, then by the textual note id.
  notes.sort((a, b) => a.onsetTicks - b.onsetTicks || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
  const tempoList = [...tempos.entries()].sort((a, b) => a[0] - b[0]).map(([tick, microseconds]) => ({
    onset: tick / ppqn, onsetTicks: tick, bpm: 60_000_000 / microseconds, microseconds
  }));
  if (tempoList.some((tempo) => tempo.bpm > 1000)) throw new MidiError("bad_tempo", "Invalid tempo time/value");

  const partList = [...parts.values()].map((part) => {
    const pitches = notes.filter((note) => note.partId === part.id).map((note) => note.pitch);
    const low = pitches.length ? Math.min(...pitches) : null;
    const high = pitches.length ? Math.max(...pitches) : null;
    return { ...part, noteCount: pitches.length, low, high, active: !part.percussion && pitches.length > 0 };
  });
  return {
    exact, warnings, parts: partList, notes, tempos: tempoList, measures,
    ppqn, duration: durationTicks / ppqn, durationTicks
  };
}

// Keeps the chosen melodic parts (and all their notes). Throws MidiError("select_parts" | "no_notes").
export function selectParts(score, ids) {
  const wanted = new Set(ids);
  const available = new Set(score.parts.filter((part) => !part.percussion).map((part) => part.id));
  if (!wanted.size || ![...wanted].every((id) => available.has(id))) {
    throw new MidiError("select_parts", "Select at least one melodic MIDI part");
  }
  const chosen = {
    ...score,
    parts: score.parts.filter((part) => wanted.has(part.id)),
    notes: score.notes.filter((note) => wanted.has(note.partId))
  };
  if (!chosen.notes.length) throw new MidiError("no_notes", "Selected MIDI parts contain no closed notes");
  return chosen;
}

// quarters -> seconds, following every tempo change (score_clock). Works for any score with
// tempos [{onset /* quarters */, bpm}]; a score without tempos runs at 120 bpm.
export function scoreClock(score) {
  const list = score.tempos && score.tempos.length ? score.tempos : [{ onset: 0, bpm: 120 }];
  const times = list.map((tempo) => tempo.onset);
  const rates = list.map((tempo) => 60 / tempo.bpm);
  const seconds = [0];
  for (let i = 1; i < times.length; i++) seconds.push(seconds[i - 1] + (times[i] - times[i - 1]) * rates[i - 1]);
  return (position) => {
    const i = Math.max(0, bisectRight(times, position) - 1);
    return seconds[i] + (position - times[i]) * rates[i];
  };
}

// Audition of the chosen parts: original pitches 21..108, shifted to the first note, at most 30 s (preview_plan).
export function previewPlan(score, ids) {
  const chosen = selectParts(score, ids);
  const clock = scoreClock(chosen);
  const items = chosen.notes
    .filter((note) => note.pitch >= SOUND_LOW && note.pitch <= SOUND_HIGH)
    .map((note) => ({ midi: note.pitch, start: clock(note.onset), end: clock(note.onset + note.duration), velocity: note.velocity, id: note.id }));
  if (!items.length) throw new MidiError("no_preview_notes", "No notes can be previewed");
  const first = Math.min(...items.map((item) => item.start));
  const duration = Math.min(PREVIEW_SECONDS, Math.max(...items.map((item) => item.end)) - first);
  return {
    duration,
    outside: chosen.notes.filter((note) => note.pitch < SOUND_LOW || note.pitch > SOUND_HIGH).length,
    notes: items
      .filter((item) => item.start - first < duration)
      .map((item) => ({ midi: item.midi, start: item.start - first, end: Math.min(duration, item.end - first), velocity: item.velocity }))
  };
}
