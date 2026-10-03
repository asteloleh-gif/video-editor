import {useEffect, useMemo, useRef, useState} from 'react';

type Clip={id:string;sourceStart:number;sourceEnd:number;label:string};
type Overlay={id:string;start:number;end:number;x:number;y:number;width:number;height:number;text:string;fontSize:number;color:string;background:string};
type Project={version:1;name:string;sourceName:string;sourceDuration:number;clips:Clip[];overlays:Overlay[];updatedAt:string};
type Selection={kind:'clip'|'overlay';id:string}|null;

const uid=()=>Math.random().toString(36).slice(2,10);
const clamp=(n:number,a:number,b:number)=>Math.min(b,Math.max(a,n));
const r2=(n:number)=>Math.round(n*100)/100;
const dur=(c:Clip)=>Math.max(.01,c.sourceEnd-c.sourceStart);

const emptyProject=():Project=>({
  version:1,name:'AstelFam Untitled',sourceName:'',sourceDuration:0,clips:[],overlays:[],updatedAt:new Date().toISOString()
});

function aiDraft(sourceDuration:number,sourceName:string):Project{
  const spec:[string,number,number][]=[
    ['Cold open',59.3,62.7],['Round 1',7.5,11.5],['Round 2',14,17.5],
    ['Close call',29.5,33],['Reaction',35,38.2],['His turn',46,50],['Final payoff',57.5,62.4],
  ];
  const clips=spec
    .map(([label,a,b])=>({id:uid(),label,sourceStart:clamp(a,0,sourceDuration),sourceEnd:clamp(b,0,sourceDuration)}))
    .filter(c=>c.sourceEnd-c.sourceStart>.15);
  const output=clips.reduce((s,c)=>s+dur(c),0);
  const overlays:Overlay[]=[
    {id:uid(),start:.05,end:1.7,x:8,y:13,width:84,height:11,text:"DON'T DROP IT 😳",fontSize:58,color:'#fff',background:'rgba(0,0,0,.72)'},
    {id:uid(),start:3.35,end:4.3,x:27,y:14,width:46,height:9,text:'EARLIER…',fontSize:44,color:'#111',background:'#FFD84D'},
    {id:uid(),start:7.3,end:8.45,x:25,y:13,width:50,height:9,text:'ROUND 2',fontSize:46,color:'#fff',background:'rgba(17,19,24,.80)'},
    {id:uid(),start:13.9,end:15.2,x:13,y:72,width:74,height:10,text:'TOO CLOSE 💀',fontSize:52,color:'#fff',background:'rgba(255,89,107,.88)'},
    {id:uid(),start:16,end:17.2,x:70,y:18,width:16,height:13,text:'😂',fontSize:78,color:'#fff',background:'transparent'},
    {id:uid(),start:18,end:19.2,x:27,y:13,width:46,height:9,text:'HIS TURN',fontSize:44,color:'#111',background:'#80F3D2'},
    {id:uid(),start:22.1,end:23.45,x:18,y:13,width:64,height:9,text:'FINAL ROUND',fontSize:46,color:'#fff',background:'rgba(17,19,24,.80)'},
    {id:uid(),start:Math.max(0,output-2.1),end:Math.max(.2,output-.3),x:17,y:71,width:66,height:11,text:'NOOO 💀',fontSize:62,color:'#fff',background:'rgba(255,89,107,.88)'},
  ].map(o=>({...o,start:clamp(o.start,0,output),end:clamp(o.end,.1,output)}));
  return {version:1,name:'AstelFam AI Draft 01',sourceName,sourceDuration,clips,overlays,updatedAt:new Date().toISOString()};
}

export default function App(){
  const [project,setProject]=useState<Project>(()=>{
    try{return JSON.parse(localStorage.getItem('astelfam-editor-project')||'null')||emptyProject()}catch{return emptyProject()}
  });
  const [videoUrl,setVideoUrl]=useState('');
  const [playhead,setPlayhead]=useState(0);
  const [playing,setPlaying]=useState(false);
  const [selection,setSelection]=useState<Selection>(null);
  const [dragClip,setDragClip]=useState<string|null>(null);
  const videoRef=useRef<HTMLVideoElement|null>(null);
  const previewRef=useRef<HTMLDivElement|null>(null);
  const timelineRef=useRef<HTMLDivElement|null>(null);
  const lastFrame=useRef<number|null>(null);
  const raf=useRef<number|null>(null);

  const outputDuration=useMemo(()=>project.clips.reduce((s,c)=>s+dur(c),0),[project.clips]);
  const selectedOverlay=selection?.kind==='overlay'?project.overlays.find(o=>o.id===selection.id)||null:null;
  const selectedClip=selection?.kind==='clip'?project.clips.find(c=>c.id===selection.id)||null:null;

  const locate=(t:number)=>{
    let cursor=0;
    for(let i=0;i<project.clips.length;i++){
      const clip=project.clips[i],d=dur(clip);
      if(t<=cursor+d||i===project.clips.length-1){
        const local=clamp(t-cursor,0,d);
        return {clip,index:i,outputStart:cursor,sourceTime:clip.sourceStart+local};
      }
      cursor+=d;
    }
    return null;
  };

  useEffect(()=>{
    localStorage.setItem('astelfam-editor-project',JSON.stringify({...project,updatedAt:new Date().toISOString()}));
  },[project]);

  useEffect(()=>{
    const v=videoRef.current,l=locate(playhead);
    if(v&&l&&Math.abs(v.currentTime-l.sourceTime)>.08)v.currentTime=l.sourceTime;
  },[playhead,project.clips]);

  useEffect(()=>{
    if(!playing){
      videoRef.current?.pause();
      if(raf.current)cancelAnimationFrame(raf.current);
      lastFrame.current=null;
      return;
    }
    videoRef.current?.play().catch(()=>undefined);
    const tick=(now:number)=>{
      if(lastFrame.current===null)lastFrame.current=now;
      const dt=(now-lastFrame.current)/1000; lastFrame.current=now;
      setPlayhead(prev=>{
        const next=prev+dt;
        if(next>=outputDuration){setPlaying(false);return outputDuration}
        const l=locate(next),v=videoRef.current;
        if(l&&v&&Math.abs(v.currentTime-l.sourceTime)>.18)v.currentTime=l.sourceTime;
        return next;
      });
      raf.current=requestAnimationFrame(tick);
    };
    raf.current=requestAnimationFrame(tick);
    return()=>{if(raf.current)cancelAnimationFrame(raf.current);lastFrame.current=null};
  },[playing,outputDuration,project.clips]);

  const patchOverlay=(id:string,p:Partial<Overlay>)=>setProject(x=>({...x,overlays:x.overlays.map(o=>o.id===id?{...o,...p}:o)}));
  const patchClip=(id:string,p:Partial<Clip>)=>setProject(x=>({...x,clips:x.clips.map(c=>c.id===id?{...c,...p}:c)}));

  const loadVideo=(file:File)=>{
    if(videoUrl)URL.revokeObjectURL(videoUrl);
    setVideoUrl(URL.createObjectURL(file));setPlaying(false);setPlayhead(0);
    setProject(p=>({...p,sourceName:file.name}));
  };

  const loadedMetadata=()=>{
    const v=videoRef.current;if(!v)return;
    setProject(p=>p.clips.length?{...p,sourceDuration:v.duration}:{...p,sourceDuration:v.duration,clips:[{id:uid(),label:'Full clip',sourceStart:0,sourceEnd:v.duration}]});
  };

  const split=()=>{
    const l=locate(playhead);if(!l)return;
    const local=playhead-l.outputStart,d=dur(l.clip);if(local<.12||d-local<.12)return;
    const s=l.clip.sourceStart+local;
    const a={...l.clip,id:uid(),sourceEnd:s,label:l.clip.label+' A'};
    const b={...l.clip,id:uid(),sourceStart:s,label:l.clip.label+' B'};
    setProject(p=>{const next=[...p.clips];next.splice(l.index,1,a,b);return{...p,clips:next}});
    setSelection({kind:'clip',id:b.id});
  };

  const addText=()=>{
    const id=uid();
    const o:Overlay={id,start:clamp(playhead,0,Math.max(0,outputDuration-.1)),end:clamp(playhead+2,.1,outputDuration||2),x:15,y:72,width:70,height:11,text:'TYPE HERE',fontSize:54,color:'#fff',background:'rgba(0,0,0,.72)'};
    setProject(p=>({...p,overlays:[...p.overlays,o]}));setSelection({kind:'overlay',id});
  };

  const removeSelected=()=>{
    if(!selection)return;
    setProject(p=>selection.kind==='clip'?{...p,clips:p.clips.filter(c=>c.id!==selection.id)}:{...p,overlays:p.overlays.filter(o=>o.id!==selection.id)});
    setSelection(null);
  };

  const saveJson=()=>{
    const data={...project,updatedAt:new Date().toISOString()};
    const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));
    const a=document.createElement('a');a.href=url;a.download=(project.name||'astelfam-project').replace(/\s+/g,'_')+'.json';a.click();URL.revokeObjectURL(url);
  };

  const loadJson=async(file:File)=>{setProject(JSON.parse(await file.text()));setPlayhead(0);setSelection(null)};

  const dragOverlay=(e:React.PointerEvent,o:Overlay,resize=false)=>{
    e.stopPropagation();e.preventDefault();setSelection({kind:'overlay',id:o.id});
    const box=previewRef.current?.getBoundingClientRect();if(!box)return;
    const sx=e.clientX,sy=e.clientY,start={...o};
    const move=(ev:PointerEvent)=>{
      const dx=(ev.clientX-sx)/box.width*100,dy=(ev.clientY-sy)/box.height*100;
      resize?patchOverlay(o.id,{width:r2(clamp(start.width+dx,8,100-start.x)),height:r2(clamp(start.height+dy,5,100-start.y))})
        :patchOverlay(o.id,{x:r2(clamp(start.x+dx,0,100-start.width)),y:r2(clamp(start.y+dy,0,100-start.height))});
    };
    const up=()=>{window.removeEventListener('pointermove',move);window.removeEventListener('pointerup',up)};
    window.addEventListener('pointermove',move);window.addEventListener('pointerup',up);
  };

  const trimClip=(e:React.PointerEvent,c:Clip,left:boolean)=>{
    e.stopPropagation();e.preventDefault();
    const rect=timelineRef.current?.getBoundingClientRect();if(!rect)return;
    const sx=e.clientX,start={...c},secPerPx=outputDuration/Math.max(1,rect.width);
    const move=(ev:PointerEvent)=>{
      const d=(ev.clientX-sx)*secPerPx;
      left?patchClip(c.id,{sourceStart:r2(clamp(start.sourceStart+d,0,start.sourceEnd-.2))})
        :patchClip(c.id,{sourceEnd:r2(clamp(start.sourceEnd+d,start.sourceStart+.2,project.sourceDuration||9999))});
    };
    const up=()=>{window.removeEventListener('pointermove',move);window.removeEventListener('pointerup',up)};
    window.addEventListener('pointermove',move);window.addEventListener('pointerup',up);
  };

  const moveOverlayTime=(e:React.PointerEvent,o:Overlay,edge:'move'|'left'|'right')=>{
    e.stopPropagation();e.preventDefault();setSelection({kind:'overlay',id:o.id});
    const rect=timelineRef.current?.getBoundingClientRect();if(!rect)return;
    const sx=e.clientX,start={...o},secPerPx=outputDuration/Math.max(1,rect.width);
    const move=(ev:PointerEvent)=>{
      const d=(ev.clientX-sx)*secPerPx;
      if(edge==='left')patchOverlay(o.id,{start:r2(clamp(start.start+d,0,start.end-.1))});
      else if(edge==='right')patchOverlay(o.id,{end:r2(clamp(start.end+d,start.start+.1,outputDuration))});
      else{const length=start.end-start.start,s=clamp(start.start+d,0,Math.max(0,outputDuration-length));patchOverlay(o.id,{start:r2(s),end:r2(s+length)})}
    };
    const up=()=>{window.removeEventListener('pointermove',move);window.removeEventListener('pointerup',up)};
    window.addEventListener('pointermove',move);window.addEventListener('pointerup',up);
  };

  const reorder=(target:string)=>{
    if(!dragClip||dragClip===target)return;
    setProject(p=>{const n=[...p.clips],from=n.findIndex(c=>c.id===dragClip),to=n.findIndex(c=>c.id===target);if(from<0||to<0)return p;const[item]=n.splice(from,1);n.splice(to,0,item);return{...p,clips:n}});
  };

  const active=project.overlays.filter(o=>playhead>=o.start&&playhead<o.end);
  let cursor=0;
  const layouts=project.clips.map(clip=>{const start=cursor,d=dur(clip);cursor+=d;return{clip,start,d}});
  const pct=(n:number)=>outputDuration?(n/outputDuration*100)+'%':'0%';

  return <main className="app">
    <header>
      <div><small>ASTEL ENGINE</small><h1>AstelFam Editor <span>v0.1</span></h1></div>
      <nav>
        <label className="btn primary">Load video<input hidden type="file" accept="video/*,.mov" onChange={e=>e.target.files?.[0]&&loadVideo(e.target.files[0])}/></label>
        <button className="btn" onClick={()=>project.sourceDuration&&setProject(aiDraft(project.sourceDuration,project.sourceName))}>Load AI draft</button>
        <label className="btn">Load JSON<input hidden type="file" accept=".json" onChange={e=>e.target.files?.[0]&&loadJson(e.target.files[0])}/></label>
        <button className="btn" onClick={saveJson}>Save JSON</button>
      </nav>
    </header>

    <section className="work">
      <div className="stage-card">
        <div className="stage-wrap">
          <div ref={previewRef} className="stage" onPointerDown={()=>setSelection(null)}>
            {videoUrl?<video ref={videoRef} src={videoUrl} playsInline onLoadedMetadata={loadedMetadata}/>:<div className="empty"><b>Load your video</b><span>It stays local in your browser.</span></div>}
            {active.map(o=><div key={o.id} className={'overlay '+(selectedOverlay?.id===o.id?'sel':'')} style={{left:o.x+'%',top:o.y+'%',width:o.width+'%',height:o.height+'%',fontSize:o.fontSize,color:o.color,background:o.background}} onPointerDown={e=>dragOverlay(e,o)}>
              {o.text}<i onPointerDown={e=>dragOverlay(e,o,true)}/>
            </div>)}
          </div>
        </div>
        <div className="transport">
          <button className="play" onClick={()=>setPlaying(v=>!v)} disabled={!videoUrl||!outputDuration}>{playing?'❚❚':'▶'}</button>
          <button className="btn sm" onClick={()=>setPlayhead(clamp(playhead-.5,0,outputDuration))}>−0.5s</button>
          <button className="btn sm" onClick={()=>setPlayhead(clamp(playhead+.5,0,outputDuration))}>+0.5s</button>
          <code>{playhead.toFixed(2)} / {outputDuration.toFixed(2)}s</code>
          <input type="range" min={0} max={Math.max(.01,outputDuration)} step=".01" value={clamp(playhead,0,Math.max(.01,outputDuration))} onChange={e=>{setPlaying(false);setPlayhead(Number(e.target.value))}}/>
        </div>
      </div>

      <aside>
        <h3>Inspector</h3>
        {!selection&&<p className="muted">Click a clip or text layer. Drag text directly on the video.</p>}
        {selectedOverlay&&<div className="form">
          <label>Text<textarea value={selectedOverlay.text} onChange={e=>patchOverlay(selectedOverlay.id,{text:e.target.value})}/></label>
          <div className="cols"><label>Start<input type="number" step=".05" value={selectedOverlay.start} onChange={e=>patchOverlay(selectedOverlay.id,{start:Number(e.target.value)})}/></label><label>End<input type="number" step=".05" value={selectedOverlay.end} onChange={e=>patchOverlay(selectedOverlay.id,{end:Number(e.target.value)})}/></label></div>
          <label>Font size<input type="range" min="18" max="100" value={selectedOverlay.fontSize} onChange={e=>patchOverlay(selectedOverlay.id,{fontSize:Number(e.target.value)})}/></label>
          <label>Background<select value={selectedOverlay.background} onChange={e=>patchOverlay(selectedOverlay.id,{background:e.target.value})}><option value="rgba(0,0,0,.72)">Dark</option><option value="rgba(255,89,107,.88)">Red</option><option value="#FFD84D">Yellow</option><option value="#80F3D2">Mint</option><option value="transparent">None</option></select></label>
          <button className="btn danger" onClick={removeSelected}>Delete text</button>
        </div>}
        {selectedClip&&<div className="form">
          <label>Label<input value={selectedClip.label} onChange={e=>patchClip(selectedClip.id,{label:e.target.value})}/></label>
          <div className="cols"><label>Source in<input type="number" step=".05" value={selectedClip.sourceStart} onChange={e=>patchClip(selectedClip.id,{sourceStart:Number(e.target.value)})}/></label><label>Source out<input type="number" step=".05" value={selectedClip.sourceEnd} onChange={e=>patchClip(selectedClip.id,{sourceEnd:Number(e.target.value)})}/></label></div>
          <div className="stat">Duration <b>{dur(selectedClip).toFixed(2)}s</b></div>
          <button className="btn danger" onClick={removeSelected}>Delete clip</button>
        </div>}
        <hr/><h3>Project</h3>
        <label>Name<input value={project.name} onChange={e=>setProject(p=>({...p,name:e.target.value}))}/></label>
        <div className="stat">Source <b>{project.sourceDuration.toFixed(2)}s</b></div>
        <div className="stat">Output <b>{outputDuration.toFixed(2)}s</b></div>
        <div className="stat">Clips <b>{project.clips.length}</b></div>
        <div className="stat">Text layers <b>{project.overlays.length}</b></div>
      </aside>
    </section>

    <section className="timeline-card">
      <div className="tools"><div><button className="btn primary sm" onClick={split}>✂ Split</button><button className="btn sm" onClick={addText}>+ Text</button><button className="btn sm" onClick={()=>project.sourceDuration&&setProject(p=>({...p,clips:[{id:uid(),label:'Full clip',sourceStart:0,sourceEnd:p.sourceDuration}],overlays:[]}))}>Reset</button></div><span>Drag clips to reorder • drag edges to trim • drag text blocks to retime</span></div>
      <div className="timeline" ref={timelineRef}>
        <div className="head" style={{left:pct(playhead)}}/>
        <div className="row"><b>VIDEO</b><div className="track" onPointerDown={e=>{const box=e.currentTarget.getBoundingClientRect();setPlaying(false);setPlayhead(clamp((e.clientX-box.left)/box.width*outputDuration,0,outputDuration))}}>
          {layouts.map(({clip,start,d})=><div key={clip.id} draggable onDragStart={()=>setDragClip(clip.id)} onDragOver={e=>e.preventDefault()} onDrop={()=>reorder(clip.id)} className={'clip '+(selectedClip?.id===clip.id?'sel':'')} style={{left:pct(start),width:pct(d)}} onClick={e=>{e.stopPropagation();setSelection({kind:'clip',id:clip.id})}}>
            <i className="edge left" onPointerDown={e=>trimClip(e,clip,true)}/><strong>{clip.label}</strong><small>{clip.sourceStart.toFixed(1)}–{clip.sourceEnd.toFixed(1)}</small><i className="edge right" onPointerDown={e=>trimClip(e,clip,false)}/>
          </div>)}
        </div></div>
        <div className="row"><b>TEXT</b><div className="track">
          {project.overlays.map(o=><div key={o.id} className={'textblock '+(selectedOverlay?.id===o.id?'sel':'')} style={{left:pct(o.start),width:pct(o.end-o.start)}} onPointerDown={e=>moveOverlayTime(e,o,'move')}>
            <i className="edge left" onPointerDown={e=>moveOverlayTime(e,o,'left')}/><span>{o.text}</span><i className="edge right" onPointerDown={e=>moveOverlayTime(e,o,'right')}/>
          </div>)}
        </div></div>
      </div>
    </section>

    <footer><b>Learning loop:</b> AI draft → you correct it here → Save JSON → send me the JSON → I compare your corrections with my original edit.</footer>
  </main>;
}