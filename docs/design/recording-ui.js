"use strict";
(() => {
  const text={
    ru:{record:"Запись",finish:"Закончить",recording:"Идёт запись",finishing:"Сохраняем звук и хвост эффекта…",ready:"Текущая запись",listen:"Прослушать запись",listening:"Остановить прослушивание",export:"Экспорт",exportTitle:"Экспорт текущей записи",exportHint:"Стерео, только звук VPA. Без микрофона. Существующий файл не перезаписывается.",audioFormat:"Формат",chooseFile:"Выбрать файл и сохранить",close:"Закрыть",exporting:"Кодирование и проверка…",saved:"Экспорт проверен:",empty:"Сначала запишите игру на пианино.",newRecording:"Новая запись",replaceRecording:"Запись ещё не экспортирована. Заменить её? Библиотека дублей не создаётся.",replace:"Заменить",cancel:"Отменить",error:"Операция не завершена. Уже записанные данные сохранены, если удалось получить звук.",encoder:"Для этого формата нужен FFmpeg.",exists:"Файл существует. Выберите другое имя — перезапись отключена.",worklet:"Не удалось подключить аудиозапись в этом движке.",overflow:"Сохранение не успевало за звуком. Доступна записанная часть.",limit:"Лимит 30 минут. Доступна записанная часть.",interrupted:"Запись прервана. Доступна записанная часть.",demo:"ПРЕДПРОСМОТР · запись и аудиоэкспорт · проекты пока не подключены",future:"Открытие ваших файлов и сохранение проектов пока не подключены. Запись и аудиоэкспорт уже доступны."},
    en:{record:"Record",finish:"Finish",recording:"Recording",finishing:"Saving audio and effect tail…",ready:"Current recording",listen:"Listen to recording",listening:"Stop listening",export:"Export",exportTitle:"Export current recording",exportHint:"Stereo, VPA audio only. No microphone. Existing files are never overwritten.",audioFormat:"Format",chooseFile:"Choose file and save",close:"Close",exporting:"Encoding and verifying…",saved:"Verified export:",empty:"Record your piano playing first.",newRecording:"New recording",replaceRecording:"The recording has not been exported. Replace it? No take library is created.",replace:"Replace",cancel:"Cancel",error:"Operation failed. Already captured audio remains available if frames were saved.",encoder:"This format needs FFmpeg.",exists:"File exists. Choose another name; overwriting is disabled.",worklet:"Could not connect audio capture in this engine.",overflow:"Storage could not keep up. The saved portion is available.",limit:"30 minute limit reached. The saved portion is available.",interrupted:"Capture interrupted. The saved portion is available.",demo:"PREVIEW · recording and audio export · projects not connected",future:"Opening your files and saving projects are not connected yet. Recording and audio export are available."},
    de:{record:"Aufnahme",finish:"Beenden",recording:"Aufnahme läuft",finishing:"Audio und Nachhall werden gespeichert…",ready:"Aktuelle Aufnahme",listen:"Aufnahme anhören",listening:"Wiedergabe stoppen",export:"Exportieren",exportTitle:"Aktuelle Aufnahme exportieren",exportHint:"Stereo, nur VPA-Klang. Kein Mikrofon. Vorhandene Dateien werden nicht überschrieben.",audioFormat:"Format",chooseFile:"Datei wählen und speichern",close:"Schließen",exporting:"Kodieren und prüfen…",saved:"Geprüfter Export:",empty:"Zuerst Ihr Klavierspiel aufnehmen.",newRecording:"Neue Aufnahme",replaceRecording:"Die Aufnahme wurde nicht exportiert. Ersetzen? Keine Aufnahmebibliothek.",replace:"Ersetzen",cancel:"Abbrechen",error:"Vorgang fehlgeschlagen. Bereits gespeicherte Audiodaten bleiben verfügbar.",encoder:"Dieses Format benötigt FFmpeg.",exists:"Datei existiert. Anderen Namen wählen; Überschreiben deaktiviert.",worklet:"Audioaufnahme konnte nicht verbunden werden.",overflow:"Speichern zu langsam. Der gespeicherte Teil ist verfügbar.",limit:"30-Minuten-Limit erreicht. Der gespeicherte Teil ist verfügbar.",interrupted:"Aufnahme unterbrochen. Der gespeicherte Teil ist verfügbar.",demo:"ENTWURF · Aufnahme und Audioexport · Projekte noch nicht verbunden",future:"Eigene Dateien und Projektspeicherung folgen später. Aufnahme und Audioexport sind verfügbar."}
  };
  const $=id=>document.getElementById(id),t=key=>text[document.documentElement.lang||"ru"][key]||text[document.documentElement.lang||"ru"].error;
  let recording={phase:"idle",frames:0,seconds:0,formats:[]},exportOpen=false,replaceOpen=false,focus,error="";
  const blocked=()=>exportOpen||replaceOpen;
  function render(){
    const active=["starting","recording","finishing"].includes(recording.phase),busy=active||recording.phase==="exporting";
    const button=document.querySelector(".record"),seconds=Math.floor(recording.seconds||0),time=String(Math.floor(seconds/60)).padStart(2,"0")+":"+String(seconds%60).padStart(2,"0");
    button.disabled=!window.vpaPreview.state().ready||["starting","finishing","exporting"].includes(recording.phase);
    button.classList.toggle("is-recording",active);button.setAttribute("aria-pressed",String(active));button.querySelector("[data-t=record]").textContent=t(active?"finish":"record");
    $("recording-bar").hidden=recording.phase==="idle";
    $("recording-summary").textContent=recording.error?t(recording.error):t(recording.phase==="recording"?"recording":recording.phase==="finishing"?"finishing":recording.phase==="exporting"?"exporting":"ready")+" · "+time;
    $("record-listen").disabled=busy||!recording.frames;$("record-listen").textContent=t(recording.listening?"listening":"listen");
    $("recording-bar").querySelector("[data-action=export]").disabled=busy||!recording.frames;
    $("export-overlay").hidden=!exportOpen;$("record-replace-overlay").hidden=!replaceOpen;
    for(const root of [$("export-overlay"),$("record-replace-overlay")])root.querySelectorAll("[data-t]").forEach(el=>{
      if(el.classList.contains("gold-key")){const label=document.createElement("span");label.className="gold-label";label.textContent=t(el.dataset.t);el.replaceChildren(label);}
      else el.textContent=t(el.dataset.t);});
    const select=$("audio-format"),ids=recording.formats.map(f=>f.id).join();
    if(select.dataset.formats!==ids){select.replaceChildren();for(const f of recording.formats){const option=document.createElement("option");option.value=f.id;option.textContent=f.label;option.disabled=!f.available;select.append(option);}select.dataset.formats=ids;}
    document.querySelector("[data-action=export-file]").disabled=busy||!recording.frames;
    $("export-status").textContent=error||recording.error?t(error||recording.error):recording.phase==="exporting"?t("exporting"):recording.exportPath?t("saved")+" "+recording.exportPath:"";
    document.querySelector("[data-t=demoOnly]").textContent=t("demo");
    if(document.querySelector("#notice-title").textContent===({ru:"Пока не подключено",en:"Not connected yet",de:"Noch nicht verbunden"})[document.documentElement.lang])$("notice-text").textContent=t("future");
    window.vpaRecording?.setLanguage(document.documentElement.lang);
    window.vpaDocument?.render();
  }
  function dialog(open){
    if(open){error="";if(recording.phase!=="ready"||!recording.frames){error="empty";}window.vpaPiano.releaseManual(true);focus=document.activeElement;}
    exportOpen=open;render();window.vpaPreview.modality();if(open)$("audio-format").focus();else focus?.focus();
  }
  window.vpaRecordingHost={onState:value=>{recording=value;render();if(window.vpaPreview.state().piano)window.vpaPreview.setHeight(window.vpaPreview.state().keyHeight);},
    onError:code=>{if(code==="replace"){focus=document.activeElement;replaceOpen=true;render();window.vpaPreview.modality();document.querySelector("[data-action=record-keep]").focus();}
      else {error=code;render();}},close:()=>window.vpaPreview.close()};
  async function record(){error="";if(recording.phase==="recording")await window.vpaRecording.stop();else await window.vpaRecording.start();}
  document.addEventListener("click",async event=>{
    const action=event.target.closest("[data-action]")?.dataset.action;
    if(action==="record-listen")await window.vpaRecording.listen();
    if(action==="export-close")dialog(false);
    if(action==="export-file"){error="";await window.vpaRecording.export($("audio-format").value);}
    if(action==="record-replace"||action==="record-keep"){replaceOpen=false;render();window.vpaPreview.modality();focus?.focus();if(action==="record-replace")await window.vpaRecording.start(true);}
    if(action==="open"||action==="save")render();
  });
  $("stop").addEventListener("click",()=>{window.vpaRecording.stopListening();if(recording.phase==="recording")window.vpaRecording.stop();});
  function keyDown(event){
    if(!blocked())return false;
    if(event.code==="Escape"){event.preventDefault();if(replaceOpen){replaceOpen=false;render();window.vpaPreview.modality();focus?.focus();}else dialog(false);}
    if(event.code==="Tab"){const root=replaceOpen?$("record-replace-overlay"):$("export-overlay"),controls=[...root.querySelectorAll("button:not(:disabled),select")];
      if(event.shiftKey&&document.activeElement===controls[0]){event.preventDefault();controls.at(-1).focus();}
      else if(!event.shiftKey&&document.activeElement===controls.at(-1)){event.preventDefault();controls[0].focus();}}
    return true;
  }
  window.vpaRecordingUI={render,record,exportDialog:()=>dialog(true),blocked,keyDown};render();
})();
