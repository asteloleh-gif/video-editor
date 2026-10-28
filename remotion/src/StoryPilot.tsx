import React from 'react';
import {Audio, Video} from '@remotion/media';
import {AbsoluteFill, CanvasImage, Composition, Sequence, interpolate, staticFile, useCurrentFrame, useVideoConfig, type CalculateMetadataFunction} from 'remotion';

type Asset = {id: string; local_src: string; author: string; license: string; year: number};
type Scene = {id: string; title: string; eyebrow: string; kind: string; start: number; end: number; trim_start?: number; media?: Asset};
type Caption = {start: number; end: number; text: string};
export type Story = {title: string; duration: number; narrationDuration: number; audioSrc: string; scenes: Scene[]; captions: Caption[]; assets: Asset[]};
type Props = {storySrc: string; story?: Story};
const ink = '#101210';
const cream = '#F7F2E8';
const amber = '#FFB83D';
const font = 'Arial, Helvetica, sans-serif';
const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

const BookArt = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  return <div style={{position:'absolute',inset:0,display:'flex',alignItems:'center',justifyContent:'center',gap:22}}>
    {[0,1,2,3,4].map((n) => <div key={n} style={{width:130,height:310+n%2*60,background:[amber,'#E7E0CF','#ACBDA8','#D8773B','#8FA8AF'][n],borderRadius:'7px 16px 16px 7px',boxShadow:'18px 25px 0 rgba(0,0,0,.24)',translate:`0 ${interpolate(frame,[n*4,n*4+fps],[120,0],clamp)}px`,rotate:`${(n-2)*-3}deg`}}><div style={{margin:'38px 18px',height:6,background:ink,opacity:.4}}/><div style={{margin:'14px 18px',height:6,background:ink,opacity:.25}}/></div>)}
    <div style={{position:'absolute',bottom:75,left:90,right:90,height:4,background:amber}}/>
    <div style={{position:'absolute',bottom:5,left:90,right:90,fontSize:42,color:cream}}>ВЫБОР НА ЭКРАНЕ / СВОБОДА ОТ ПОЛОК</div>
  </div>;
};

const CloudArt = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  return <div style={{position:'absolute',inset:0}}>
    <svg viewBox="0 0 1080 800" style={{width:'100%',height:'100%'}}>
      {[230,420,610,800].map((x,n)=><g key={x} opacity={interpolate(frame,[n*6,n*6+fps],[0,1],clamp)}>
        <path d={`M540 260 L${x} 470`} stroke={amber} strokeWidth="5" fill="none"/>
        <rect x={x-63} y="470" width="126" height="178" fill="#26352D" stroke="#839788" strokeWidth="3" rx="10"/>
        {[505,540,575].map(y=><path key={y} d={`M${x-40} ${y} H${x+40}`} stroke={cream} strokeWidth="6"/>)}
      </g>)}
      <rect x="345" y="75" width="390" height="205" rx="105" fill={amber}/>
      <text x="540" y="205" textAnchor="middle" fontSize="83" fontWeight="bold" fill={ink} fontFamily={font}>S3</text>
      <text x="540" y="745" textAnchor="middle" fontSize="43" fill={cream} fontFamily={font}>ДАННЫЕ / ХРАНЕНИЕ / ИНФРАСТРУКТУРА</text>
    </svg>
  </div>;
};

const SceneView = ({scene, story, number}: {scene: Scene; story: Story; number: number}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const time = scene.start + frame/fps;
  const caption = story.captions.find(c=>time>=c.start && time<c.end);
  const source = scene.media;
  const isVideo = scene.kind === 'video';
  return <AbsoluteFill style={{background:ink,color:cream,fontFamily:font,overflow:'hidden'}}>
    <div style={{position:'absolute',top:86,left:84,right:84,display:'flex',justifyContent:'space-between',fontSize:30,letterSpacing:3,color:'#B2B7AC'}}><span>ASTEL / ИСТОРИИ КОМПАНИЙ</span><span>{String(number).padStart(2,'0')} / 07</span></div>
    <div style={{position:'absolute',left:84,top:179,fontSize:33,letterSpacing:3,color:amber}}>{scene.eyebrow}</div>
    <div style={{position:'absolute',left:78,right:70,top:244,fontWeight:800,fontSize:scene.id==='origin'?113:104,lineHeight:1.03,letterSpacing:-4,whiteSpace:'pre-line',translate:`0 ${interpolate(frame,[0,.45*fps],[28,0],clamp)}px`,opacity:interpolate(frame,[0,.35*fps],[0,1],clamp)}}>{scene.title}</div>
    <div style={{position:'absolute',left:0,right:0,top:550,height:800,overflow:'hidden',background:'#17231B'}}>
      {source && !isVideo && <CanvasImage src={staticFile(source.local_src)} style={{height:'100%',width:'100%',objectFit:'cover',objectPosition:scene.kind==='founder'?'center 28%':'center',scale:interpolate(frame,[0,Math.max(1,(scene.end-scene.start)*fps)],[1.02,1.11],clamp)}}/>}
      {source && isVideo && <Video src={staticFile(source.local_src)} trimBefore={(scene.trim_start ?? 0)*fps} muted premountFor={fps} style={{height:'100%',width:'100%',objectFit:'cover'}}/>}
      {scene.kind==='books' && <BookArt/>}
      {scene.kind==='cloud' && <CloudArt/>}
      {source && <div style={{position:'absolute',bottom:0,left:0,right:0,padding:'60px 46px 28px',background:'linear-gradient(transparent,rgba(0,0,0,.85))',fontSize:29,color:'#fff'}}>{scene.kind==='founder'?'Джефф Безос / фото 2004 года':`Amazon / съёмка ${source.year} года`}<span style={{display:'block',fontSize:24,marginTop:8,color:'#D2D9D0'}}>{source.author} · {source.license} · Wikimedia Commons</span></div>}
    </div>
    {scene.id==='origin' && <div style={{position:'absolute',top:1403,left:84,right:84,fontSize:43,display:'flex',justifyContent:'space-between'}}><span><b style={{color:amber}}>1994</b> / основание</span><span><b style={{color:amber}}>1995</b> / старт продаж</span></div>}
    {scene.id!=='origin' && <div style={{position:'absolute',top:1408,left:84,width:912,height:4,background:'#344036'}}><div style={{height:4,background:amber,width:`${interpolate(frame,[0,Math.max(1,(scene.end-scene.start)*fps)],[0,100],clamp)}%`}}/></div>}
    <div style={{position:'absolute',left:76,right:76,top:1513,minHeight:150,display:'flex',alignItems:'center',justifyContent:'center',fontSize:49,fontWeight:600,lineHeight:1.22,textAlign:'center',color:cream}}>{caption?.text}</div>
    <div style={{position:'absolute',bottom:100,left:84,right:84,fontSize:27,letterSpacing:2,color:'#879184'}}>КНИГИ → ДОСТАВКА → ОБЛАЧНАЯ ИНФРАСТРУКТУРА</div>
  </AbsoluteFill>;
};

const Credits = () => <AbsoluteFill style={{background:amber,color:ink,fontFamily:font,padding:'160px 84px'}}>
  <div style={{fontSize:34,letterSpacing:4}}>ASTEL / ТЕСТ ФОРМАТА</div>
  <div style={{fontSize:108,fontWeight:800,lineHeight:1.04,letterSpacing:-4,marginTop:90}}>ИСТОРИИ<br/>КОМПАНИЙ</div>
  <div style={{fontSize:46,marginTop:100}}>Amazon: от книг к инфраструктуре</div>
  <div style={{fontSize:32,lineHeight:1.55,marginTop:120}}>Видео BHX4: domdomegg · CC BY 4.0<br/>Фото Безоса: JD Lasica · CC BY 2.0<br/>Фото MSP1: Tony Webster · CC BY 2.0<br/>Материалы: Wikimedia Commons<br/>Лицензии: creativecommons.org/licenses/by/4.0/<br/>и creativecommons.org/licenses/by/2.0/</div>
  <div style={{fontSize:31,lineHeight:1.5,marginTop:90}}>Кадры обрезаны и оформлены графикой.<br/>Факты: Amazon Investor Relations и AWS.<br/>Полные ссылки — в файле SOURCES.md.</div>
</AbsoluteFill>;

export const StoryPilot = ({story}: Props) => {
  const {fps} = useVideoConfig();
  if(!story) return <AbsoluteFill style={{background:ink,color:cream,fontFamily:font,justifyContent:'center',padding:90,fontSize:80}}>Здесь появится тестовый ролик</AbsoluteFill>;
  const s=story.scenes;
  const start=(i:number)=>Math.round(s[i].start*fps);
  const length=(i:number)=>Math.round(s[i].end*fps)-start(i);
  return <AbsoluteFill>
    <Audio src={staticFile(story.audioSrc)} volume={1} premountFor={fps}/>
    <Sequence name="01 / Завязка" from={start(0)} durationInFrames={length(0)} premountFor={fps}><SceneView scene={s[0]} story={story} number={1}/></Sequence>
    <Sequence name="02 / Основание" from={start(1)} durationInFrames={length(1)} premountFor={fps}><SceneView scene={s[1]} story={story} number={2}/></Sequence>
    <Sequence name="03 / Книги" from={start(2)} durationInFrames={length(2)} premountFor={fps}><SceneView scene={s[2]} story={story} number={3}/></Sequence>
    <Sequence name="04 / Доставка" from={start(3)} durationInFrames={length(3)} premountFor={fps}><SceneView scene={s[3]} story={story} number={4}/></Sequence>
    <Sequence name="05 / Облако" from={start(4)} durationInFrames={length(4)} premountFor={fps}><SceneView scene={s[4]} story={story} number={5}/></Sequence>
    <Sequence name="06 / Система" from={start(5)} durationInFrames={length(5)} premountFor={fps}><SceneView scene={s[5]} story={story} number={6}/></Sequence>
    <Sequence name="07 / Вывод" from={start(6)} durationInFrames={length(6)} premountFor={fps}><SceneView scene={s[6]} story={story} number={7}/></Sequence>
    <Sequence name="Источники" from={Math.round(story.narrationDuration*fps)} durationInFrames={3*fps} premountFor={fps}><Credits/></Sequence>
  </AbsoluteFill>;
};

const metadata: CalculateMetadataFunction<Props> = async ({props, abortSignal}) => {
  if(props.story) return {durationInFrames:Math.ceil(props.story.duration*30),props};
  const response=await fetch(staticFile(props.storySrc),{signal:abortSignal});
  if(!response.ok) return {durationInFrames:1800,props};
  const loaded=await response.json() as {story:Story};
  return {durationInFrames:Math.ceil(loaded.story.duration*30),props:{...props,...loaded}};
};

export const StoryPilotRegistration = () => <Composition id="AstelStoryPilot" component={StoryPilot} width={1080} height={1920} fps={30} durationInFrames={1800} defaultProps={{storySrc:'jobs/amazon-pilot-20261028/props.json'}} calculateMetadata={metadata}/>;
