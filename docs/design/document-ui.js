"use strict";
// Document operations use the accepted Python handlers; audio stays in its host.
(() => {
  const text={
    ru:{open:"Открыть",export:"Экспорт",xml:"MusicXML — открыть",merge:"MusicXML — объединить страницы",project:"Открыть проект VPA",source:"PDF или изображение",recognize:"Распознать выбранный источник",txt:"Буквенная запись — TXT",audio:"Запись игры — аудио",dismiss:"Закрыть",pdf:"Страница PDF",untitled:"Без названия",empty:"Откройте MusicXML, проект или источник для распознавания.",label:"ВАШ ПРОЕКТ",live:"Рабочий интерфейс",footer:"ПРОЕКТЫ · буквенная запись · локальное пианино · запись и экспорт",pending:"Источник выбран · требуется распознавание",legacy:"Точное проигрывание недоступно: импортируйте MusicXML заново.",recording:"Сначала завершите запись или экспорт аудио.",recognizing:"Распознавание выполняется. Дождитесь результата.",physical:"Физическая раскладка",error:"Действие не выполнено.",compare:"Проиграть партитуру с этим звуком"},
    en:{open:"Open",export:"Export",xml:"Open MusicXML",merge:"Merge MusicXML pages",project:"Open VPA project",source:"PDF or image",recognize:"Recognise selected source",txt:"Letter notation — TXT",audio:"Recorded playing — audio",dismiss:"Close",pdf:"PDF page",untitled:"Untitled",empty:"Open MusicXML, a project or a source for recognition.",label:"YOUR PROJECT",live:"Application",footer:"PROJECTS · letter notation · local piano · recording and export",pending:"Source selected · recognition needed",legacy:"Exact playback unavailable: reimport MusicXML.",recording:"Finish recording or audio export first.",recognizing:"Recognition is running. Wait for the result.",physical:"Physical keyboard layout",error:"Operation failed.",compare:"Play score with this sound"},
    de:{open:"Öffnen",export:"Exportieren",xml:"MusicXML öffnen",merge:"MusicXML-Seiten zusammenführen",project:"VPA-Projekt öffnen",source:"PDF oder Bild",recognize:"Gewählte Vorlage erkennen",txt:"Buchstabennotation — TXT",audio:"Klavierspiel — Audio",dismiss:"Schließen",pdf:"PDF-Seite",untitled:"Unbenannt",empty:"MusicXML, ein Projekt oder eine Vorlage zur Erkennung öffnen.",label:"IHR PROJEKT",live:"Anwendung",footer:"PROJEKTE · Buchstabennotation · lokales Klavier · Aufnahme und Export",pending:"Vorlage gewählt · Erkennung erforderlich",legacy:"Exakte Wiedergabe nicht verfügbar: MusicXML erneut importieren.",recording:"Zuerst Aufnahme oder Audioexport beenden.",recognizing:"Erkennung läuft. Auf das Ergebnis warten.",physical:"Physische Tastaturbelegung",error:"Vorgang fehlgeschlagen.",compare:"Partitur mit diesem Klang abspielen"}
  };
  const recognitionReview={ru:"проверьте распознавание",en:"review recognition",de:"Erkennung prüfen"};
  const practiceText={
    ru:{tools:"Тональность и упрощение",mode:"Упрощение для игры",normal:"Обычные аккорды",single:"Одна верхняя нота",upper:"Верхняя партия без баса",shift:"Тональность пианино",link:"Сохранять исходное звучание",hint:"Связано: сдвиг пианино противоположен сдвигу букв. Верхняя партия выбирается по высоте; проверьте мелодию."},
    en:{tools:"Key and simplification",mode:"Playing difficulty",normal:"Normal chords",single:"One highest note",upper:"Upper part, no bass",shift:"Piano transposition",link:"Keep original pitch",hint:"Linked: piano shift is opposite to letter shift. The upper part is selected by pitch; check the melody."},
    de:{tools:"Tonart und Vereinfachung",mode:"Spielschwierigkeit",normal:"Normale Akkorde",single:"Eine höchste Note",upper:"Oberstimme ohne Bass",shift:"Klaviertransposition",link:"Originaltonhöhe beibehalten",hint:"Verknüpft: Klavierversatz ist entgegengesetzt zum Buchstabenversatz. Oberstimme nach Tonhöhe gewählt; Melodie prüfen."}
  };
  Object.assign(practiceText.ru,{off:"Без упрощения — все ноты",normal:"Упрощать аккорды",restore:"Вернуть все ноты",less:"На полутон ниже",more:"На полутон выше"});
  Object.assign(practiceText.en,{off:"No simplification — all notes",normal:"Simplify chords",restore:"Restore all notes",less:"One semitone down",more:"One semitone up"});
  Object.assign(practiceText.de,{off:"Ohne Vereinfachung — alle Noten",normal:"Akkorde vereinfachen",restore:"Alle Noten wiederherstellen",less:"Einen Halbton tiefer",more:"Einen Halbton höher"});
  Object.assign(practiceText.ru,{keyboard:"Для ПК — без смешанного Shift",hint:"Режим ПК оставляет мелодию и ноты с таким же Shift, убирая конфликтующее сопровождение. Подбор тональности уменьшает такие конфликты; исходник не меняется."});
  Object.assign(practiceText.en,{keyboard:"PC keys — no mixed Shift",hint:"PC mode retains the melody and notes with the same Shift state, removing conflicting accompaniment. Key selection reduces conflicts; the source is unchanged."});
  Object.assign(practiceText.de,{keyboard:"PC-Tasten — ohne gemischte Umschalttaste",hint:"PC-Modus behält Melodie und Noten mit gleichem Umschaltzustand, entfernt widersprechende Begleitung. Tonartwahl reduziert Konflikte; die Quelle bleibt unverändert."});
  Object.assign(practiceText.ru,{balanced:"Умеренно — мелодия и редкий бас"});
  Object.assign(practiceText.en,{balanced:"Balanced — melody and occasional bass"});
  Object.assign(practiceText.de,{balanced:"Mittel — Melodie mit gelegentlichem Bass"});
  Object.assign(practiceText.ru,{musical:"Музыкальная адаптация — аккорды и регистр",hint:"Музыкальная адаптация: верхняя нота считается мелодией; сопровождение выбирается из исходного аккорда с учётом соседних. Выходящие за 61 клавишу голоса переносятся целиком по октавам, если помещаются. Новые соседние ноты не добавляются. TXT не содержит точного ритма — проверьте результат."});
  Object.assign(practiceText.en,{musical:"Musical adaptation — chords and register",hint:"Musical adaptation assumes the highest note is the melody; accompaniment is selected from original chord tones using neighbouring chords. Whole voices are octave-shifted into 61 keys when possible. No new neighbouring notes are invented. TXT has no exact rhythm — review the result."});
  Object.assign(practiceText.de,{musical:"Musikalische Anpassung — Akkorde und Register",hint:"Die höchste Note gilt als Melodie; Begleitung wird aus Originalakkordtönen mit Blick auf benachbarte Akkorde gewählt. Ganze Stimmen werden wenn möglich oktaviert. Keine neuen Nachbartöne. TXT enthält keinen genauen Rhythmus — Ergebnis prüfen."});
  const recognitionText={
    ru:{cancel:"Отменить распознавание",preparing:"Подготовка копии источника…",starting:"Запуск распознавателя…",processing:"Распознавание нот…",reading:"Чтение результата…",cancelling:"Остановка распознавателя…",cancelled:"Отменено. Можно повторить.",done:"Распознавание завершено",failed:"Не удалось распознать. Проверьте источник и повторите."},
    en:{cancel:"Cancel recognition",preparing:"Preparing a source copy…",starting:"Starting recognizer…",processing:"Recognising notes…",reading:"Reading result…",cancelling:"Stopping recognizer…",cancelled:"Cancelled. You can retry.",done:"Recognition finished",failed:"Recognition failed. Check the source and retry."},
    de:{cancel:"Erkennung abbrechen",preparing:"Vorlagenkopie vorbereiten…",starting:"Erkennungsmodul starten…",processing:"Noten erkennen…",reading:"Ergebnis lesen…",cancelling:"Erkennungsmodul stoppen…",cancelled:"Abgebrochen. Erneuter Versuch möglich.",done:"Erkennung abgeschlossen",failed:"Erkennung fehlgeschlagen. Vorlage prüfen und erneut versuchen."}
  };
  Object.assign(text.ru,{recognize:"Повторить",open:"Открыть файл…"});
  Object.assign(text.en,{recognize:"Retry",open:"Open file…"});
  Object.assign(text.de,{recognize:"Erneut versuchen",open:"Datei öffnen…"});
  recognitionText.ru.done="Ноты распознаны · проверьте их по источнику";
  recognitionText.en.done="Notes recognised · check against the source";
  recognitionText.de.done="Noten erkannt · mit der Vorlage vergleichen";
  Object.assign(text.ru,{source:"PDF или изображения",text:"Открыть буквенную запись TXT",queue:"Порядок изображений (по имени):",textOnly:"TXT · без длительностей"});
  Object.assign(text.en,{source:"PDF or images",text:"Open letter notation TXT",queue:"Image order (by filename):",textOnly:"TXT · no timing"});
  Object.assign(text.de,{source:"PDF oder Bilder",text:"Buchstabennotation TXT öffnen",queue:"Bildreihenfolge (nach Dateiname):",textOnly:"TXT · ohne Zeitdaten"});
  const progress=document.createElement("progress");progress.id="recognition-progress";progress.hidden=true;
  document.querySelector('#file-overlay [data-document-action="dismiss"]').before(progress);
  const cancel=document.createElement("button");cancel.dataset.documentAction="cancel";cancel.hidden=true;
  document.getElementById("file-open-actions").append(cancel);
  const queue=document.createElement("div");queue.id="recognition-queue";
  document.getElementById("file-error").after(queue);
  const $=id=>document.getElementById(id),t=key=>text[document.documentElement.lang||"ru"][key]||text[document.documentElement.lang||"ru"].error;
  let bridge,active=false,info={},open=false,kind="open",focus,lastRevision=-1,error="",pendingSound=false;
  const call=(method,...args)=>new Promise(resolve=>bridge[method](...args,raw=>resolve(JSON.parse(raw))));
  const busy=()=>info.busy||["starting","recording","finishing","exporting"].includes(window.vpaRecording?.state().phase);
  function accept(value){
    info=value;
    if(document.getElementById("piano-shift")){
      $("piano-shift").value=value.pianoShift||0;$("link-piano-shift").checked=value.linkPianoShift!==false;
      $("piano-shift").disabled=Boolean(info.busy)||$("link-piano-shift").checked;
      window.vpaPiano?.setPianoShift(value.pianoShift||0);
    }
    if(lastRevision!==value.revision){lastRevision=value.revision;$("physical-layout").value=value.physical;$("pdf-page").value=value.pdfPage;$("practice-mode").value=value.practiceMode||"normal";window.vpaPiano?.panic();window.vpaPreview.loadDocument(value);}
    updateMode();updateSteppers();
    render();
  }
  function render(){
    if(!active)return;
    updateSteppers();
    const p=practiceText[document.documentElement.lang||"ru"];
    const help=$("keyboard-help");
    if(help){
      const issues=(info.modifierConflicts||0)+(info.outside||0)+(info.registerMoves||0);
      help.hidden=!issues||Boolean(info.manual);
      const wording={ru:[`Конфликтов Shift: ${info.modifierConflicts||0} · вне диапазона: ${info.outside||0} · адаптированных букв: ${info.registerMoves||0}. При игре со слежением звучат исходные октавы. ↓/↑ — недоступная нота.`,`Подготовить для клавиатуры…`],en:[`Mixed Shift chords: ${info.modifierConflicts||0} · outside range: ${info.outside||0} · adapted keys: ${info.registerMoves||0}. Following uses original octaves. ↓/↑ marks unavailable notes.`,`Prepare for keyboard…`],de:[`Umschaltkonflikte: ${info.modifierConflicts||0} · außerhalb: ${info.outside||0} · angepasste Tasten: ${info.registerMoves||0}. Mit Notenverfolgung erklingen Originaloktaven. ↓/↑: nicht spielbare Note.`,`Für Tastatur vorbereiten…`]}[document.documentElement.lang||"ru"];
      help.querySelector('span').textContent=wording[0];help.querySelector('button').textContent=wording[1];
    }
    if($("piano-shift"))$("piano-shift").title=p.hint;
    if($("practice-mode"))$("practice-mode").title=p.hint;
    for(const el of document.querySelectorAll("[data-practice]"))if(el.textContent!==p[el.dataset.practice])el.textContent=p[el.dataset.practice];
    document.querySelector('[data-t="project"]').textContent=(info.name||t("untitled"))+(info.dirty?" *":"");
    document.querySelector('[data-t="exampleLabel"]').textContent=t("label");document.querySelector('[data-t="livePreview"]').textContent=t("live");
    document.querySelector('[data-t="demoOnly"]').textContent=t("footer");
    document.querySelector('[data-action="compare"]').textContent=t("compare");
    const units={ru:["тактов","нот"],en:["measures","notes"],de:["Takte","Noten"]}[document.documentElement.lang];
    const r=recognitionText[document.documentElement.lang||"ru"],stage=(info.busy&&info.recognitionTotal>1?`${info.recognitionPage||1} / ${info.recognitionTotal} · `:"")+(r[info.recognitionStage]||t("recognizing"));
    const footer=document.querySelector(".editor-foot span:last-child");footer.textContent=info.busy?stage:info.untimedText||(!info.selected&&info.manual)?t("textOnly"):(info.measures||0)+" "+units[0]+" · "+(info.selected||0)+" "+units[1];footer.title=[info.status,info.warnings].filter(Boolean).join("\n");
    if(!info.busy&&info.recognitionStage==="done"&&info.warnings)footer.textContent+=" · ⚠ "+recognitionReview[document.documentElement.lang||"ru"];
    if(info.approximatePlayback)footer.textContent+=" · ⚠ "+({ru:"Приблизительное MIDI-воспроизведение",en:"Approximate MIDI playback",de:"Ungefähre MIDI-Wiedergabe"}[document.documentElement.lang||"ru"]);
    $("notation").disabled=Boolean(info.busy);
    document.querySelector('[data-action="record"]').disabled=Boolean(info.busy)||!window.vpaPreview.state().ready||["starting","finishing","exporting"].includes(window.vpaRecording?.state().phase);
    if(!$("notation").value&&!window.vpaPreview.state().editing)$("reading").dataset.empty=t(info.busy?"recognizing":info.source?"pending":"empty");else $("reading").dataset.empty="";
    for(const el of document.querySelectorAll('[data-action="save"],[data-action="open"]'))el.disabled=Boolean(busy())&&!(info.busy&&el.dataset.action==="open");
    $("file-overlay").hidden=!open;$("file-title").textContent=t(kind);
    $("file-open-actions").hidden=kind!=="open";$("file-export-actions").hidden=kind!=="export";
    $("file-error").textContent=error?t(error):info.recognitionStage?stage:!info.playable&&info.selected?t("legacy"):"";
    $("file-error").title=info.recognitionError||"";
    queue.hidden=kind!=="open"||!info.busy||!(info.sources?.length>1);
    const queueKey=JSON.stringify([document.documentElement.lang,info.sources]);
    if(!queue.hidden&&queue.dataset.key!==queueKey){queue.dataset.key=queueKey;queue.replaceChildren();const heading=document.createElement("small");heading.textContent=t("queue");const list=document.createElement("ol");for(const name of info.sources){const item=document.createElement("li");item.textContent=name;list.append(item);}queue.append(heading,list);}
    progress.hidden=!info.busy;progress.setAttribute("aria-label",stage);
    cancel.hidden=!info.busy;
    $("pdf-page").max=info.pdfMax||1;
    $("pdf-page").disabled=Boolean(info.busy);
    for(const el of document.querySelectorAll("[data-document-action]")){
      const key=el.dataset.documentAction;
      if(key==="cancel"){el.textContent=r.cancel;el.disabled=!info.busy||info.recognitionStage==="cancelling";continue;}
      if(el.classList.contains("gold-key")){let label=el.querySelector(".gold-label");if(!label){label=document.createElement("span");label.className="gold-label";el.replaceChildren(label);}if(label.textContent!==t(key))label.textContent=t(key);}else if(el.textContent!==t(key))el.textContent=t(key);
      el.disabled=key!=="dismiss"&&Boolean(busy());
      if(key==="recognize"){el.hidden=!["failed","cancelled"].includes(info.recognitionStage);el.disabled=el.disabled||!info.source;}
    }
    if(pendingSound&&window.vpaPreview.state().ready){
      pendingSound=false;const value=info.view;
      window.vpaPiano.setReverb(value.reverbPreset,value.reverbAmount);window.vpaPiano.setSpeed(value.speed);
      if(value.layer!==8)$("layer").dispatchEvent(new Event("change"));
    }
  }
  function dialog(value){
    error="";kind=value;focus=document.activeElement;open=true;window.vpaPiano.releaseManual(true);render();window.vpaPreview.modality();
    $("file-overlay").querySelector("button:not(:disabled)")?.focus();
  }
  function dismiss(){open=false;render();window.vpaPreview.modality();focus?.focus();}
  async function action(value){
    if(!active)return;
    if(value==="dismiss"){dismiss();return;}
    if(value==="audio"){dismiss();window.vpaRecordingUI.exportDialog();return;}
    error="";window.vpaPiano.releaseManual(true);window.vpaRecording.stopListening();
    const result=await call("documentAction",value,$("notation").value,Number($("pdf-page").value)||1);
    if(result.error){if(!open)dialog("open");error=result.error;render();return;}
    if(value!=="close"){accept(result);if(!result.busy)dismiss();else if(!open)dialog("open");else render();}
  }
  function keyDown(event){
    if($("notation-settings")?.open){
      if(event.code==="Escape"){event.preventDefault();$("notation-settings").open=false;}
      if(event.code==="Tab"){
        const controls=[...$("notation-overlay").querySelectorAll("button:not(:disabled),input:not(:disabled),select:not(:disabled)")].filter(el=>el.getClientRects().length);
        if(event.shiftKey&&document.activeElement===controls[0]){event.preventDefault();controls.at(-1)?.focus();}
        else if(!event.shiftKey&&document.activeElement===controls.at(-1)){event.preventDefault();controls[0]?.focus();}
      }
      return true;
    }
    if(!open)return false;
    if(event.code==="Escape"){event.preventDefault();dismiss();}
    if(event.code==="Tab"){
      const controls=[...$("file-overlay").querySelectorAll("button:not(:disabled),input:not(:disabled)")].filter(el=>el.getClientRects().length);
      if(event.shiftKey&&document.activeElement===controls[0]){event.preventDefault();controls.at(-1)?.focus();}
      else if(!event.shiftKey&&document.activeElement===controls.at(-1)){event.preventDefault();controls[0]?.focus();}
    }
    return true;
  }
  document.addEventListener("click",event=>{
    const value=event.target.closest("[data-document-action]")?.dataset.documentAction;if(value)action(value);
  });
  const saveView=()=>{if(active){const s=window.vpaPreview.state();bridge.setView(JSON.stringify({fontSize:Number($("font-size").value),keyLabels:$("key-labels").value,piano:s.piano,follow:$("follow").checked,volume:Number($("volume").value),speed:Number($("tempo").value),layer:Number($("layer").value),reverbPreset:$("reverb-preset").value,reverbAmount:Number($("room").value),reducedMotion:$("reduced-motion").checked,linkLanguageLayout:$("link-language-layout").checked}),()=>{});}};
  document.addEventListener("vpa-keyboard-change",event=>{if(active){bridge.documentLanguage(event.detail.language,event.detail.physical);saveView();}});
  for(const id of["font-size","key-labels","follow","volume","tempo","layer","reverb-preset","room","reduced-motion","rhythm-hints"])$(id).addEventListener("change",()=>{saveView();if(active)bridge.setView(JSON.stringify({rhythmHints:$("rhythm-hints").checked}),()=>{});});
  document.addEventListener("click",event=>{if(event.target.closest('[data-action="piano"]'))saveView();});
  function updateMode(){
    const mode=$("practice-mode")?.value||"normal",enabled=['normal','keyboard','balanced','musical'].includes(mode);
    $("fullness").disabled=!enabled;
    const hint={ru:enabled?'Полнота внутри выбранного режима: меньше сопровождения → больше нот. Исходные высоты сохраняются.':mode==='off'?'Все ноты: упрощение выключено.':'В этом режиме остаётся одна нота на нажатие — сокращать аккорд уже нечего.',en:enabled?'Fullness within this mode: less accompaniment → more notes. Original pitches are retained.':mode==='off'?'All notes: simplification is off.':'This mode keeps one note per attack — there is no chord to thin.',de:enabled?'Umfang im gewählten Modus: weniger Begleitung → mehr Noten. Originaltonhöhen bleiben erhalten.':mode==='off'?'Alle Noten: Vereinfachung ist aus.':'Eine Note pro Anschlag — kein Akkord zum Reduzieren.'}[document.documentElement.lang||'ru'];
    if($('fullness-hint'))$('fullness-hint').textContent=hint;
    $('fullness').title=hint;
    if($('notation-rests'))$('notation-rests').checked=$('rhythm-hints').checked;
  }
  function updateSteppers(){for(const button of document.querySelectorAll("[data-step-for]")){const input=$(button.dataset.stepFor),next=Number(input.value)+Number(button.dataset.step);button.disabled=input.disabled||next<-12||next>12;button.setAttribute("aria-disabled",String(button.disabled));const p=practiceText[document.documentElement.lang||"ru"];button.setAttribute("aria-label",p[Number(button.dataset.step)<0?"less":"more"]);}}
  function stepper(input,eventName){
    const group=document.createElement("div");group.className="stepper";input.before(group);
    const clamp=()=>input.value=Math.max(-12,Math.min(12,Math.round(Number(input.value)||0)));
    // Sanitize before existing preview/native listeners read a pasted value.
    input.addEventListener("input",()=>{if(input.value!=="")clamp();},true);
    input.addEventListener("change",clamp,true);
    for(const delta of[-1,1]){const button=document.createElement("button");button.type="button";button.textContent=delta<0?"−":"+";button.dataset.stepFor=input.id;button.dataset.step=String(delta);button.addEventListener("click",()=>{clamp();input.value=Math.max(-12,Math.min(12,Number(input.value)+delta));input.dispatchEvent(new Event(eventName));updateSteppers();});group.append(button);}
    group.insertBefore(input,group.lastElementChild);
    input.addEventListener("change",()=>{if(eventName==="input")input.dispatchEvent(new Event("input"));updateSteppers();});
  }
  window.vpaDocument={get active(){return active;},info:()=>info,blocked:()=>open||Boolean($("notation-settings")?.open),refreshControls:()=>{updateMode();updateSteppers();},render,dialog,action,keyDown,
    syncText:()=>{if(active){const value=$("notation").value;bridge.setText(value,manual=>{if(value===$("notation").value)window.vpaPreview.syncManual(manual);});}},
    configure:async value=>{bridge=value;active=true;bridge.documentChanged.connect(raw=>accept(JSON.parse(raw)));
      const pane=document.querySelector('[data-pane="notes"]');pane.removeAttribute("data-pane");pane.classList.add("notation-controls");
      const details=document.createElement("details");details.id="notation-settings";const summary=document.createElement("summary");summary.dataset.practice="tools";details.append(summary);document.querySelector(".follow-bar").after(details);
      const help=document.createElement('div');help.id='keyboard-help';help.hidden=true;help.innerHTML='<span></span><button type="button"></button>';details.before(help);
      help.querySelector('button').addEventListener('click',async()=>{
        details.open=true;$("practice-mode").value='musical';$("fullness").value=100;updateMode();
        await window.vpaPreview.proposal(true);
      });
      const overlay=document.createElement("div");overlay.id="notation-overlay";overlay.className="modal-backdrop";overlay.hidden=true;overlay.append(pane);document.body.append(overlay);pane.setAttribute("role","dialog");pane.setAttribute("aria-modal","true");pane.setAttribute("aria-labelledby","notation-title");
      const heading=document.createElement("div");heading.className="notation-heading";heading.innerHTML='<h2 id="notation-title" data-practice="tools"></h2><button type="button" data-t="close"></button>';pane.prepend(heading);heading.querySelector("button").addEventListener("click",()=>details.open=false);
      pane.append($("conflict"));
      overlay.addEventListener("click",event=>{if(event.target===overlay)details.open=false;});
      details.addEventListener("toggle",()=>{overlay.hidden=!details.open;if(details.open){window.vpaPiano.releaseManual(true);heading.querySelector("button").focus();}window.vpaPreview.modality();window.dispatchEvent(new Event("resize"));if(!details.open)summary.focus();});
      document.querySelector('[data-tab="notes"]').remove();
      const mode=document.createElement("label");mode.innerHTML='<span data-practice="mode"></span><select id="practice-mode"><option value="off" data-practice="off"></option><option value="normal" data-practice="normal"></option><option value="balanced" data-practice="balanced"></option><option value="keyboard" data-practice="keyboard"></option><option value="single" data-practice="single"></option><option value="upper" data-practice="upper"></option></select>';pane.querySelector(".proposal").before(mode);
      const musical=document.createElement('option');musical.value='musical';musical.dataset.practice='musical';mode.querySelector('select').append(musical);
      const fullnessHint=document.createElement('small');fullnessHint.id='fullness-hint';$('fullness').closest('label').append(fullnessHint);
      const restControl=document.createElement('label');restControl.className='check notation-rest-toggle';restControl.innerHTML='<input id="notation-rests" type="checkbox"><span data-t="rhythmHints"></span>';pane.querySelector('.proposal').before(restControl);
      $('notation-rests').addEventListener('change',()=>{$('rhythm-hints').checked=$('notation-rests').checked;$('rhythm-hints').dispatchEvent(new Event('change'));});
      $('rhythm-hints').addEventListener('change',updateMode);
      $("practice-mode").addEventListener("change",()=>{if($("practice-mode").value==="off")$("fullness").value=100;updateMode();$("fullness").dispatchEvent(new Event("input"));});
      const restore=document.createElement("button");restore.type="button";restore.className="wide";restore.dataset.practice="restore";mode.after(restore);restore.addEventListener("click",()=>{$("practice-mode").value="off";$("practice-mode").dispatchEvent(new Event("change"));});
      const tuning=document.createElement("div");tuning.className="piano-tuning";tuning.innerHTML='<label><span data-practice="shift"></span><input id="piano-shift" type="number" min="-12" max="12" value="0"></label><label class="check"><input id="link-piano-shift" type="checkbox" checked><span data-practice="link"></span></label><small data-practice="hint"></small>';$("piano-body").before(tuning);
      for(const id of["piano-shift","link-piano-shift"])$(id).addEventListener("change",async()=>{const result=await call("pianoOptions",Number($("piano-shift").value),$("link-piano-shift").checked);if(!result.error)accept(result);});
      stepper($("transpose"),"input");stepper($("piano-shift"),"change");
      bridge.documentDirty.connect(dirty=>{info.dirty=dirty;render();});
      info=await call("document");$("physical-layout").value=info.physical;$("pdf-page").value=info.pdfPage;
      pendingSound=true;window.vpaPreview.restoreView(info.view);accept(info);}};
})();
