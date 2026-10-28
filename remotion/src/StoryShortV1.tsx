import React from 'react';
import {AbsoluteFill, CanvasImage, Composition, Loop, Sequence, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {Audio, Video} from '@remotion/media';

export type WorkspaceStory = {
  id: string; title: string; durationInFrames: number; audioSrc: string;
  scenes: {id: string; title: string; from: number; durationInFrames: number; src: string; kind: string; sourceDuration: number; author: string; license: string}[];
  captions: {start: number; end: number; text: string}[];
};
type Props = {story: WorkspaceStory};

const Scene = ({scene, number}: {scene: WorkspaceStory['scenes'][number]; number: number}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const scale = interpolate(frame, [0, scene.durationInFrames], [1.01, 1.055], {extrapolateRight: 'clamp'});
  return <AbsoluteFill style={{background: '#10271F', overflow: 'hidden'}}>
    {scene.src && (scene.kind === 'video'
      ? <Loop durationInFrames={Math.max(1, Math.floor(scene.sourceDuration * fps))}><Video src={staticFile(scene.src)} muted objectFit="cover" style={{width: '100%', height: '100%'}} /></Loop>
      : <CanvasImage src={staticFile(scene.src)} style={{width: '100%', height: '100%', objectFit: 'cover', transform: `scale(${scale})`}} />)}
    <AbsoluteFill style={{background: 'linear-gradient(180deg,rgba(5,20,15,.88),rgba(5,20,15,.05) 45%,rgba(5,20,15,.95))'}} />
    <div style={{position: 'absolute', top: 136, left: 76, right: 76, color: '#F7F5E7'}}>
      <div style={{fontSize: 28, letterSpacing: 4, color: '#BEE5CB'}}>ASTEL / {String(number).padStart(2, '0')}</div>
      <div style={{marginTop: 34, fontSize: 72, lineHeight: 1.1, fontWeight: 800, textWrap: 'balance', opacity: interpolate(frame, [0, 9], [0, 1], {extrapolateRight: 'clamp'})}}>{scene.title}</div>
    </div>
    <div style={{position: 'absolute', left: 76, right: 76, bottom: 65, color: '#D6E0D7', fontSize: 22, lineHeight: 1.4}}>{scene.author} · {scene.license}</div>
  </AbsoluteFill>;
};

const Captions = ({items}: {items: WorkspaceStory['captions']}) => {
  const frame = useCurrentFrame(); const {fps} = useVideoConfig();
  const item = items.find(cue => frame / fps >= cue.start && frame / fps < cue.end);
  if (!item) return null;
  return <div style={{position: 'absolute', left: 68, right: 68, bottom: 190, padding: '22px 28px', borderRadius: 20, background: 'rgba(5,20,15,.9)', color: '#FFFCEF', fontSize: 52, fontWeight: 600, textAlign: 'center', lineHeight: 1.22, textWrap: 'balance'}}>{item.text}</div>;
};

export const StoryShortV1 = ({story}: Props) => {
  const last = story.scenes[story.scenes.length - 1];
  const narrationFrames = last ? last.from + last.durationInFrames : 90;
  return <AbsoluteFill style={{background: '#10271F', fontFamily: 'Arial, Helvetica, sans-serif'}}>
    {story.audioSrc && <Audio src={staticFile(story.audioSrc)} />}
    {story.scenes.map((scene, index) => <Sequence key={scene.id} name={scene.title} from={scene.from} durationInFrames={scene.durationInFrames} premountFor={30}><Scene scene={scene} number={index + 1} /></Sequence>)}
    <Captions items={story.captions} />
    <Sequence from={narrationFrames} durationInFrames={90} name="Источники">
      <AbsoluteFill style={{padding: '160px 76px', color: '#10271F', background: '#EBCB83'}}>
        <div style={{fontSize: 30, letterSpacing: 3}}>ASTEL / ИСТОЧНИКИ</div>
        <div style={{fontSize: 76, fontWeight: 800, lineHeight: 1.1, marginTop: 70}}>{story.title}</div>
        <div style={{fontSize: 30, lineHeight: 1.5, marginTop: 90}}>{Array.from(new Set(story.scenes.map(s => `${s.author} · ${s.license}`))).slice(0, 8).map(source => <div key={source}>{source}</div>)}</div>
        <div style={{fontSize: 28, marginTop: 70}}>Полные источники и хэши: SOURCES.md</div>
      </AbsoluteFill>
    </Sequence>
  </AbsoluteFill>;
};

export const StoryShortV1Registration = () => <Composition id="StoryShortV1" component={StoryShortV1} width={1080} height={1920} fps={30} durationInFrames={390}
  defaultProps={{story: {id: 'preview', title: 'Новая история', durationInFrames: 390, audioSrc: '', scenes: [{id: 'scene-1', title: 'Ваш сценарий и выбранные материалы', from: 0, durationInFrames: 300, src: '', kind: 'image', sourceDuration: 0, author: 'Astel', license: 'Предпросмотр шаблона'}], captions: []}}}
  calculateMetadata={({props}) => ({durationInFrames: props.story.durationInFrames})} />;
