import {Easing, interpolate} from 'remotion';

// Both renderers sample this pure timeline. Seeking backwards or rendering
// frames out of order must not advance a simulation or a wall-clock animation.
export const motionState = (frame: number, fps: number) => {
  const seconds = frame / fps;
  const ramp = (start: number, end: number) => interpolate(seconds, [start, end], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.bezier(0.65, 0, 0.2, 1),
  });
  return {
    seconds,
    entrance: ramp(0, 0.85),
    box: ramp(3.2, 4.4),
    server: ramp(7.2, 8.6),
    network: ramp(9, 10.6),
    beat: seconds < 3.8 ? 0 : seconds < 7.9 ? 1 : 2,
  };
};

export const palette = {
  ink: '#102421', paper: '#F3F0E7', muted: '#A7B7AD',
  mint: '#A2E4BB', amber: '#EDA35D', line: '#35554B',
};
