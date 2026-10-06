"use strict";
(() => {
  const text = {
    "Русский": {play:"▶ Прослушать проект",stop:"■ Стоп",volume:"Громкость",touch:"Удар",room:"Реверберация",sustain:"Сустейн",soft:"Мягкий",normal:"Обычный",bright:"Яркий",loading:"Загрузка звуков…",ready:"Готово · нажмите клавишу, чтобы включить звук",empty:"Сначала загрузите ноты в VPA",error:"Не удалось загрузить звук",hint:"Кликните клавиши или играйте буквами. Shift — чёрные клавиши. Пробел — сустейн.",offline:"Сэмплы внутри приложения. Интернет и MIDI-драйверы не нужны.",legacy:"Прослушивание использует ноты проекта, не ручной текст. BPM выбирается здесь; точные длительности голосов будут доработаны отдельно."},
    English: {play:"▶ Play project",stop:"■ Stop",volume:"Volume",touch:"Touch",room:"Reverb",sustain:"Sustain",soft:"Soft",normal:"Normal",bright:"Bright",loading:"Loading samples…",ready:"Ready · press a key to enable sound",empty:"Load a score in VPA first",error:"Could not load audio",hint:"Click keys or play letters. Shift: black keys. Space: sustain.",offline:"Samples are bundled. No internet or MIDI drivers needed.",legacy:"Playback uses project notes, not edited text. Choose BPM here; individual voice durations will be refined separately."},
    Deutsch: {play:"▶ Projekt abspielen",stop:"■ Stopp",volume:"Lautstärke",touch:"Anschlag",room:"Hall",sustain:"Sustain",soft:"Weich",normal:"Normal",bright:"Kräftig",loading:"Klänge werden geladen…",ready:"Bereit · Taste drücken, um den Klang zu aktivieren",empty:"Zuerst Noten in VPA laden",error:"Audio konnte nicht geladen werden",hint:"Klicken oder mit Buchstaben spielen. Shift: schwarze Tasten. Leertaste: Sustain.",offline:"Samples sind enthalten. Kein Internet oder MIDI-Treiber erforderlich.",legacy:"Wiedergabe nutzt Projektnoten, nicht bearbeiteten Text. BPM hier wählen; einzelne Stimmenlängen werden später verbessert."}
  };
  for (const [lang, labels] of Object.entries({
    "Русский": {pause:"Ⅱ Пауза",resume:"▶ Продолжить",speed:"Скорость, %",paused:"Пауза",unavailable:"Точное проигрывание недоступно. Повторно импортируйте MusicXML или проверьте предупреждения.",range:"Ноты вне 61 клавиши пропущены: ",legacy:"Темп берётся из партитуры; скорость меняет его пропорционально. Звучат ноты проекта, а не ручной текст."},
    English: {pause:"Ⅱ Pause",resume:"▶ Resume",speed:"Speed, %",paused:"Paused",unavailable:"Exact playback unavailable. Reimport MusicXML or review warnings.",range:"Notes outside 61 keys skipped: ",legacy:"Score tempo is used; speed scales it proportionally. Playback uses project notes, not manual text."},
    Deutsch: {pause:"Ⅱ Pause",resume:"▶ Fortsetzen",speed:"Tempo, %",paused:"Pausiert",unavailable:"Exakte Wiedergabe nicht verfügbar. MusicXML neu importieren oder Warnungen prüfen.",range:"Noten außerhalb von 61 Tasten ausgelassen: ",legacy:"Partiturtempo wird verwendet; Geschwindigkeit skaliert es proportional. Wiedergabe nutzt Projektnoten, nicht manuellen Text."}
  })) Object.assign(text[lang], labels);
  Object.assign(text["Русский"], {capacity:"Достигнут предел 128 звуковых голосов; проигрывание остановлено."});
  Object.assign(text.English, {capacity:"Audio voice limit (128) reached; playback stopped."});
  Object.assign(text.Deutsch, {capacity:"Audiostimmenlimit (128) erreicht; Wiedergabe gestoppt."});
  const $ = id => document.getElementById(id);
  // Optional design host reuses this sampler; the existing panel keeps its UI.
  const host = window.vpaPianoHost;
  let bridge, mapping = {}, language = "Русский", ctx, graph, ready = false, layer = 8;
  let nextId = 0, generation = 0, loadSequence = 0, sustain = false, playing = false, paused = false, starting = false;
  let plan = null, planSpeed = 1, playbackIndex = 0, origin = 0, position = 0, timer = null, completion = null;
  const visualHeld = new Map(), visualTimers = new Map(), transportVisual = new Map();
  const cache = new Map(), voices = new Map(), held = new Map(), keyboardHeld = new Map(), pointers = new Map();
  const sampleNotes = Array.from({length:30}, (_, i) => 21 + i * 3);
  const words = () => text[language] || text.English;
  let lastStatus = "";
  const status = value => { lastStatus = value; $("status").textContent = value; if (host) host.onStatus(value); };
  const call = (method, ...args) => new Promise(resolve => bridge[method](...args, resolve));

  function configure(raw) {
    const config = JSON.parse(raw);
    language = config.language; mapping = config.mapping;
    document.documentElement.lang = {"Русский":"ru",English:"en",Deutsch:"de"}[language] || "en";
    document.querySelectorAll("[data-i18n]").forEach(el => { el.textContent = words()[el.dataset.i18n]; });
    panic();
    if (ready) status(words().ready);
    buildKeys();
    if (host) host.onConfiguration(config);
  }

  function impulse(context, seconds, colored = false) {
    const buffer = context.createBuffer(2, Math.floor(context.sampleRate * seconds), context.sampleRate);
    let seed = 13579;
    for (let ch = 0; ch < 2; ch++) {
      const data = buffer.getChannelData(ch); let filtered = 0;
      for (let i = 0; i < data.length; i++) {
        seed = (1664525 * seed + 1013904223) >>> 0;
        filtered = filtered * 0.45 + (seed / 2147483648 - 1) * 0.55;
        data[i] = (colored ? filtered : seed / 2147483648 - 1) * Math.pow(1 - i / data.length, 3.5);
      }
    }
    return buffer;
  }

  function audioGraph(context, effect = null) {
    const input = context.createGain(), volume = context.createGain(), wet = context.createGain(), dry = context.createGain();
    const compressor = context.createDynamicsCompressor();
    compressor.threshold.value = -6; compressor.knee.value = 4; compressor.ratio.value = 12;
    compressor.attack.value = 0.003; compressor.release.value = 0.12;
    const convolver = context.createConvolver();
    convolver.buffer = impulse(context, effect ? (effect.preset === "hall" ? 2.6 : 0.75) : 1.4, Boolean(effect));
    volume.gain.value = Number($("volume").value) / 100;
    const mix = effect ? (effect.preset === "off" ? 0 : effect.amount / 100) : Number($("room").value) / 100;
    wet.gain.value = mix; dry.gain.value = effect ? 1 - mix : 1;
    input.connect(dry); dry.connect(volume); input.connect(convolver); convolver.connect(wet); wet.connect(volume);
    volume.connect(compressor); compressor.connect(context.destination);
    return {input, volume, wet, dry, convolver, effect, output:compressor};
  }

  function setReverb(preset, amount) {
    if (!["off", "room", "hall"].includes(preset) || !Number.isFinite(amount)) return;
    amount = Math.max(0, Math.min(100, amount));
    if (!graph) return;
    if (!graph.effect || graph.effect.preset !== preset) graph.convolver.buffer = impulse(ctx, preset === "hall" ? 2.6 : 0.75, true);
    graph.effect = {preset, amount}; const mix = preset === "off" ? 0 : amount / 100;
    graph.wet.gain.setTargetAtTime(mix, ctx.currentTime, 0.03);
    graph.dry.gain.setTargetAtTime(1 - mix, ctx.currentTime, 0.03);
  }

  async function getSample(midi, selectedLayer) {
    const key = `${midi}:${selectedLayer}`;
    if (!cache.has(key)) cache.set(key, (async () => {
      const encoded = await call("sample", midi, selectedLayer);
      if (!encoded) throw new Error(`Missing sample ${key}`);
      const bytes = Uint8Array.from(atob(encoded), char => char.charCodeAt(0));
      return ctx.decodeAudioData(bytes.buffer);
    })());
    return cache.get(key);
  }

  async function loadLayer(selectedLayer, preservePlayback = false) {
    if (![3, 8, 13].includes(selectedLayer)) return;
    if (!preservePlayback) { panic(); ready = false; $("play").disabled = true; }
    const loadingGeneration = ++loadSequence;
    bridge.report("loading"); status(words().loading);
    try {
      if (!ctx) { ctx = new AudioContext({latencyHint:"interactive"}); graph = audioGraph(ctx, host ? {preset:"room", amount:20} : null); }
      // Four concurrent decoders keep startup bounded without flooding Chromium.
      let index = 0;
      await Promise.all(Array.from({length:4}, async () => {
        while (index < sampleNotes.length) {
          const midi = sampleNotes[index++]; await getSample(midi, selectedLayer);
        }
      }));
      if (loadingGeneration !== loadSequence) return;
      layer = selectedLayer; ready = true; $("play").disabled = false; status(words().ready); bridge.report("ready");
      if (host) host.onReady();
    } catch (error) { if (loadingGeneration === loadSequence) { status(`${words().error}: ${error.message}`); bridge.report(`error:${error.message}`); } }
  }

  function samplePitch(midi) { return Math.max(21, Math.min(108, 21 + Math.round((midi - 21) / 3) * 3)); }

  function voiceSource(context, target, buffer, midi, pitch, when, strength = 0.85, offset = 0) {
    const source = context.createBufferSource(), gain = context.createGain();
    source.buffer = buffer; source.playbackRate.value = 2 ** ((midi - pitch) / 12);
    gain.gain.setValueAtTime(0, when);
    gain.gain.linearRampToValueAtTime(strength, when + 0.003);
    source.connect(gain); gain.connect(target); source.start(when, offset);
    return {source, gain, strength, when};
  }

  function release(voice, when, duration = 0.18) {
    if (!voice || (voice.released && voice.stopAt <= when + duration + 0.01)) return;
    voice.released = true;
    voice.releaseAt = when;
    voice.stopAt = when + duration + 0.01;
    voice.gain.gain.cancelScheduledValues(when);
    voice.gain.gain.setValueAtTime(when > voice.when ? voice.strength : voice.gain.gain.value, when);
    voice.gain.gain.linearRampToValueAtTime(0, when + duration);
    voice.source.stop(when + duration + 0.01);
  }

  async function noteOn(midi, token, request) {
    if (!ready || midi < 21 || midi > 108) return;
    const guard = generation;
    await ctx.resume();
    const pitch = samplePitch(midi), buffer = await getSample(pitch, layer);
    // A delayed decoder/resume must not revive an already released or retriggered key.
    if (guard !== generation || held.get(token) !== request) return;
    if (voices.size >= 64) {
      const oldest = voices.values().next().value;
      release(oldest, ctx.currentTime, 0.02); voices.delete(oldest.id);
      if (held.get(oldest.token) === oldest.id) held.delete(oldest.token);
    }
    const id = ++nextId, voice = {...voiceSource(ctx, graph.input, buffer, midi, pitch, ctx.currentTime), midi, token, id};
    voices.set(id, voice); held.set(token, id);
    voice.source.onended = () => { voices.delete(id); if (held.get(token) === id) held.delete(token); voice.source.disconnect(); voice.gain.disconnect(); highlight(); };
    highlight();
  }

  function press(midi, token) {
    if (midi < 36 || midi > 96 || !ready) return;
    clearTimeout(visualTimers.get(token)); visualTimers.delete(token);
    const old = held.get(token); release(voices.get(old), ctx.currentTime, 0.025);
    visualHeld.set(token, midi); highlight();
    const request = Symbol(token); held.set(token, request);
    const resolved=host?.soundPitch?.(midi);
    if(Number.isInteger(resolved)&&(resolved<21||resolved>108)){
      held.delete(token);visualHeld.delete(token);highlight();status(words().range+resolved);return;
    }
    const sounding=Number.isInteger(resolved)&&resolved>=21&&resolved<=108?resolved:midi+pianoShift;
    if (host) host.onNote(midi, token, true);
    noteOn(sounding, token, request).catch(error => status(error.message));
  }
  function noteOff(token) {
    const id = held.get(token); held.delete(token);
    if (host) host.onNote(null, token, false);
    if (!sustain) release(voices.get(id), ctx ? ctx.currentTime : 0);
    clearTimeout(visualTimers.get(token));
    visualTimers.set(token, setTimeout(() => { visualHeld.delete(token); visualTimers.delete(token); highlight(); }, 100));
  }

  function setSustain(value) {
    sustain = value; $("sustain").checked = value;
    if (!value && ctx) for (const voice of voices.values()) if (!voice.token.startsWith("score:") && ![...held.values()].includes(voice.id)) release(voice, ctx.currentTime);
  }

  function releaseManual(keepSustain = false) {
    const pedal = keepSustain === true && sustain;
    keyboardHeld.clear(); pointers.clear(); held.clear(); setSustain(false);
    for (const timeout of visualTimers.values()) clearTimeout(timeout);
    visualTimers.clear(); visualHeld.clear();
    if (ctx) for (const voice of voices.values()) if (!voice.token.startsWith("score:")) release(voice, ctx.currentTime, 0.025);
    if (host) host.onManualClear(); setSustain(pedal); highlight();
  }

  function highlight() {
    const active = new Set(visualHeld.values());
    if (playing && plan) {
      const at = Math.max(0, ctx.currentTime - origin);
      for (const [id, note] of transportVisual) {
        if (note.end <= at) transportVisual.delete(id);
        else if (note.start <= at && !note.audioOnly) active.add(note.displayMidi ?? note.midi);
      }
    }
    document.querySelectorAll(".key").forEach(key => key.classList.toggle("active", active.has(Number(key.dataset.midi))));
  }

  let focusPedal = null;
  let pianoShift = 0;
  function setPianoShift(value) {
    if (!Number.isInteger(value) || value < -12 || value > 12 || value === pianoShift) return;
    const pedal = sustain; panic(); setSustain(pedal); pianoShift = value;
  }
  function focusLost() {
    if (focusPedal === null) focusPedal = sustain;
    panic(true);
  }
  function focusRestored() {
    if (focusPedal !== null) { const value = focusPedal; focusPedal = null; setSustain(value); }
  }
  function panic(preserveFocus = false) {
    if (preserveFocus !== true) focusPedal = null;
    generation++; clearInterval(timer); timer = null; playing = false; paused = false; starting = false;
    plan = null; position = 0; completion = null; keyboardHeld.clear(); pointers.clear(); held.clear(); setSustain(false);
    for (const timeout of visualTimers.values()) clearTimeout(timeout);
    visualTimers.clear(); visualHeld.clear(); transportVisual.clear();
    if (host) host.onManualClear();
    if (ctx) for (const voice of voices.values()) release(voice, ctx.currentTime, 0.025);
    highlight();
    if ($("pause")) { $("pause").disabled = true; $("pause").textContent = words().pause; }
  }

  function buildKeys() {
    $("keys").replaceChildren(); let white = 0;
    for (let midi = 36; midi <= 96; midi++) {
      const info = mapping[midi]; if (!info) continue;
      const key = document.createElement("button"); key.className = `key ${info.shift ? "black" : "white"}`;
      key.dataset.midi = midi; key.style.width = `${(info.shift ? 0.64 : 1) * 100 / 36}%`;
      key.style.left = `${(info.shift ? white - 0.32 : white) * 100 / 36}%`;
      if (!info.shift) white++;
      const label = document.createElement("span"); label.textContent = info.shift ? info.key : info.key.toLowerCase();
      key.append(label); key.setAttribute("aria-label", `Note ${midi} · ${info.shift ? "Shift + " : ""}${info.key}`);
      key.onpointerdown = event => {
        if (event.button !== 0) return;
        event.preventDefault(); $("keys").focus(); key.setPointerCapture(event.pointerId);
        const token = `mouse:${event.pointerId}`; pointers.set(event.pointerId, token); press(midi, token);
      };
      const up = event => { const token = pointers.get(event.pointerId); if (token) noteOff(token); pointers.delete(event.pointerId); };
      key.onpointerup = up; key.onpointercancel = up; key.onlostpointercapture = up;
      $("keys").append(key);
    }
    if (host) host.onKeys();
  }

  function keyboardCode(event) {
    if (/^Numpad[0-9]$/.test(event.code)) return event.code;
    // Qt can report ArrowRight + NUMPAD location instead of Numpad6 when
    // NumLock is off. Never alias the separate navigation cluster (location 0).
    if (event.location === 3) {
      const navigation = {Insert:"0", End:"1", ArrowDown:"2", PageDown:"3", ArrowLeft:"4", Clear:"5", ArrowRight:"6", Home:"7", ArrowUp:"8", PageUp:"9"};
      const digit = /^[0-9]$/.test(event.key) ? event.key : navigation[event.key] ?? navigation[event.code];
      if (digit !== undefined) return `Numpad${digit}`;
    }
    return event.code;
  }
  document.addEventListener("keydown", event => {
    if (event.repeat || event.ctrlKey || event.altKey || event.metaKey || event.target.closest("input,select,textarea,[contenteditable=true],button:not(.key)") || (host && !host.canPlay())) return;
    const code = keyboardCode(event);
    if (code === "Space") { event.preventDefault(); setSustain(!sustain); return; }
    // code identifies the physical keypad key even when key is End/Insert/etc.
    // Separate code-based tokens also let Digit6 and Numpad6 overlap safely.
    const physical = code.startsWith("Key") ? code.slice(3) : code.startsWith("Digit") ? code.slice(5) : /^Numpad[0-9]$/.test(code) ? code.slice(6) : "";
    const match = Object.entries(mapping).find(([, info]) => info.key === physical && info.shift === event.shiftKey);
    if (!match || keyboardHeld.has(code)) return;
    event.preventDefault(); const token = `key:${code}`; keyboardHeld.set(code, token); press(Number(match[0]), token);
  });
  document.addEventListener("keyup", event => { const code = keyboardCode(event), token = keyboardHeld.get(code); if (token) noteOff(token); keyboardHeld.delete(code); });
  window.addEventListener("blur", focusLost);
  window.addEventListener("focus", focusRestored);
  document.addEventListener("visibilitychange", () => { if (document.hidden) focusLost(); else focusRestored(); });
  $("stop").onclick = panic;
  $("sustain").onchange = () => setSustain($("sustain").checked);
  $("volume").oninput = () => { if (graph) graph.volume.gain.setTargetAtTime(Number($("volume").value) / 100, ctx.currentTime, 0.015); };
  $("room").oninput = () => { if (host) setReverb($("reverb-preset").value, Number($("room").value)); else if (graph) graph.wet.gain.setTargetAtTime(Number($("room").value) / 100, ctx.currentTime, 0.03); };
  $("layer").onchange = async () => { $("layer").disabled = true; await loadLayer(Number($("layer").value), Boolean(host)); $("layer").disabled = false; };

  function trackVoice(voice, token) {
    const id = ++nextId; Object.assign(voice, {id, token}); voices.set(id, voice);
    voice.source.onended = () => { voices.delete(id); voice.source.disconnect(); voice.gain.disconnect(); highlight(); };
    return voice;
  }

  async function scheduleNote(note, from, guard) {
    const pitch = samplePitch(note.midi), buffer = await getSample(pitch, layer);
    if (guard !== generation || !playing) return;
    if (voices.size >= 128) { panic(); status(words().capacity); return; }
    const offset = Math.max(0, from - note.start), rate = 2 ** ((note.midi - pitch) / 12);
    if (offset * rate >= buffer.duration || origin + note.end <= ctx.currentTime) return;
    const when = Math.max(ctx.currentTime, origin + note.start);
    const elapsed = Math.max(offset, when - origin - note.start);
    const strength=note.velocity===undefined?0.85:0.85*note.velocity/127;
    const voice = trackVoice({...voiceSource(ctx, graph.input, buffer, note.midi, pitch, when, strength, elapsed * rate),
                              midi:note.midi}, `score:${note.id}`);
    transportVisual.set(note.id, note);
    release(voice, origin + note.end);
  }

  function updateTransport() {
    if (!playing || !plan) return;
    const at = Math.max(0, ctx.currentTime - origin), guard = generation;
    while (playbackIndex < plan.notes.length && plan.notes[playbackIndex].start <= at + 0.1) {
      const note = plan.notes[playbackIndex++];
      if (note.end > at) scheduleNote(note, at, guard).catch(error => { panic(); status(error.message); });
    }
    highlight();
    if (at >= plan.duration) {
      const finished = host ? {duration:plan.duration, scorePosition:plan.duration * planSpeed} : null;
      const pedal = Boolean(host) && sustain;
      panic(); completion = finished; setSustain(pedal); status(words().ready);
    }
  }

  function runTransport(from) {
    transportVisual.clear(); position = from; origin = ctx.currentTime - from; playbackIndex = 0; playing = true; paused = false;
    $("pause").disabled = false; $("pause").textContent = words().pause;
    updateTransport(); timer = setInterval(updateTransport, 20);
  }

  function pausePlayback() {
    if (!playing || !plan) return;
    const pedal = Boolean(host) && sustain;
    position = Math.min(plan.duration, Math.max(0, ctx.currentTime - origin));
    generation++; clearInterval(timer); timer = null; playing = false; paused = true;
    keyboardHeld.clear(); pointers.clear(); held.clear(); setSustain(false);
    for (const timeout of visualTimers.values()) clearTimeout(timeout);
    visualTimers.clear(); visualHeld.clear(); transportVisual.clear();
    if (host) host.onManualClear();
    for (const voice of voices.values()) release(voice, ctx.currentTime, 0.025);
    setSustain(pedal); highlight(); $("pause").textContent = words().resume; status(words().paused);
  }

  async function resumePlayback() {
    if (!paused || !plan) return;
    const guard = generation; await ctx.resume();
    if (guard !== generation || !paused) return;
    runTransport(position);
  }

  async function playProject() {
    const pedal = Boolean(host) && sustain;
    panic(); if (!ready) return;
    setSustain(pedal);
    const guard = generation; starting = true;
    try {
      await ctx.resume();
      const received = JSON.parse(await call("plan"));
      if (guard !== generation) return;
      starting = false;
      if (received.error) { status(words().unavailable); return; }
      if (!received.notes.length) { status(received.outside ? words().range + received.outside : words().empty); return; }
      const speed = Math.max(50, Math.min(200, Number($("tempo").value) || 100)) / 100;
      plan = {...received, duration:received.duration / speed,
              notes:received.notes.map(n => ({...n, start:n.start / speed, end:n.end / speed}))};
      planSpeed = speed;
      if (received.outside) status(words().range + received.outside); else status(host ? "" : words().play);
      runTransport(0);
    } catch (error) { if (guard === generation) { panic(); status(`${words().error}: ${error.message}`); } }
  }
  $("play").onclick = playProject;
  async function playPreview(received) {
    // Explicit native MIDI audition; never fetches/replaces the document plan.
    panic();if(!ready)throw new Error("Piano samples are not ready");
    if(!received||received.preview!==true||!Array.isArray(received.notes)||received.notes.length>100000||
       !Number.isFinite(received.duration)||received.duration<=0||received.duration>30||
       received.notes.some(n=>!Number.isInteger(n.midi)||n.midi<21||n.midi>108||
         !Number.isFinite(n.start)||!Number.isFinite(n.end)||n.start<0||n.end<=n.start||n.end>received.duration))
      throw new Error("Invalid MIDI preview");
    const guard=generation;starting=true;await ctx.resume();
    if(guard!==generation)return;
    starting=false;plan={...received};planSpeed=1;runTransport(0);
  }
  $("pause").onclick = () => paused ? resumePlayback() : pausePlayback();
  function setSpeed(value) {
    const next = Math.max(50, Math.min(200, Number(value) || 100)) / 100;
    const running = playing;
    if (running) pausePlayback();
    if (plan) {
      const ratio = planSpeed / next;
      plan = {...plan, duration:plan.duration * ratio, notes:plan.notes.map(n => ({...n, start:n.start * ratio, end:n.end * ratio}))};
      position *= ratio; planSpeed = next;
      if (running) runTransport(position);
    }
  }
  $("tempo").onchange = host ? () => setSpeed($("tempo").value) : panic;

  // Audio regression tests use the same sample decoder, pitch ratio and mixer.
  async function renderDemo(effect = null) {
    const offline = new OfflineAudioContext(2, 48000 * (effect ? 7 : 5), 48000), mixer = audioGraph(offline, effect);
    for (const [midi, when, duration] of [[60,0,1.2],[64,0.3,1.2],[67,0.6,1.2],[60,2,1.6],[64,2,1.6],[67,2,1.6]]) {
      const pitch = samplePitch(midi), buffer = await getSample(pitch, layer);
      const voice = voiceSource(offline, mixer.input, buffer, midi, pitch, when); release(voice, when + duration);
    }
    const buffer = await offline.startRendering(), bytes = new Uint8Array(44 + buffer.length * 4), data = new DataView(bytes.buffer);
    const string = (offset,value) => { for (let i=0;i<value.length;i++) bytes[offset+i]=value.charCodeAt(i); };
    string(0,"RIFF");data.setUint32(4,bytes.length-8,true);string(8,"WAVEfmt ");data.setUint32(16,16,true);
    data.setUint16(20,1,true);data.setUint16(22,2,true);data.setUint32(24,48000,true);data.setUint32(28,192000,true);
    data.setUint16(32,4,true);data.setUint16(34,16,true);string(36,"data");data.setUint32(40,bytes.length-44,true);
    let peak = 0, energy = 0;
    for(let i=0;i<buffer.length;i++) for(let ch=0;ch<2;ch++) {
      const sample=buffer.getChannelData(ch)[i];peak=Math.max(peak,Math.abs(sample));energy+=sample*sample;
      data.setInt16(44+(i*2+ch)*2,Math.round(Math.max(-1,Math.min(1,sample))*32767),true);
    }
    let binary="";for(let i=0;i<bytes.length;i+=8192) binary+=String.fromCharCode(...bytes.subarray(i,i+8192));
    return {wave:btoa(binary),peak,rms:Math.sqrt(energy/(buffer.length*2)),seconds:buffer.duration,
            dryGain:mixer.dry.gain.value,wetGain:mixer.wet.gain.value};
  }

  window.vpaPiano = {panic,focusLost,focusRestored,setPianoShift,press,noteOff,setSustain,loadLayer,renderDemo,playProject,playPreview,pausePlayback,resumePlayback,releaseManual,setReverb,setSpeed,
    audioOutput:()=>ready?{context:ctx,output:graph.output,tail:graph.effect&&graph.effect.preset!=="off"&&graph.effect.amount>0?graph.convolver.buffer.duration:0}:null,
    setLanguage:value => { const key=Object.keys(words()).find(k=>words()[k]===lastStatus); if (text[value]) language=value; if (key) status(words()[key]); },
    state:() => ({ready,layer,pianoShift,preview:Boolean(plan?.preview),manualPitches:[...voices.values()].filter(v=>!v.token.startsWith("score:")&&!v.released).map(v=>v.midi),voices:voices.size,held:held.size,sustain,playing,paused,starting,duration:plan ? plan.duration : completion?.duration || 0,position:completion?.duration ?? (playing ? Math.max(0,ctx.currentTime-origin) : position),
      scorePosition:completion?.scorePosition ?? ((playing ? Math.max(0,ctx.currentTime-origin) : position) * planSpeed),completed:Boolean(completion),context:ctx ? ctx.state : "none",cached:cache.size,
      activeNotes:[...voices.values()].filter(v => !v.released).map(v => v.midi)})};
  function connectBridge() {
    if (typeof qt !== "undefined") new QWebChannel(qt.webChannelTransport, async channel => {
      bridge = channel.objects.piano; configure(await call("configuration"));
      if (host) await host.onBridge(bridge, channel.objects.recorder);
      bridge.configurationChanged.connect(configure); await loadLayer(8);
    });
    else if (host) configure(JSON.stringify({language:"Русский",mapping:host.mapping}));
  }
  // Ordered page scripts must finish installing recording/document modules before
  // the native channel can call the host's asynchronous initialization hooks.
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded",connectBridge,{once:true});
  else connectBridge();
})();
