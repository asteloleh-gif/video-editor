import React from 'react';
import {Composition} from 'remotion';
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

export const Root: React.FC = () => {
  return (
    <Composition
      id="BattleBoxShort"
      component={BattleBoxShort}
      durationInFrames={900}
      fps={30}
      width={1080}
      height={1920}
      defaultProps={defaultProps}
    />
  );
};
