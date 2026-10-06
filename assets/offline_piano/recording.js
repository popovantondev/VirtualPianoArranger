"use strict";
// A silent tap on VPA's final mix: never opens the microphone or system audio.
(() => {
  const processor = `class VpaCapture extends AudioWorkletProcessor {
    constructor(){super();this.active=false;this.pcm=new Int16Array(8192);this.used=0;
      this.port.onmessage=e=>{if(e.data==="start")this.active=true;
        if(e.data==="stop"){this.active=false;this.flush();this.port.postMessage({end:true});}};}
    flush(){if(this.used){const pcm=this.pcm.slice(0,this.used);this.port.postMessage({pcm:pcm.buffer},[pcm.buffer]);this.used=0;}}
    process(inputs,outputs){if(this.active){const channels=inputs[0],left=channels[0],right=channels[1]||left;
      const frames=left?left.length:outputs[0][0].length;
      for(let i=0;i<frames;i++){for(const data of [left,right]){const sample=Math.max(-1,Math.min(1,data?data[i]:0));this.pcm[this.used++]=Math.round(sample*(sample<0?32768:32767));}
        if(this.used===this.pcm.length)this.flush();}}
      return true;}
  } registerProcessor("vpa-capture",VpaCapture);`;
  let bridge, node, output, session, queue=[], sending=false, sequence=0, loadedContext,generation=0,closing=false;
  let phase="idle", finishResolve, endSeen=false, seconds=0, current={phase:"idle",frames:0,formats:[]};
  const playback=new Audio();
  const publish=()=>window.vpaRecordingHost?.onState({...current,phase,seconds,listening:!playback.paused});
  const call=(name,...args)=>new Promise(resolve=>bridge[name](...args,raw=>resolve(JSON.parse(raw))));
  const encode=buffer=>{let s="";const bytes=new Uint8Array(buffer);for(let i=0;i<bytes.length;i+=8192)s+=String.fromCharCode(...bytes.subarray(i,i+8192));return btoa(s);};
  function disconnect(){if(node){output.disconnect(node);node.disconnect();node.port.onmessage=null;node=null;}}
  async function drain(){
    if(sending)return;sending=true;const guard=generation;
    while(queue.length){const chunk=queue.shift(),result=await call("appendPcm",session,sequence++,encode(chunk));
      if(guard!==generation)break;
      if(result.error){queue=[];await fail(result.error);break;}}
    sending=false;
    if(endSeen&&session&&guard===generation){const id=session;session=null;disconnect();const result=await call("finish",id,"");
      current=result;phase=result.phase;seconds=result.seconds;publish();finishResolve?.();finishResolve=null;}
  }
  async function fail(code){
    generation++;
    disconnect();queue=[];endSeen=false;
    if(session){const id=session;session=null;current=await call("finish",id,code);}
    else current={...current,error:code};
    phase=current.frames?"ready":"error";publish();finishResolve?.();finishResolve=null;
  }
  async function start(replace=false){
    if(!bridge||["starting","recording","finishing","exporting"].includes(phase))return;
    phase="starting";publish();playback.pause();
    try{
      const audio=window.vpaPiano.audioOutput();if(!audio?.context.audioWorklet)throw Error("worklet");
      await audio.context.resume();
      if(loadedContext!==audio.context){const url=URL.createObjectURL(new Blob([processor],{type:"text/javascript"}));
        try{await audio.context.audioWorklet.addModule(url);loadedContext=audio.context;}finally{URL.revokeObjectURL(url);}}
      const result=await call("begin",audio.context.sampleRate,replace);
      if(result.error){phase=current.frames?"ready":"idle";publish();window.vpaRecordingHost?.onError(result.error);return;}
      session=result.session;sequence=0;queue=[];endSeen=false;seconds=0;const guard=++generation;
      node=new AudioWorkletNode(audio.context,"vpa-capture",{channelCount:2,channelCountMode:"explicit",outputChannelCount:[2]});
      output=audio.output;node.onprocessorerror=()=>{if(guard===generation)fail("worklet");};
      node.port.onmessage=e=>{if(guard!==generation)return;if(e.data.pcm){seconds+=e.data.pcm.byteLength/4/audio.context.sampleRate;queue.push(e.data.pcm);
          if(queue.length>32){fail("overflow");return;}drain();publish();}
        if(e.data.end){endSeen=true;drain();}};
      output.connect(node);node.connect(audio.context.destination);node.port.postMessage("start");phase="recording";publish();
    }catch(error){console.error("VPA capture:",error.name,error.message);await fail(error.message==="worklet"?"worklet":"capture");}
  }
  async function stop(){
    if(phase!=="recording")return;
    phase="finishing";publish();window.vpaPiano.panic();
    // Keep the actual reverb tail, but do not retain held piano voices.
    const tail=window.vpaPiano.audioOutput()?.tail||0;
    await new Promise(resolve=>setTimeout(resolve,Math.ceil((tail+.2)*1000)));
    if(!node)return;
    const id=session;
    await new Promise(resolve=>{const timeout=setTimeout(()=>{if(session===id&&finishResolve)fail("interrupted");},5000);
      finishResolve=()=>{clearTimeout(timeout);resolve();};node.port.postMessage("stop");});
  }
  async function listen(){
    if(phase!=="ready"||!current.url)return;
    if(!playback.paused){playback.pause();publish();return;}
    window.vpaPiano.panic();playback.src=current.url;playback.currentTime=0;
    try{await playback.play();publish();}catch{window.vpaRecordingHost?.onError("playback");}
  }
  playback.onended=playback.onpause=publish;
  window.addEventListener("blur",()=>{playback.pause();publish();});
  document.addEventListener("visibilitychange",()=>{if(document.hidden)playback.pause();});
  window.vpaRecording={configure:async value=>{if(!value)return;bridge=value;bridge.changed.connect(raw=>{current=JSON.parse(raw);
      if(!["starting","finishing"].includes(phase))phase=current.phase;publish();});current=await call("info");phase=current.phase;publish();},
    start,stop,listen,stopListening:()=>{playback.pause();publish();},
    export:async format=>{playback.pause();const result=await call("exportAudio",format);if(result.error)window.vpaRecordingHost?.onError(result.error);},
    setLanguage:language=>bridge?.setLanguage(language),
    state:()=>({...current,phase,seconds,listening:!playback.paused}),
    requestClose:async()=>{if(closing)return;closing=true;playback.pause();
      while(["starting","finishing"].includes(phase))await new Promise(resolve=>setTimeout(resolve,50));
      if(phase==="recording")await stop();window.vpaRecordingHost?.close();closing=false;}};
})();
