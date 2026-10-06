"use strict";
// Live preview adapter. Audio and timing belong to the shared Salamander engine.
(() => {
  const translations = {
    ru: {
      open:"Открыть",save:"Сохранить",export:"Экспорт",settings:"Настройки",close:"Закрыть",notes:"Ноты",sound:"Звук",view:"Вид",
      project:"Ночной этюд",exampleLabel:"ВСТРОЕННЫЙ ПРИМЕР · 8 ТАКТОВ",livePreview:"Живой макет",notation:"Буквенная запись",
      fontSize:"Размер букв",follow:"Автопрокрутка по игре",followReset:"Сначала",textHint:"Правки текста не меняют звучащие ноты.",bars:"тактов",
      transpose:"Транспозиция",semitones:"полутонов",best:"Подобрать удобную тональность",fullness:"Полнота аккордов",easy:"Лёгкая партия",full:"Все ноты",layout:"Раскладка букв",
      preview:"Предпросмотр изменений",apply:"Применить",cancel:"Отменить",tone:"Характер звука",soft:"Мягкий",normal:"Обычный",bright:"Яркий",
      reverb:"Реверберация",dry:"Без эффекта",room:"Комната",hall:"Зал",amount:"Количество эффекта",reverbHint:"0% — без дополнительного эффекта. 100% — только обработанный звук. Сравните один пример с разными пресетами.",
      compare:"Проиграть пример с этим звуком",resizeHint:"Потяните границу над пианино: клавиши меняют размер целиком. Кнопка сворачивания скрывает их полностью.",
      reduceMotion:"Без анимации",futureHint:"Режим поверх окон и компактный игровой режим подключим при переносе в приложение.",
      conflict:"Заменить ручной текст новым результатом?",keep:"Оставить правки",replace:"Заменить",stop:"Стоп",record:"Запись",speed:"Скорость, %",volume:"Громкость",sustain:"Сустейн",
      keyLabels:"Подписи",noLabels:"Нет",keys:"клавиша",keyHint:"Мышь или клавиши по подписям · Shift — чёрные · пробел — сустейн",credits:"О звуке",
      demoOnly:"ПРЕДПРОСМОТР · настоящий звук · без сохранения, записи и экспорта",understood:"Понятно",play:"Играть",pause:"Пауза",resume:"Продолжить",
      collapse:"Свернуть клавиши",expand:"Показать клавиши",generated:"Сгенерировано",edited:"Ручная правка",edit:"Править",read:"Читать",
      followReady:"Играйте выделенную запись · допускаются 3 пропуска",followWait:"Не совпало — позиция сохранена",followOff:"Автопрокрутка выключена",followEdit:"Слежение приостановлено: правка",followDone:"Фрагмент пройден",followSkip:"Пропуск распознан",followPlayback:"Позиция проигрывания",followPaused:"Позиция сохранена · пауза",followManualText:"Ручной текст не связан со временем нот",
      unavailable:"Откройте preview_dark.py для настоящего звука и пересчёта.",notConnected:"Пока не подключено",futureOperation:"Это отдельный макет. Открытие ваших файлов, сохранение проектов, запись и экспорт будут подключены позже. Сейчас доступен только встроенный пример.",
      creditText:"Salamander Grand Piano V3 · Yamaha C5 · Alexander Holm · CC BY 3.0. Локальные сэмплы, три слоя удара; дополнительная реверберация создаётся внутри программы.",
      unchanged:"Буквы не изменились: для этого примера результат совпадает.",changed:"Новый результат готов. Исходные данные и ваши правки ещё не заменены.",
      metrics:"Нот: {selected} из {original} · Shift: {shiftKeys} · вне диапазона: {outside} · сдвиг: {shift}",
      idle:"Готово",playing:"Проигрывание",paused:"Пауза",loading:"Загрузка звуков…"
    },
    en: {
      open:"Open",save:"Save",export:"Export",settings:"Settings",close:"Close",notes:"Notes",sound:"Sound",view:"View",
      project:"Midnight study",exampleLabel:"BUILT-IN EXAMPLE · 8 MEASURES",livePreview:"Live preview",notation:"Letter notation",
      fontSize:"Letter size",follow:"Follow my playing",followReset:"Restart",textHint:"Text edits do not change the played notes.",bars:"measures",
      transpose:"Transpose",semitones:"semitones",best:"Find a comfortable key",fullness:"Chord fullness",easy:"Easy part",full:"All notes",layout:"Letter layout",
      preview:"Preview changes",apply:"Apply",cancel:"Cancel",tone:"Tone character",soft:"Soft",normal:"Normal",bright:"Bright",
      reverb:"Reverb",dry:"No effect",room:"Room",hall:"Hall",amount:"Effect amount",reverbHint:"0% adds no effect. 100% is wet sound only. Compare the same example with different presets.",
      compare:"Play example with this sound",resizeHint:"Drag the divider above the piano: keys resize without cropping. Collapse hides the entire keyboard.",
      reduceMotion:"Reduce motion",futureHint:"Always-on-top and compact play mode will be connected in the application.",
      conflict:"Replace your manual text with the new result?",keep:"Keep edits",replace:"Replace",stop:"Stop",record:"Record",speed:"Speed, %",volume:"Volume",sustain:"Sustain",
      keyLabels:"Labels",noLabels:"None",keys:"keys",keyHint:"Mouse or labelled keys · Shift: black keys · Space: sustain",credits:"About sound",
      demoOnly:"PREVIEW · real sound · no saving, recording or export",understood:"Got it",play:"Play",pause:"Pause",resume:"Resume",
      collapse:"Collapse keys",expand:"Show keys",generated:"Generated",edited:"Manual edit",edit:"Edit",read:"Read",
      followReady:"Play the highlighted notation · up to 3 skipped tokens",followWait:"No match — position preserved",followOff:"Auto-scroll off",followEdit:"Following paused: editing",followDone:"Section complete",followSkip:"Skipped token recognised",followPlayback:"Playback position",followPaused:"Position preserved · paused",followManualText:"Manual text has no link to note timing",
      unavailable:"Open preview_dark.py for real sound and processing.",notConnected:"Not connected yet",futureOperation:"This is an isolated preview. Opening your files, saving projects, recording and export will be connected later. Only the built-in example is available.",
      creditText:"Salamander Grand Piano V3 · Yamaha C5 · Alexander Holm · CC BY 3.0. Bundled samples, three velocity layers; extra reverb is generated locally.",
      unchanged:"Letters unchanged: this example produces the same result.",changed:"New result ready. Source data and manual edits have not been replaced.",
      metrics:"Notes: {selected}/{original} · Shift: {shiftKeys} · out of range: {outside} · transpose: {shift}",
      idle:"Ready",playing:"Playing",paused:"Paused",loading:"Loading samples…"
    },
    de: {
      open:"Öffnen",save:"Speichern",export:"Exportieren",settings:"Einstellungen",close:"Schließen",notes:"Noten",sound:"Klang",view:"Ansicht",
      project:"Mitternachtsetüde",exampleLabel:"INTEGRIERTES BEISPIEL · 8 TAKTE",livePreview:"Live-Entwurf",notation:"Buchstabennotation",
      fontSize:"Buchstabengröße",follow:"Meinem Spiel folgen",followReset:"Von vorn",textHint:"Textkorrekturen ändern die gespielten Noten nicht.",bars:"Takte",
      transpose:"Transponierung",semitones:"Halbtöne",best:"Bequeme Tonart finden",fullness:"Akkordumfang",easy:"Leichte Stimme",full:"Alle Noten",layout:"Buchstabenbelegung",
      preview:"Änderungsvorschau",apply:"Anwenden",cancel:"Abbrechen",tone:"Klangcharakter",soft:"Weich",normal:"Normal",bright:"Kräftig",
      reverb:"Nachhall",dry:"Kein Effekt",room:"Raum",hall:"Saal",amount:"Effektanteil",reverbHint:"0% ohne zusätzlichen Effekt. 100% nur Effektsignal. Dasselbe Beispiel mit verschiedenen Presets vergleichen.",
      compare:"Beispiel mit diesem Klang spielen",resizeHint:"Trennlinie oberhalb des Klaviers ziehen: ganze Tasten bleiben sichtbar. Einklappen verbirgt die gesamte Tastatur.",
      reduceMotion:"Bewegung reduzieren",futureHint:"Immer im Vordergrund und kompakter Spielmodus folgen in der Anwendung.",
      conflict:"Manuelle Korrekturen durch das neue Ergebnis ersetzen?",keep:"Korrekturen behalten",replace:"Ersetzen",stop:"Stopp",record:"Aufnahme",speed:"Tempo, %",volume:"Lautstärke",sustain:"Sustain",
      keyLabels:"Beschriftung",noLabels:"Keine",keys:"Tasten",keyHint:"Maus oder beschriftete Tasten · Shift: schwarze · Leertaste: Sustain",credits:"Über den Klang",
      demoOnly:"ENTWURF · echter Klang · ohne Speichern, Aufnahme oder Export",understood:"Verstanden",play:"Abspielen",pause:"Pause",resume:"Fortsetzen",
      collapse:"Tasten einklappen",expand:"Tasten anzeigen",generated:"Generiert",edited:"Manuell korrigiert",edit:"Bearbeiten",read:"Lesen",
      followReady:"Markierte Notation spielen · bis zu 3 übersprungene Zeichen",followWait:"Keine Übereinstimmung — Position beibehalten",followOff:"Automatisches Scrollen aus",followEdit:"Folgen pausiert: Bearbeitung",followDone:"Abschnitt abgeschlossen",followSkip:"Übersprungene Notation erkannt",followPlayback:"Wiedergabeposition",followPaused:"Position beibehalten · Pause",followManualText:"Manueller Text ist nicht mit den Notenzeiten verknüpft",
      unavailable:"preview_dark.py für echten Klang und Berechnung öffnen.",notConnected:"Noch nicht verbunden",futureOperation:"Dies ist ein separater Entwurf. Eigene Dateien, Projektspeicherung, Aufnahme und Export werden später verbunden. Nur das integrierte Beispiel ist verfügbar.",
      creditText:"Salamander Grand Piano V3 · Yamaha C5 · Alexander Holm · CC BY 3.0. Lokale Samples mit drei Anschlagstufen; zusätzlicher Hall wird lokal erzeugt.",
      unchanged:"Unveränderte Buchstaben: dieses Beispiel ergibt dasselbe Ergebnis.",changed:"Neues Ergebnis bereit. Originaldaten und Textkorrekturen wurden nicht ersetzt.",
      metrics:"Noten: {selected}/{original} · Shift: {shiftKeys} · außerhalb: {outside} · Versatz: {shift}",
      idle:"Bereit",playing:"Wiedergabe",paused:"Pausiert",loading:"Klänge werden geladen…"
    }
  };
  Object.assign(translations.ru,{minimize:"Свернуть окно",maximize:"Развернуть окно",restore:"Восстановить окно",closeApp:"Закрыть программу",keyHint:"Мышь или подписи · цифровой блок 0–9: с любым NumLock · Shift — чёрные · пробел — сустейн"});
  Object.assign(translations.en,{minimize:"Minimize window",maximize:"Maximize window",restore:"Restore window",closeApp:"Close application",keyHint:"Mouse or labels · numpad 0–9: either NumLock state · Shift: black keys · Space: sustain"});
  Object.assign(translations.de,{minimize:"Fenster minimieren",maximize:"Fenster maximieren",restore:"Fenster wiederherstellen",closeApp:"Programm schließen",keyHint:"Maus oder Beschriftung · Ziffernblock 0–9: unabhängig von NumLock · Shift: schwarze Tasten · Leertaste: Sustain"});
  Object.assign(translations.ru,{interfaceLanguage:"Язык интерфейса",physicalLayout:"Раскладка клавиатуры для игры",linkLanguageLayout:"Связать язык и раскладку",languageLayoutHint:"При смене языка меняются раскладка игры и подписи клавиш. Чтобы выбрать раскладку отдельно, отключите связь. Буквенная партитура не переписывается."});
  Object.assign(translations.en,{interfaceLanguage:"Interface language",physicalLayout:"Keyboard layout for playing",linkLanguageLayout:"Link language and keyboard layout",languageLayoutHint:"Changing language changes the playing layout and key labels. Unlink to choose a layout separately. Letter notation is not rewritten."});
  Object.assign(translations.de,{interfaceLanguage:"Sprache der Oberfläche",physicalLayout:"Tastaturbelegung zum Spielen",linkLanguageLayout:"Sprache und Tastaturbelegung verknüpfen",languageLayoutHint:"Ein Sprachwechsel ändert die Spielbelegung und Tastenbeschriftung. Für eine eigene Belegung die Verknüpfung deaktivieren. Die Buchstabennotation bleibt unverändert."});
  const $ = id => document.getElementById(id), $$ = selector => [...document.querySelectorAll(selector)];
  Object.assign(translations.ru,{followReady:"Играйте дальше · пропуски определяются по следующим нотам"});
  Object.assign(translations.en,{followReady:"Keep playing · skipped notes follow your next attacks"});
  Object.assign(translations.de,{followReady:"Weiterspielen · nächste Noten erkennen übersprungene Zeichen"});
  Object.assign(translations.ru,{rhythmHints:"Показывать паузы",rest:"Пауза",quarterBeats:"доли"});
  Object.assign(translations.en,{rhythmHints:"Show rests",rest:"Rest",quarterBeats:"beats"});
  Object.assign(translations.de,{rhythmHints:"Pausen anzeigen",rest:"Pause",quarterBeats:"Viertel"});
  const state = {lang:"ru",physical:"ru",editing:false,edited:false,settings:false,tab:"notes",piano:true,ready:false,keyHeight:220,layout:"ru",applied:null,proposal:null,request:0,applying:false};
  let bridge, tokens=[], cursor=0, message="followReady", held=new Map(), recent=new Map(), noticeFocus, settingsFocus, playbackStatus="";
  let rests=[],activeRest=null,editingView=null,lastEditorSelection=null;
  const physical="1234567890QWERTYUIOPASDFGHJKLZXCVBNM";
  const ru="1234567890йцукенгшщзфывапролдячсмить";
  const digits={ru:['!','"','№',';','%',':','?','*','(',')'],en:['!','@','#','$','%','^','&','*','(',')'],de:['!','"','§','$','%','&','/','(',')','=']};
  const mapping={}; let white=0;
  for(let midi=36;midi<=96;midi++){const shift=[1,3,6,8,10].includes(midi%12);mapping[midi]={key:physical[shift?white-1:white++],shift};}
  const t = key => translations[state.lang][key] || key;
  const readyStatus = {ru:"Сэмплер офлайн · звуки загружены",en:"Offline sampler · samples loaded",de:"Offline-Sampler · Klänge geladen"};
  const engine = () => window.vpaPiano;
  const call = (method,...args) => new Promise((resolve,reject) => {
    if(!bridge){reject(new Error(t("unavailable")));return;}
    bridge[method](...args,raw=>{try{const result=JSON.parse(raw);if(result.error)throw new Error(result.error);resolve(result);}catch(error){reject(error);}});
  });
  function label(midi,layout){
    const info=mapping[midi];if(!info)return "?";
    const index=physical.indexOf(info.key);let base=layout==="ru"?ru[index]:info.key.toLowerCase();
    if(layout==="de"){if(base==="y")base="z";else if(base==="z")base="y";}
    return info.shift?(index<10?digits[layout][index]:base.toUpperCase()):base;
  }
  function labels(){
    const mode=$("key-labels").value;
    $$(".key").forEach(key=>{key.querySelector("span").textContent=mode==="none"?"":label(Number(key.dataset.midi),mode);});
  }
  function keyboardChanged(){
    document.dispatchEvent(new CustomEvent("vpa-keyboard-change",{detail:{language:state.lang,physical:state.physical}}));
  }
  function setPhysical(value){
    if(!["ru","en","de"].includes(value))return;
    engine()?.releaseManual(true);state.physical=value;
    if($("key-labels").value!=="none")$("key-labels").value=value;
  }
  function setLanguage(value){
    if(!["ru","en","de"].includes(value))return;
    state.lang=value;if($("link-language-layout").checked)setPhysical(value);
    render();transport();keyboardChanged();
  }
  function keyboardSkin(){
    // Real black keys sit off-centre between the white keys in each octave.
    let white=0;const offset={1:-.08,3:.08,6:-.1,8:0,10:.1};
    $$(".key").forEach(key=>{const midi=Number(key.dataset.midi),black=key.classList.contains("black");
      key.style.width=(black?.62:1)*100/36+"%";
      key.style.left=(black?white-.31+offset[midi%12]:white++)*100/36+"%";
    });
    labels();
  }
  function modality(){
    document.querySelector(".app").inert=state.settings||window.vpaDocument?.blocked()||window.vpaRecordingUI?.blocked()||!$("notice").hidden;
    $("settings").inert=window.vpaDocument?.blocked()||window.vpaRecordingUI?.blocked()||!$("notice").hidden;
  }
  function settings(open=!state.settings){
    if(!document.querySelector('[data-tab="'+state.tab+'"]'))state.tab="sound";
    if(open){engine()?.releaseManual(true);settingsFocus=document.activeElement===document.body?document.querySelector(".app [data-action=settings]"):document.activeElement;}
    state.settings=open;render();
    if(open)document.querySelector("#settings [data-action=settings]").focus();
    else settingsFocus?.focus();
  }
  function windowState(maximized){
    document.documentElement.classList.toggle("maximized",maximized);render();
  }
  function reading(structured){
    tokens=[];rests=[];activeRest=null;cursor=0;recent.clear();pendingFollow=[];message="followReady";$("reading").replaceChildren();
    const content=document.createElement("div");content.id="reading-text";$("reading").append(content);
    let row,offset=0;
    const newRow=(separator='\n')=>{
      if(row){content.append(document.createTextNode(separator));offset+=separator.length;}
      row=document.createElement('span');row.className='notation-row';content.append(row);
    };
    const text=value=>{row.append(document.createTextNode(value));offset+=value.length;};
    const add=(text,pitches,start,rhythm,originalPitches)=>{
      const span=document.createElement("span");span.className="notation-token";span.textContent=text;const index=tokens.length;
      span.addEventListener("click",()=>{cursor=index;recent.clear();pendingFollow=[];updateReading(true);});
      tokens.push({span,pitches,start,originalPitches,textOffset:offset});offset+=text.length;row.append(span);
    };
    if(structured){
      const separator=state.applied?.spacing===false?"":" ";
      const restMark=r=>{
        const span=document.createElement('span');span.className='notation-rest';
        const [numerator,denominator=1]=r.duration.split('/').map(Number);
        span.title=t('rest')+': '+new Intl.NumberFormat(state.lang,{maximumFractionDigits:3}).format(numerator/denominator)+' '+t('quarterBeats');span.setAttribute('aria-label',span.title);
        for(const symbol of r.symbols||[{kind:'quarter',dots:0}]){
          const glyph=document.createElement('span');glyph.className='rest-glyph';
          glyph.dataset.label=symbol.tuplet?'3':symbol.approximate?'≈':'';
          const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 28 44');svg.setAttribute('aria-hidden','true');
          const shape=(tag,attrs)=>{const el=document.createElementNS(svg.namespaceURI,tag);for(const [key,value] of Object.entries(attrs))el.setAttribute(key,value);svg.append(el);};
          if(symbol.kind==='whole'||symbol.kind==='half'){
            shape('rect',{x:4,y:15,width:18,height:1});shape('rect',{x:7,y:symbol.kind==='whole'?16:10,width:12,height:6});
          }else if(symbol.kind==='quarter'){
            shape('path',{d:'M12 3 L21 13 L14 20 L20 28 C9 23 7 28 15 38 C1 33 5 24 13 25 L7 18 L15 11 Z'});
          }else{
            const flags={eighth:1,sixteenth:2,thirtysecond:3,sixtyfourth:4}[symbol.kind]||1;
            shape('path',{d:'M19 7 L11 39',fill:'none',stroke:'currentColor','stroke-width':2});
            for(let i=0;i<flags;i++){const y=8+i*7;shape('circle',{cx:9,cy:y,r:3});shape('path',{d:`M8 ${y+2} Q15 ${y+7} 19 ${y-1}`,fill:'none',stroke:'currentColor','stroke-width':2});}
          }
          for(let dot=0;dot<(symbol.dots||0);dot++)shape('circle',{cx:24,cy:20+dot*7,r:1.6});
          glyph.append(svg);span.append(glyph);
        }
        row.append(span);rests.push({span,start:r.start,end:r.end});
      };
      let measure=0;
      const hints=state.applied?.rhythm||[];
      if(hints.length){
        for(const hint of hints){
          const entries=structured.filter(x=>x.measure===hint.measure);
          newRow(entries.length&&measure?'\n':'');if(!entries.length)row.classList.add('rest-only');let count=0;
          let rest=0;
          for(const token of entries){
            while(rest<hint.rests.length&&hint.rests[rest].onset<=token.onset)restMark(hint.rests[rest++]);
            if(count++)text(separator);
            measure=token.measure;add(token.label,token.pitches,token.start,token.beat,token.originalPitches);
          }
          while(rest<hint.rests.length)restMark(hint.rests[rest++]);
        }
      }else for(const token of structured){if(measure!==token.measure)newRow();else text(separator);measure=token.measure;add(token.label,token.pitches,token.start,undefined,token.originalPitches);}
    }else{
      const lines=$("notation").value.split(/(\r\n|\r|\n)/);
      for(let i=0;i<lines.length;i+=2){
        newRow(i?lines[i-1]:'');const line=lines[i],pattern=/\[[^\]\r\n]*\]|\([^()\s]{2,}\)|[^\s]/g;let last=0,match;
        while((match=pattern.exec(line))){text(line.slice(last,match.index));
          const grouped=match[0].startsWith("[")||(match[0].startsWith("(")&&match[0].endsWith(")")&&match[0].length>3);
          const chars=grouped?[...match[0].slice(1,-1)]:[match[0]];
          add(match[0],chars.map(char=>Number(Object.keys(mapping).find(midi=>label(Number(midi),state.layout)===char)) || undefined));last=pattern.lastIndex;}
        text(line.slice(last));
      }
    }
    $('reading').classList.toggle('rhythm-hints',$('rhythm-hints').checked);updateReading(false);
  }
  function followPlayback(audio){
    const active=audio.playing||audio.paused||audio.completed;
    if(active){
      if(audio.completed&&playbackStatus==="completed")return;
      const started=!playbackStatus;playbackStatus=audio.completed?"completed":"active";recent.clear();pendingFollow=[];
      // Edited letters deliberately have no invented timing or effect on the score.
      if(state.edited||state.editing){activeRest=null;message=state.edited?"followManualText":"followEdit";updateReading(false);return;}
      let index=0;
      while(index+1<tokens.length&&Number.isFinite(tokens[index+1].start)&&tokens[index+1].start<=audio.scorePosition+0.001)index++;
      if(audio.completed)index=tokens.length;
      const rest=audio.completed||!$('rhythm-hints').checked?null:rests.find(r=>Number.isFinite(r.start)&&r.start<=audio.scorePosition&&audio.scorePosition<r.end)||null;
      const changed=started||cursor!==index||activeRest!==rest;activeRest=rest;cursor=index;message=audio.paused?"followPaused":audio.completed?"followDone":"followPlayback";
      updateReading(changed);
    }else if(playbackStatus&&!audio.starting){
      playbackStatus="";activeRest=null;cursor=0;message="followReady";updateReading(true);
    }
  }
  function updateReading(scroll){
    tokens.forEach((token,index)=>{token.span.classList.toggle("current",!activeRest&&index===cursor);token.span.classList.toggle("done",index<cursor||Boolean(activeRest)&&token.start<=activeRest.start);});
    rests.forEach(rest=>rest.span.classList.toggle('current',rest===activeRest));
    $("follow-status").textContent=t(state.editing?"followEdit":!$("follow").checked?"followOff":cursor>=tokens.length?"followDone":message);
    const selected=activeRest?.span||tokens[cursor]?.span;
    if(scroll && $("follow").checked && !state.editing && selected){
      const pane=$("reading"),rect=pane.getBoundingClientRect(),target=selected.getBoundingClientRect();
      if(target.bottom>rect.bottom-25||target.top<rect.top+10)pane.scrollTop+=target.top-rect.top-rect.height*.35;
    }
  }
  function matchedToken(tokens,cursor,recent,midi){
    // Prefer the current attack, then the nearest full new-attack match.
    // Bounded lookahead cannot jump to a distant repetition in the song.
    for(let i=cursor;i<Math.min(tokens.length,cursor+7);i++){
      const required=tokens[i]?.pitches;
      if(required?.length&&required.includes(midi)&&required.every(p=>p!==undefined&&recent.has(p)))return i;
      // One member of the current chord is not evidence that the player
      // jumped to a later single note with the same pitch. Explicit token
      // clicking remains available for that inherently ambiguous skip.
      if(i===cursor&&required?.includes(midi))return -1;
    }
    return -1;
  }
  let pendingFollow=[];
  function followDecision(tokens,cursor,recent,midi,pending,now){
    const local=matchedToken(tokens,cursor,recent,midi);
    if(local===cursor)return {index:local,pending:[]};
    // A distant or repeated-pitch position needs two successive fresh attacks.
    // An unfinished current chord remains completable; no mouse is required.
    for(const candidate of pending){
      const index=candidate.index+1,required=tokens[index]?.pitches;
      if(index>=cursor&&required?.includes(midi)&&required.every(p=>recent.has(p)&&recent.get(p)>candidate.at))return {index,pending:[]};
    }
    if(local>=0)return {index:local,pending:[]};
    const next=[];
    for(let i=cursor+1;i<tokens.length;i++){
      const required=tokens[i].pitches;
      if(required?.includes(midi)&&required.every(p=>p!==undefined&&recent.has(p)))next.push({index:i,at:now});
    }
    return {index:-1,pending:next.length?next:pending.filter(c=>tokens[c.index+1]?.pitches?.includes(midi))};
  }
  function track(midi){
    if(!state.ready||state.editing||!$("follow").checked||engine()?.state().playing)return;
    activeRest=null;
    const now=performance.now();for(const[p,at]of recent)if(now-at>300)recent.delete(p);recent.set(midi,now);
    const result=followDecision(tokens,cursor,recent,midi,pendingFollow,now);pendingFollow=result.pending;const matched=result.index;
    if(matched>=0){message=matched>cursor?"followSkip":"followReady";cursor=matched+1;recent.clear();updateReading(true);return;}
    message="followWait";updateReading(false);
  }
  function renderProposal(){
    window.vpaDocument?.refreshControls();
    const p=state.proposal;if(!p){$("proposal-text").textContent=t("unavailable");return;}
    const lines=p.text.split("\n");
    $("proposal-text").textContent=$("notation-overlay")?lines.slice(0,5).join("\n")+(lines.length>5?"\n…":""):p.text;
    $("proposal-metrics").textContent=t("metrics").replace(/\{(\w+)\}/g,(_,key)=>p[key]);
    if(p.registerMoves)$("proposal-metrics").textContent+=' · '+({ru:'Октавных переносов: ',en:'Octave moves: ',de:'Oktavierungen: '}[state.lang])+p.registerMoves;
    $("proposal-message").textContent=t(p.text===state.applied?.text?"unchanged":"changed");
    $("fullness-value").textContent=$("fullness").value+"%";
  }
  function render(){
    document.documentElement.lang=state.lang;$$("[data-t]").forEach(el=>{
      if(el.classList.contains("gold-key")){let span=el.querySelector(".gold-label");if(!span){span=document.createElement("span");span.className="gold-label";el.replaceChildren(span);}if(span.textContent!==t(el.dataset.t))span.textContent=t(el.dataset.t);}
      else el.textContent=t(el.dataset.t);
    });
    $$("[data-lang]").forEach(el=>el.setAttribute("aria-pressed",String(el.dataset.lang===state.lang)));
    $("interface-language").value=state.lang;$("physical-layout").value=state.physical;
    $("physical-layout").disabled=$("link-language-layout").checked;
    $$("[data-action=settings]").forEach(el=>el.setAttribute("aria-expanded",String(state.settings)));
    $("settings-overlay").hidden=!state.settings;modality();
    $$("[data-window]").forEach(el=>{const key=el.dataset.window==="close"?"closeApp":el.dataset.window==="maximize"&&document.documentElement.classList.contains("maximized")?"restore":el.dataset.window;el.title=t(key);el.setAttribute("aria-label",t(key));el.disabled=!bridge;});
    $$("[data-tab]").forEach(el=>el.setAttribute("aria-selected",String(el.dataset.tab===state.tab)));
    $$("[data-pane]").forEach(el=>el.hidden=el.dataset.pane!==state.tab);
    $("reading").hidden=state.editing;$("notation").hidden=!state.editing;
    if(state.editing)alignEditor();
    $("text-status").textContent=t(state.edited?"edited":"generated");$("edit-label").textContent=t(state.editing?"read":"edit");
    $("piano-body").hidden=!state.piano;$("splitter").hidden=!state.piano;
    $("collapse-label").textContent=t(state.piano?"collapse":"expand");$("collapse-label").setAttribute("aria-expanded",String(state.piano));
    $("room-value").textContent=$("room").value+"%";$("room").disabled=$("reverb-preset").value==="off";
    $("transport-toggle").disabled=!state.ready||(window.vpaDocument?.active && !state.applied?.playable);
    renderProposal();labels();updateReading(false);
    window.vpaRecordingUI?.render();
    window.vpaDocument?.render();
    if(state.piano)setHeight(state.keyHeight);
    engine()?.setLanguage({ru:"Русский",en:"English",de:"Deutsch"}[state.lang]);
  }
  async function proposal(best=false){
    const sequence=++state.request;
    try{
      const mode=$("practice-mode")?.value||"normal";
      const result=window.vpaDocument?.active?(best?await call("bestPractice",Number($("fullness").value),$("layout").value,mode):await call("previewPractice",Number($("transpose").value),Number($("fullness").value),$("layout").value,mode)):(best?await call("best",Number($("fullness").value),$("layout").value):await call("preview",Number($("transpose").value),Number($("fullness").value),$("layout").value));
      if(sequence!==state.request)return;
      state.proposal=result;if(best)$("transpose").value=result.shift;renderProposal();
    }catch(error){$("proposal-message").textContent=error.message;}
  }
  async function apply(replace=false){
    if(!bridge||state.applying)return;
    if(state.edited&&!replace){$("conflict").hidden=false;document.querySelector("[data-action=keep]").focus();return;}
    state.applying=true;
    ++state.request;
    const shift=Number($("transpose").value),fullness=Number($("fullness").value),layout=$("layout").value;
    try{
      const request=state.request;
      const result=window.vpaDocument?.active?await call("applyPractice",shift,fullness,layout,$("practice-mode")?.value||"normal",replace):await call("apply",shift,fullness,layout);
      if(request!==state.request)return;
      engine()?.panic();state.applied=result;state.proposal=result;state.layout=result.layout;state.edited=false;
      $("notation").value=result.text;$("conflict").hidden=true;
      if($("key-labels").value!=="none")$("key-labels").value=result.layout;
      reading(result.tokens);render();
    }catch(error){$("proposal-message").textContent=error.message;}
    finally{state.applying=false;}
  }
  function cancel(){
    ++state.request;const p=state.applied;if(p){$("transpose").value=p.shift;$("fullness").value=p.fullness;$("layout").value=p.layout;if($("practice-mode"))$("practice-mode").value=p.practiceMode||"normal";state.proposal=p;}
    $("conflict").hidden=true;renderProposal();
  }
  function notice(title,text){
    engine()?.releaseManual(true);noticeFocus=document.activeElement;
    $("notice-title").textContent=t(title);$("notice-text").textContent=t(text);$("notice").hidden=false;
    modality();
    document.querySelector("[data-action=notice-close]").focus();
  }
  function hideNotice(){$("notice").hidden=true;modality();noticeFocus?.focus();}
  async function play(){
    window.vpaRecording?.stopListening();
    if(!state.ready)return;const audio=engine(),current=audio.state();
    if(current.playing)audio.pausePlayback();else if(current.paused)await audio.resumePlayback();else await audio.playProject();
    transport();
  }
  function transport(){
    if(engine()?.state().preview)return; // audition is not the open score's clock
    const audio=engine()?.state()||{playing:false,paused:false,position:0,duration:0};
    const duration=audio.duration || (state.applied?.duration||17.45)/(Number($("tempo").value)/100);
    const format=n=>String(Math.floor(n/60)).padStart(2,"0")+":"+String(Math.floor(n%60)).padStart(2,"0");
    $("play-label").textContent=t(audio.playing?"pause":audio.paused?"resume":"play");
    $("transport-toggle").classList.toggle("is-playing",audio.playing);$("transport-toggle").setAttribute("aria-pressed",String(audio.playing));
    $("position").max=duration;$("position").value=audio.position;$("time").textContent=format(audio.position)+" / "+format(duration);
    $("transport-status").textContent=t(audio.playing?"playing":audio.paused?"paused":"idle");
    followPlayback(audio);
  }
  function setHeight(value,persist=false){
    const pane=document.querySelector(".letter-panel");
    const current=parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--key-height"))||220;
    const notation=state.editing?$("notation"):$("reading");
    // Wrapped warnings and translated controls consume space outside the score.
    // Reserve a readable viewport, not a fixed total panel height. Auto-fitting
    // must not overwrite the user's preferred splitter position.
    const chrome=pane.getBoundingClientRect().height-notation.getBoundingClientRect().height;
    const minimum=Math.max($("notation-settings")?189:165,chrome+96);
    pane.style.minHeight=minimum+"px";
    const main=document.querySelector("main");
    const overflow=Math.max(0,main.scrollHeight-main.clientHeight);
    const available=current+pane.getBoundingClientRect().height-minimum-overflow;
    const next=Math.max(innerHeight<=720?96:112,Math.min(260,available,value));
    document.documentElement.style.setProperty("--key-height",next+"px");
    $("splitter").setAttribute("aria-valuenow",String(Math.round(next)));
    if(persist){state.keyHeight=next;bridge?.setKeyHeight(Math.round(next));}
  }
  window.vpaPianoHost={
    mapping,
    soundPitch:midi=>{
      if(state.edited||state.editing||!$("follow").checked||engine()?.state().playing)return undefined;
      const now=performance.now(),attacks=new Map([...recent].filter(([,at])=>now-at<=300));attacks.set(midi,now);
      const match=followDecision(tokens,cursor,attacks,midi,pendingFollow,now).index;
      const target=match>=0?tokens[match]:tokens.slice(cursor,cursor+7).find(t=>t.pitches?.includes(midi));
      const index=target?.pitches?.indexOf(midi),pitch=target?.originalPitches?.[index];
      return Number.isInteger(pitch)?pitch+Number(state.applied?.shift||0)+Number(state.applied?.pianoShift||0):undefined;
    },
    onStatus:value=>{$("status").textContent=/^(Готово ·|Ready ·|Bereit ·)/.test(value)?readyStatus[state.lang]:value;},
    onConfiguration:config=>{Object.assign(mapping,config.mapping);labels();},
    onKeys:keyboardSkin,
    onReady:()=>{state.ready=true;render();transport();},
    canPlay:()=>state.ready&&!state.editing&&!state.settings&&!window.vpaDocument?.blocked()&&!window.vpaRecordingUI?.blocked()&&window.vpaRecording?.state().phase!=="finishing"&&$("notice").hidden,
    onNote:(midi,token,down)=>{if(down){held.set(token,midi);track(midi);}else held.delete(token);},
    onManualClear:()=>{held.clear();recent.clear();},
    onBridge:async (value,recorder)=>{
      bridge=value;bridge.windowStateChanged.connect(windowState);bridge.windowMaximized(windowState);
      await window.vpaRecording?.configure(recorder);
      if(typeof bridge.document==="function")await window.vpaDocument.configure(bridge);
      else {const initial=await call("preview",0,100,"ru");
        state.applied=initial;state.proposal=initial;$("notation").value=initial.text;reading(initial.tokens);}
      bridge.keyHeight(value=>{state.keyHeight=value;setHeight(value);});
      render();
    }
  };
  document.addEventListener("click",async event=>{
    const button=event.target.closest("button[data-action],button[data-lang],button[data-tab]");if(!button)return;
    if(button.dataset.lang){setLanguage(button.dataset.lang);return;}
    if(button.dataset.tab){state.tab=button.dataset.tab;render();return;}
    switch(button.dataset.action){
      case "settings":settings();break;
      case "edit":engine()?.releaseManual(true);toggleEdit();break;
      case "piano":engine()?.releaseManual(true);state.piano=!state.piano;render();if(state.piano)setHeight(state.keyHeight);break;
      case "play":await play();break;
      case "compare":await engine()?.playProject();transport();break;
      case "follow-reset":cursor=0;recent.clear();pendingFollow=[];message="followReady";updateReading(true);break;
      case "best":await proposal(true);break;
      case "apply":await apply();break;
      case "replace":await apply(true);break;
      case "keep":cancel();break;
      case "cancel":cancel();break;
      case "credits":notice("credits","creditText");break;
      case "notice-close":hideNotice();break;
      case "record":await window.vpaRecordingUI?.record();break;
      case "export":if(window.vpaDocument?.active&&!button.closest("#recording-bar"))window.vpaDocument.dialog("export");else window.vpaRecordingUI?.exportDialog();break;
      case "open":if(window.vpaDocument?.active){if(window.vpaDocument.info().busy)window.vpaDocument.dialog("open");else await window.vpaDocument.action("open");}else notice("notConnected","futureOperation");break;
      case "save":if(window.vpaDocument?.active)await window.vpaDocument.action("save");else notice("notConnected","futureOperation");break;
    }
  });
  $("settings-overlay").addEventListener("click",event=>{if(event.target===$("settings-overlay"))settings(false);});
  $$("[data-window]").forEach(el=>el.addEventListener("click",()=>el.dataset.window==="close"?window.vpaRecording.requestClose():bridge?.windowAction(el.dataset.window)));
  document.querySelector(".topbar").addEventListener("pointerdown",event=>{if(event.button===0&&!event.target.closest("button,nav"))bridge?.windowAction("move");});
  document.querySelector(".topbar").addEventListener("dblclick",event=>{if(event.button===0&&!event.target.closest("button,nav"))bridge?.windowAction("maximize");});
  $$("[data-resize]").forEach(el=>el.addEventListener("pointerdown",event=>{if(event.button===0){event.preventDefault();bridge?.windowAction("resize-"+el.dataset.resize);}}));
  document.addEventListener("keydown",event=>{
    if(window.vpaDocument?.keyDown(event))return;
    if(window.vpaRecordingUI?.keyDown(event))return;
    if(!$("notice").hidden){
      if(event.code==="Escape"){event.preventDefault();hideNotice();}
      if(event.code==="Tab"){event.preventDefault();document.querySelector("[data-action=notice-close]").focus();}
      return;
    }
    if(state.settings){
      if(event.code==="Escape"){event.preventDefault();settings(false);return;}
      if(event.code==="Tab"){
        const focusable=[...$("settings").querySelectorAll('button:not(:disabled),input:not(:disabled),select:not(:disabled)')].filter(el=>el.getClientRects().length);
        const first=focusable[0],last=focusable.at(-1);
        if(event.shiftKey&&document.activeElement===first){event.preventDefault();last?.focus();}
        else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus();}
      }
    }
    const tab=event.target.closest("[data-tab]");
    if(tab&&["ArrowLeft","ArrowRight"].includes(event.code)){
      event.preventDefault();const names=$$("[data-tab]").map(el=>el.dataset.tab);state.tab=names[(names.indexOf(state.tab)+(event.code==="ArrowRight"?1:names.length-1))%names.length];render();document.querySelector('[data-tab="'+state.tab+'"]').focus();
    }
  });
  $("notation").addEventListener("input",()=>{state.edited=true;window.vpaDocument?.syncText();reading();render();});
  const editableTarget=target=>Boolean(target.closest('textarea,input[type=text],input[type=number],[contenteditable="true"]'));
  document.addEventListener('pointerdown',()=>document.documentElement.classList.remove('keyboard-navigation'),true);
  document.addEventListener('keydown',event=>{if(event.code==='Tab')document.documentElement.classList.add('keyboard-navigation');},true);
  for(const name of ['selectstart','dragstart'])document.addEventListener(name,event=>{if(!editableTarget(event.target))event.preventDefault();});
  $("notation").addEventListener("focus",()=>engine()?.releaseManual(true));
  $("font-size").addEventListener("input",()=>{document.documentElement.style.setProperty("--letter-size",$("font-size").value+"px");$("font-value").textContent=$("font-size").value;updateReading(true);alignEditor();});
  $("follow").addEventListener("change",()=>{recent.clear();updateReading(false);});
  $('rhythm-hints').addEventListener('change',()=>{$('reading').classList.toggle('rhythm-hints',$('rhythm-hints').checked);transport();});
  // Run after the sampler's Stop handler, before the next manual note arrives.
  $("stop").addEventListener("click",()=>queueMicrotask(transport));
  $("key-labels").addEventListener("change",labels);
  $("interface-language").addEventListener("change",event=>setLanguage(event.target.value));
  $("link-language-layout").addEventListener("change",()=>{if($("link-language-layout").checked)setPhysical(state.lang);render();keyboardChanged();});
  $("physical-layout").addEventListener("change",event=>{$("link-language-layout").checked=false;setPhysical(event.target.value);render();keyboardChanged();});
  for(const id of ["transpose","fullness","layout"])$(id).addEventListener("input",()=>{ $("fullness-value").textContent=$("fullness").value+"%";proposal();});
  $("reverb-preset").addEventListener("change",()=>{engine()?.setReverb($("reverb-preset").value,Number($("room").value));render();});
  $("room").addEventListener("input",()=>{$("room-value").textContent=$("room").value+"%";});
  $("reduced-motion").addEventListener("change",()=>document.documentElement.classList.toggle("reduce-motion",$("reduced-motion").checked));
  let drag;
  $("splitter").addEventListener("pointerdown",event=>{if(event.button!==0)return;drag={y:event.clientY,height:parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--key-height"))};$("splitter").setPointerCapture(event.pointerId);event.preventDefault();});
  $("splitter").addEventListener("pointermove",event=>{if(drag)setHeight(drag.height+drag.y-event.clientY);});
  const endDrag=()=>{if(drag){setHeight(parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--key-height")),true);drag=null;}};
  $("splitter").addEventListener("pointerup",endDrag);$("splitter").addEventListener("pointercancel",endDrag);
  $("splitter").addEventListener("keydown",event=>{if(["ArrowUp","ArrowDown"].includes(event.code)){event.preventDefault();setHeight(state.keyHeight+(event.code==="ArrowUp"?8:-8),true);}});
  function alignEditor(){
    const editor=$("notation");
    if(editor.hidden)return;
    editor.style.paddingInline='24px';
  }
  function caretTop(offset){
    const editor=$('notation'),style=getComputedStyle(editor),mirror=document.createElement('div');
    for(const name of ['font','lineHeight','letterSpacing','padding','textAlign','tabSize'])mirror.style[name]=style[name];
    Object.assign(mirror.style,{position:'absolute',visibility:'hidden',boxSizing:'border-box',width:editor.clientWidth+'px',whiteSpace:'pre-wrap',overflowWrap:'normal',left:'-10000px'});
    const marker=document.createElement('span');marker.textContent='\u200b';mirror.append(document.createTextNode(editor.value.slice(0,offset)),marker,document.createTextNode(editor.value.slice(offset)||' '));document.body.append(mirror);
    const top=marker.getBoundingClientRect().top-mirror.getBoundingClientRect().top;mirror.remove();return top;
  }
  function toggleEdit(){
    const pane=$('reading'),editor=$('notation');
    if(!state.editing){
      const rect=pane.getBoundingClientRect(),anchor=tokens.reduce((best,token)=>Math.abs(token.span.getBoundingClientRect().top-rect.top-20)<Math.abs(best.span.getBoundingClientRect().top-rect.top-20)?token:best,tokens[0]);
      editingView={top:pane.scrollTop,left:pane.scrollLeft,cursor,text:editor.value,offset:anchor?.textOffset||0,relative:anchor?anchor.span.getBoundingClientRect().top-rect.top:20};
      const selection=lastEditorSelection?.text===editor.value&&lastEditorSelection.top===pane.scrollTop?lastEditorSelection:{start:editingView.offset,end:editingView.offset,direction:'none'};
      state.editing=true;activeRest=null;render();editor.focus({preventScroll:true});editor.setSelectionRange(selection.start,selection.end,selection.direction);
      const top=Math.max(0,caretTop(editingView.offset)-editingView.relative);editor.scrollTop=top;editor.scrollLeft=0;
      Object.assign(editingView,{selectionStart:selection.start,selectionEnd:selection.end,editorTop:editor.scrollTop});
      requestAnimationFrame(()=>{if(state.editing)editor.scrollTop=top;});
    }else{
      const selection={start:editor.selectionStart,end:editor.selectionEnd,direction:editor.selectionDirection,text:editor.value,scrollTop:editor.scrollTop},relative=caretTop(selection.start)-editor.scrollTop;
      state.editing=false;reading(state.edited?undefined:state.applied?.tokens);render();pane.focus({preventScroll:true});
      const sameText=editingView?.text===editor.value;
      if(sameText){cursor=editingView.cursor;updateReading(false);}
      if(sameText&&selection.start===editingView.selectionStart&&selection.end===editingView.selectionEnd&&Math.abs(selection.scrollTop-editingView.editorTop)<2){pane.scrollTop=editingView.top;pane.scrollLeft=editingView.left;}
      else{const anchor=[...tokens].reverse().find(token=>token.textOffset<=selection.start);if(anchor)pane.scrollTop+=anchor.span.getBoundingClientRect().top-pane.getBoundingClientRect().top-relative;}
      lastEditorSelection={...selection,top:pane.scrollTop};editingView=null;
    }
  }
  window.addEventListener("resize",()=>{if(state.piano)setHeight(state.keyHeight);alignEditor();});
  function loadDocument(value){
    ++state.request;state.applied=value;state.proposal=value;state.layout=value.layout;state.lang=value.language;
    state.physical=value.physical;
    state.edited=value.manual;state.editing=false;playbackStatus="";editingView=null;lastEditorSelection=null;
    $("notation").value=value.visibleText;$("transpose").value=value.shift;$("fullness").value=value.fullness;$("layout").value=value.layout;
    $("conflict").hidden=true;reading(value.manual?undefined:value.tokens);render();
  }
  function restoreView(value){
    for(const[id,key]of[["font-size","fontSize"],["key-labels","keyLabels"],["volume","volume"],["tempo","speed"],["layer","layer"],["reverb-preset","reverbPreset"],["room","reverbAmount"]])$(id).value=value[key];
    $('rhythm-hints').checked=value.rhythmHints!==false;$('reading').classList.toggle('rhythm-hints',value.rhythmHints!==false);
    $("follow").checked=value.follow;$("reduced-motion").checked=value.reducedMotion;$("link-language-layout").checked=value.linkLanguageLayout!==false;state.piano=value.piano;
    document.documentElement.classList.toggle("reduce-motion",value.reducedMotion);
    document.documentElement.style.setProperty("--letter-size",value.fontSize+"px");$("font-value").textContent=value.fontSize;render();
  }
  window.vpaPreview={state:()=>({...state,cursor,tokenCount:tokens.length}),proposal,apply,cancel,setHeight,modality,loadDocument,restoreView,
    syncManual:manual=>{
      const changed=state.edited!==manual,pane=$('reading'),top=pane.scrollTop,left=pane.scrollLeft;
      state.edited=manual;if(!state.editing&&changed){reading(manual?undefined:state.applied?.tokens);pane.scrollTop=top;pane.scrollLeft=left;}render();
    },
    close:()=>window.vpaDocument?.active?window.vpaDocument.action("close"):bridge?.windowAction("close")};
  $("status").textContent=typeof qt==="undefined"?t("unavailable"):t("loading");
  render();transport();setInterval(transport,80);
})();
