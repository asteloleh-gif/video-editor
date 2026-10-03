import React from 'react';
import {Composition} from 'remotion';
import {AstelFamShort} from './AstelFamShort';
import {BattleBoxShort, ShortProps} from './Short';

const defaultProps: ShortProps = {
  videoSrc: '',
  durationInFrames: 900,
  fps: 30,
  events: [],
  captions: [],
  style: {
    accent: '#D7FF35',
    danger: '#FF5D5D',
    text: '#FFFFFF',
    panel: 'rgba(8, 12, 10, 0.88)',
    shadow: 'rgba(0, 0, 0, 0.55)',
    brand: 'BATTLE BOX',
    show_brand: true,
    show_attempt_counter: true,
    show_score_counter: true,
    reaction_zoom: 1.045,
    caption: {enabled: true, font_size: 64, bottom: 150},
    event_badge: {enabled: true, font_size: 90, top: 180},
  },
};

const astelFamDefaultProps: ShortProps = {
  ...defaultProps,
  style: {
    accent: '#FFD84D',
    danger: '#FF6B7A',
    text: '#FFFFFF',
    panel: 'rgba(12, 12, 16, 0.76)',
    shadow: 'rgba(0, 0, 0, 0.62)',
    brand: 'ASTEL FAM',
    show_brand: true,
    show_attempt_counter: false,
    show_score_counter: false,
    reaction_zoom: 1.07,
    caption: {enabled: true, font_size: 60, bottom: 150},
    event_badge: {enabled: true, font_size: 72, top: 170},
  },
};

export const Root: React.FC = () => {
  return (
    <>
      <Composition
        id="BattleBoxShort"
        component={BattleBoxShort}
        durationInFrames={900}
        fps={30}
        width={1080}
        height={1920}
        defaultProps={defaultProps}
      />
      <Composition
        id="AstelFamShort"
        component={AstelFamShort}
        durationInFrames={900}
        fps={30}
        width={1080}
        height={1920}
        defaultProps={astelFamDefaultProps}
      />
    </>
  );
};
