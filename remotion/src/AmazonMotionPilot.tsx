import React from 'react';
import type {Caption} from '@remotion/captions';
import {Audio, Video} from '@remotion/media';
import {AbsoluteFill, CanvasImage, Composition, Folder, Interactive, Sequence, interpolate, staticFile, useCurrentFrame, useVideoConfig, type CalculateMetadataFunction} from 'remotion';
import type {Story} from './StoryPilot';
import {VolumeMotion} from './motion-study/VolumeMotion';
import {palette as c} from './motion-study/timing';

type Props = {storySrc: string; story?: Story};
type Asset = Story['assets'][number];
type Phase = 'journey' | 'book' | 'parcel' | 'network';
type MotionProps = {phase: Phase; width: number; height: number; journeySeconds?: number};
const font = 'Arial, Helvetica, sans-serif';
const clamp = {extrapolateLeft:'clamp',extrapolateRight:'clamp'} as const;

// The approved A/B renderer remains the model source. Only its pose clock is
// remapped here to spoken beats; floating/data movement keeps real local time.
export const NarrativeMotion = ({phase,width,height,journeySeconds=6}:MotionProps) => {
  const frame=useCurrentFrame();
  const {fps}=useVideoConfig();
  const seconds=frame/fps;
  const pose=phase==='book'?Math.min(seconds,2.8):phase==='parcel'?3.2+Math.min(seconds,2):phase==='network'?7.2+seconds:seconds*12/journeySeconds;
  return <VolumeMotion width={width} height={height} timelineSeconds={pose}/>;
};

const SourceNote = ({asset,label}:{asset:Asset;label:string}) => <div style={{position:'absolute',left:80,right:80,bottom:77,fontSize:24,lineHeight:1.35,color:'#CAD5CD',textShadow:'0 2px 8px #000'}}>
  {label} · {asset.author} · {asset.license}<br/>Wikimedia Commons
</div>;

const VideoBackdrop = ({asset,trimSeconds=0}:{asset:Asset;trimSeconds?:number}) => {
  const {fps}=useVideoConfig();
  return <AbsoluteFill>
    <Video src={staticFile(asset.local_src)} trimBefore={trimSeconds*fps} muted premountFor={fps} objectFit="cover" style={{width:'100%',height:'100%'}}/>
    <AbsoluteFill style={{background:'linear-gradient(180deg,rgba(4,18,14,.82) 0%,rgba(4,18,14,.08) 45%,rgba(4,18,14,.95) 100%)'}}/>
  </AbsoluteFill>;
};

const PhotoBackdrop = ({asset,founder=false}:{asset:Asset;founder?:boolean}) => {
  const frame=useCurrentFrame();
  const {fps}=useVideoConfig();
  return <AbsoluteFill>
    <CanvasImage src={staticFile(asset.local_src)} style={{width:'100%',height:'100%',objectFit:'cover',objectPosition:founder?'center 26%':'center',scale:interpolate(frame,[0,9*fps],[1.01,1.10],clamp)}}/>
    <AbsoluteFill style={{background:founder?'linear-gradient(180deg,rgba(5,20,15,.55),transparent 40%,rgba(5,20,15,.97) 82%)':'linear-gradient(180deg,rgba(5,20,15,.88),rgba(5,20,15,.78))'}}/>
  </AbsoluteFill>;
};

const Chapter = ({kicker,title}:{kicker:string;title:string}) => {
  const frame=useCurrentFrame();
  const {fps}=useVideoConfig();
  return <div style={{position:'absolute',left:80,right:80,top:150}}>
    <div style={{fontSize:30,letterSpacing:3,color:c.mint,marginBottom:34}}>{kicker}</div>
    <Interactive.Div name="Заголовок сцены" style={{fontSize:103,fontWeight:800,lineHeight:1.02,letterSpacing:-4,whiteSpace:'pre-line',opacity:interpolate(frame,[0,.3*fps],[0,1],clamp),translate:`0 ${interpolate(frame,[0,.4*fps],[22,0],clamp)}px`}}>{title}</Interactive.Div>
  </div>;
};

const Hook = ({asset}:{asset:Asset}) => <AbsoluteFill>
  <VideoBackdrop asset={asset} trimSeconds={12}/>
  <AbsoluteFill style={{background:'rgba(8,28,21,.55)'}}/>
  <Chapter kicker="AMAZON / НЕОЖИДАННЫЙ ПОВОРОТ" title={'От книг —\nк облаку.'}/>
  <div style={{position:'absolute',left:0,top:570}}><NarrativeMotion phase="journey" width={1080} height={950} journeySeconds={6}/></div>
  <SourceNote asset={asset} label="Amazon BHX4 · видео 2019 года · 3D-иллюстрация"/>
</AbsoluteFill>;

const Origin = ({asset}:{asset:Asset}) => {
  const frame=useCurrentFrame();
  const {fps}=useVideoConfig();
  const online=frame>=5.09*fps;
  return <AbsoluteFill>
    <PhotoBackdrop asset={asset} founder/>
    <div style={{position:'absolute',left:80,top:150,fontSize:31,letterSpacing:3,color:c.paper}}>ДЖЕФФ БЕЗОС / ОСНОВАТЕЛЬ</div>
    <div style={{position:'absolute',left:75,top:1110,fontSize:180,lineHeight:1,fontWeight:800,letterSpacing:-9,color:c.amber}}>{online?'1995':'1994'}</div>
    <div style={{position:'absolute',left:82,top:1324,right:80,fontSize:68,fontWeight:700,lineHeight:1.1}}>{online?'Интернет-магазин книг':'Основание компании'}</div>
    <SourceNote asset={asset} label="Портрет · фото 2004 года"/>
  </AbsoluteFill>;
};

const Books = () => {
  const frame=useCurrentFrame();
  const {fps}=useVideoConfig();
  return <AbsoluteFill style={{background:c.ink}}>
    <Chapter kicker="ПОЧЕМУ КНИГИ?" title={'Каталог без\nграниц полки.'}/>
    <div style={{position:'absolute',top:560,left:0}}><NarrativeMotion phase="book" width={1080} height={860}/></div>
    <div style={{position:'absolute',left:105,right:105,top:1390,display:'flex',justifyContent:'space-between',fontSize:36,color:c.mint}}>
      <span>КНИГА</span><span>→</span><span style={{opacity:interpolate(frame,[1.4*fps,2.2*fps],[.15,1],clamp)}}>КАТАЛОГ</span><span>→</span><span style={{opacity:interpolate(frame,[3*fps,3.8*fps],[.15,1],clamp)}}>САЙТ</span>
    </div>
    <div style={{position:'absolute',left:80,bottom:93,fontSize:24,color:c.muted}}>3D-ИЛЛЮСТРАЦИЯ / ASTEL</div>
  </AbsoluteFill>;
};

const Delivery = ({asset,second=false}:{asset:Asset;second?:boolean}) => <AbsoluteFill>
  <VideoBackdrop asset={asset} trimSeconds={second?0:2}/>
  <Chapter kicker="ЛОГИСТИКА / AMAZON" title={second?'Склад → упаковка\n→ доставка':'За кнопкой\n«купить»'}/>
  <SourceNote asset={asset} label="Amazon BHX4 · видео 2019 года"/>
</AbsoluteFill>;

const ParcelOverlay = () => <div style={{position:'absolute',left:570,top:1000,width:430,height:480,borderRadius:30,overflow:'hidden',background:'rgba(16,36,33,.92)',border:'1px solid rgba(162,228,187,.35)'}}>
  <NarrativeMotion phase="parcel" width={430} height={410}/>
  <div style={{position:'absolute',left:28,right:28,bottom:28,fontSize:25,letterSpacing:2,color:c.mint,textAlign:'center'}}>ЗАКАЗ → ПОСЫЛКА</div>
</div>;

const Cloud = () => {
  const frame=useCurrentFrame();
  const {fps}=useVideoConfig();
  const time=frame/fps;
  return <AbsoluteFill style={{background:c.ink}}>
    <Chapter kicker={time<3?'СЛЕДУЮЩИЙ ПОВОРОТ':'2006 / AMAZON S3'} title={time<6.64?'От коробки —\nк данным.':'Хранение данных\nчерез интернет.'}/>
    <div style={{position:'absolute',left:0,top:570}}><NarrativeMotion phase="network" width={1080} height={900}/></div>
    <div style={{position:'absolute',left:80,top:1410,right:80,display:'flex',justifyContent:'space-between',color:c.mint,fontSize:37}}>
      <span style={{opacity:interpolate(frame,[3*fps,3.5*fps],[0,1],clamp)}}>S3</span>
      <span style={{opacity:interpolate(frame,[6.64*fps,7.1*fps],[0,1],clamp)}}>ДАННЫЕ</span>
      <span style={{opacity:interpolate(frame,[9*fps,9.5*fps],[0,1],clamp)}}>РАЗРАБОТЧИКИ</span>
    </div>
    <div style={{position:'absolute',left:80,bottom:93,fontSize:24,color:c.muted}}>УПРОЩЁННАЯ 3D-ИЛЛЮСТРАЦИЯ / ASTEL</div>
  </AbsoluteFill>;
};

const Lesson = ({asset}:{asset:Asset}) => <AbsoluteFill>
  <VideoBackdrop asset={asset} trimSeconds={10}/>
  <Chapter kicker="ЧТО ОБЪЕДИНЯЕТ ЭТУ ИСТОРИЮ" title={'От товара\nк системе.'}/>
  <div style={{position:'absolute',left:570,top:1000,width:430,height:480,background:'rgba(16,36,33,.94)',borderRadius:30,overflow:'hidden',border:'1px solid rgba(162,228,187,.35)'}}>
    <NarrativeMotion phase="network" width={430} height={410}/>
    <div style={{position:'absolute',bottom:26,left:25,right:25,textAlign:'center',fontSize:25,color:c.mint}}>ПРОДУКТ → СИСТЕМА</div>
  </div>
  <SourceNote asset={asset} label="Amazon BHX4 · видео 2019 года · 3D-иллюстрация"/>
</AbsoluteFill>;

const Closing = ({asset,duration}:{asset:Asset;duration:number}) => <AbsoluteFill>
  <PhotoBackdrop asset={asset}/>
  <Chapter kicker="ИСТОРИИ КОМПАНИЙ / ASTEL" title={'Смотри шире\nпервого продукта.'}/>
  <div style={{position:'absolute',left:0,top:570}}><NarrativeMotion phase="journey" width={1080} height={900} journeySeconds={duration}/></div>
  <SourceNote asset={asset} label="Amazon MSP1 · фото 2019 года · 3D-иллюстрация"/>
</AbsoluteFill>;

const CaptionTrack = ({captions}:{captions:Caption[]}) => {
  const frame=useCurrentFrame();
  const {fps}=useVideoConfig();
  const cue=captions.find(item=>frame/fps*1000>=item.startMs && frame/fps*1000<item.endMs);
  return <div style={{position:'absolute',left:65,right:65,top:1580,minHeight:150,padding:'20px 23px',boxSizing:'border-box',borderRadius:18,color:c.paper,background:cue?'rgba(6,22,16,.91)':'transparent',fontFamily:font,fontSize:48,fontWeight:600,lineHeight:1.2,textAlign:'center',display:'flex',alignItems:'center',justifyContent:'center'}}><span style={{display:'block',width:'100%',textWrap:'balance'}}>{cue?.text}</span></div>;
};

const Sources = () => <AbsoluteFill style={{background:c.amber,color:c.ink,fontFamily:font,padding:'160px 84px'}}>
  <div style={{fontSize:34,letterSpacing:4}}>ASTEL / AMAZON / ВЕРСИЯ 2</div>
  <div style={{fontSize:108,fontWeight:800,lineHeight:1.04,letterSpacing:-4,marginTop:90}}>ОТ КНИГ —<br/>К ОБЛАКУ</div>
  <div style={{fontSize:34,lineHeight:1.5,marginTop:120}}>Видео BHX4: domdomegg · CC BY 4.0<br/>Фото Безоса: JD Lasica · CC BY 2.0<br/>Фото MSP1: Tony Webster · CC BY 2.0<br/>Материалы: Wikimedia Commons<br/>Кадры обрезаны и оформлены графикой.<br/>3D-иллюстрации: Astel / Three.js.</div>
  <div style={{fontSize:31,lineHeight:1.5,marginTop:75}}>Факты: Amazon Investor Relations и AWS.<br/>Полные ссылки и лицензии — SOURCES.md.<br/>creativecommons.org/licenses/by/4.0/<br/>creativecommons.org/licenses/by/2.0/</div>
</AbsoluteFill>;

export const AmazonMotionPilot = ({story}:Props) => {
  const {fps}=useVideoConfig();
  if(!story) return <AbsoluteFill style={{background:c.ink,color:c.paper,fontFamily:font,padding:90,fontSize:64}}>Для монтажа нужен локальный пакет первого пилота.</AbsoluteFill>;
  const asset=(id:string)=>{
    const item=story.assets.find(a=>a.id===id);
    if(!item) throw new Error(`Missing reviewed pilot asset: ${id}`);
    return item;
  };
  const captions:Caption[]=story.captions.map(cue=>({text:cue.text,startMs:cue.start*1000,endMs:cue.end*1000,timestampMs:null,confidence:null}));
  const narrationFrames=Math.ceil(story.narrationDuration*fps);
  return <AbsoluteFill style={{background:c.ink,color:c.paper,fontFamily:font}}>
    <Sequence name="Рассказ / исходный голос и субтитры" from={0} durationInFrames={narrationFrames} premountFor={fps}>
      <Audio name="Олег / исходная озвучка" src={staticFile(story.audioSrc)} volume={1} premountFor={fps}/>
      <Sequence name="01 / 3D-завязка поверх склада" from={0} durationInFrames={6*fps} premountFor={fps}><Hook asset={asset('warehouse-1')}/></Sequence>
      <Sequence name="02 / Безос и даты" from={6*fps} durationInFrames={9*fps} premountFor={fps}><Origin asset={asset('bezos')}/></Sequence>
      <Sequence name="03 / 3D-книга и каталог" from={15*fps} durationInFrames={7*fps} premountFor={fps}><Books/></Sequence>
      <Sequence name="04 / Склад — первый план" from={22*fps} durationInFrames={5*fps} premountFor={fps}><Delivery asset={asset('warehouse-1')}/></Sequence>
      <Sequence name="05 / Склад — второй план" from={27*fps} durationInFrames={5*fps} premountFor={fps}><Delivery asset={asset('warehouse-2')} second/></Sequence>
      <Sequence name="Посылка / 3D поверх реального видео" from={26*fps} durationInFrames={6*fps} premountFor={fps}><ParcelOverlay/></Sequence>
      <Sequence name="06 / 3D-инфраструктура и S3" from={32*fps} durationInFrames={13*fps} premountFor={fps}><Cloud/></Sequence>
      <Sequence name="07 / Видеоряд и 3D-система" from={45*fps} durationInFrames={6*fps} premountFor={fps}><Lesson asset={asset('warehouse-2')}/></Sequence>
      <Sequence name="08 / Итоговая 3D-трансформация" from={51*fps} durationInFrames={narrationFrames-51*fps} premountFor={fps}><Closing asset={asset('warehouse-photo')} duration={story.narrationDuration-51}/></Sequence>
      <CaptionTrack captions={captions}/>
    </Sequence>
    <Sequence name="Источники и авторы" from={narrationFrames} durationInFrames={3*fps} premountFor={fps}><Sources/></Sequence>
  </AbsoluteFill>;
};

const metadata:CalculateMetadataFunction<Props> = async ({props,abortSignal}) => {
  const loaded=props.story?{story:props.story}:await fetch(staticFile(props.storySrc),{signal:abortSignal}).then(response=>{
    if(!response.ok) throw new Error('The reviewed local pilot props are required');
    return response.json() as Promise<{story:Story}>;
  });
  return {durationInFrames:Math.ceil(loaded.story.narrationDuration*30)+90,props:{...props,...loaded}};
};

export const AmazonMotionPilotRegistration = () => <Folder name="Amazon-V2">
  <Composition id="AstelStoryPilot-3D" component={AmazonMotionPilot} width={1080} height={1920} fps={30} durationInFrames={1868} defaultProps={{storySrc:'jobs/amazon-pilot-20261028/props.json'}} calculateMetadata={metadata}/>
  <Composition id="Amazon3DLayer" component={NarrativeMotion} width={1080} height={900} fps={30} durationInFrames={360} defaultProps={{phase:'journey',width:1080,height:900,journeySeconds:12}}/>
</Folder>;
