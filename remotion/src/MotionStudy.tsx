import React, {type CSSProperties} from 'react';
import {AbsoluteFill, Composition, Folder, Interactive, Sequence, interpolate, useCurrentFrame, useVideoConfig, type InteractivitySchema} from 'remotion';
import {FlatMotion} from './motion-study/FlatMotion';
import {VolumeMotion} from './motion-study/VolumeMotion';
import {motionState, palette as c} from './motion-study/timing';

type PanelProps = {variant:'2d'|'3d'; width:number; height:number; style?:CSSProperties};
const PanelInner = ({variant,width,height,style}:PanelProps) => <div style={{position:'absolute',width,height,overflow:'hidden',...style}}>
  {variant==='2d'?<FlatMotion width={width} height={height}/>:<VolumeMotion width={width} height={height}/>}
</div>;
const panelSchema = {
  variant:{type:'enum',default:'2d',description:'Стиль движения',variants:{'2d':{},'3d':{}}},
  width:{type:'number',default:900,description:'Ширина сцены',hiddenFromList:false},
  height:{type:'number',default:720,description:'Высота сцены',hiddenFromList:false},
} as const satisfies InteractivitySchema;
// This checkout uses 4.0.529: explicit Sequence nodes supply timing; the
// later wrapInSequence API is deliberately not assumed or backported.
export const MotionPanel = Interactive.withSchema<typeof panelSchema,PanelProps>({Component:PanelInner,componentName:'<MotionPanel>',schema:panelSchema,supportsEffects:false});

const BeatCaption = ({compact=false}:{compact?:boolean}) => {
  const frame=useCurrentFrame();
  const {fps}=useVideoConfig();
  const m=motionState(frame,fps);
  return <div style={{color:c.paper,fontFamily:'Arial, Helvetica, sans-serif'}}>
    <div style={{display:'flex',alignItems:'baseline',gap:22,fontSize:compact?56:80,fontWeight:800,letterSpacing:-2}}>
      <span style={{color:c.amber,fontSize:compact?30:38,fontWeight:400,letterSpacing:0}}>0{m.beat+1}</span>
      <span>{['Книги','Доставка','Инфраструктура'][m.beat]}</span>
    </div>
    <div style={{marginTop:compact?12:22,fontSize:compact?30:43,color:c.muted,lineHeight:1.2}}>
      {['Начало с одного продукта.','Система вокруг каждой покупки.','Возможности для других компаний.'][m.beat]}
    </div>
  </div>;
};

const Progress = () => {
  const frame=useCurrentFrame();
  const {fps}=useVideoConfig();
  return <div style={{height:3,background:c.line,width:'100%'}}><div style={{height:3,background:c.mint,width:`${interpolate(frame,[0,12*fps-1],[0,100],{extrapolateLeft:'clamp',extrapolateRight:'clamp'})}%`}}/></div>;
};

export const MotionComparison = () => {
  const {fps}=useVideoConfig();
  return <AbsoluteFill style={{background:c.ink,color:c.paper,fontFamily:'Arial, Helvetica, sans-serif',overflow:'hidden'}}>
    <div style={{position:'absolute',left:80,top:46,color:c.muted,fontSize:23,letterSpacing:4}}>ASTEL / AMAZON / МОУШН-ПРОБА</div>
    <Interactive.Div name="Общий заголовок" style={{position:'absolute',left:76,top:100,fontSize:76,fontWeight:800,letterSpacing:-3}}>От книг к инфраструктуре.</Interactive.Div>
    <div style={{position:'absolute',left:80,top:224,fontSize:25,color:c.mint}}>A / 2D — ГРАФИКА</div>
    <div style={{position:'absolute',left:1010,top:224,fontSize:25,color:c.mint}}>B / 3D — ОБЪЁМ И СВЕТ</div>
    <div style={{position:'absolute',left:960,top:220,bottom:170,width:1,background:c.line}}/>
    <Sequence name="A / Плоская графика" from={0} durationInFrames={12*fps} premountFor={fps}>
      <MotionPanel variant="2d" width={880} height={630} style={{left:40,top:253}}/>
    </Sequence>
    <Sequence name="B / Объёмная сцена" from={0} durationInFrames={12*fps} premountFor={fps}>
      <MotionPanel variant="3d" width={880} height={630} style={{left:1000,top:253}}/>
    </Sequence>
    <div style={{position:'absolute',left:80,top:873}}><BeatCaption compact/></div>
    <div style={{position:'absolute',right:80,bottom:70,color:c.muted,fontSize:23}}>ОДИН СЮЖЕТ · ОДИН ТАЙМИНГ · 12 СЕКУНД</div>
    <div style={{position:'absolute',left:80,right:80,bottom:38}}><Progress/></div>
  </AbsoluteFill>;
};

type PortraitProps = {variant:'2d'|'3d'};
export const MotionPortrait = ({variant}:PortraitProps) => {
  const {fps}=useVideoConfig();
  return <AbsoluteFill style={{background:c.ink,color:c.paper,fontFamily:'Arial, Helvetica, sans-serif',overflow:'hidden'}}>
    <div style={{position:'absolute',left:84,top:112,fontSize:29,letterSpacing:4,color:c.muted}}>ASTEL / AMAZON</div>
    <Interactive.Div name="Заголовок" style={{position:'absolute',left:78,right:78,top:230,fontSize:130,fontWeight:800,letterSpacing:-6,lineHeight:1.02}}>От книг —<br/>к облаку.</Interactive.Div>
    <div style={{position:'absolute',left:84,top:528,fontSize:30,letterSpacing:3,color:c.mint}}>{variant==='2d'?'A / ГРАФИКА':'B / ОБЪЁМ И СВЕТ'}</div>
    <Sequence name="Трансформация" from={0} durationInFrames={12*fps} premountFor={fps}>
      <MotionPanel variant={variant} width={1080} height={850} style={{left:0,top:610}}/>
    </Sequence>
    <div style={{position:'absolute',left:84,right:84,top:1520}}><BeatCaption/></div>
    <div style={{position:'absolute',left:84,right:84,bottom:115}}><Progress/></div>
    <div style={{position:'absolute',left:84,bottom:65,fontSize:23,color:c.muted,letterSpacing:2}}>МОУШН-ПРОБА / ИЛЛЮСТРАЦИЯ</div>
  </AbsoluteFill>;
};

export const MotionStudyRegistration = () => <Folder name="Motion-Lab">
  <Composition id="AmazonMotion-Compare" component={MotionComparison} width={1920} height={1080} fps={30} durationInFrames={360}/>
  <Composition id="AmazonMotion-2D" component={MotionPortrait} width={1080} height={1920} fps={30} durationInFrames={360} defaultProps={{variant:'2d'}}/>
  <Composition id="AmazonMotion-3D" component={MotionPortrait} width={1080} height={1920} fps={30} durationInFrames={360} defaultProps={{variant:'3d'}}/>
  <Composition id="AmazonMotion-Panel" component={MotionPanel} width={880} height={630} fps={30} durationInFrames={360} defaultProps={{variant:'2d',width:880,height:630}}/>
</Folder>;
