import React from 'react';
import {
  AbsoluteFill,
  Easing,
  OffthreadVideo,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';

export type EventCue = {
  start: number;
  end: number;
  label: string;
  confidence?: number;
};

export type CaptionCue = {
  start: number;
  end: number;
  text: string;
};

export type StyleConfig = {
  accent?: string;
  danger?: string;
  text?: string;
  panel?: string;
  shadow?: string;
  brand?: string;
  show_brand?: boolean;
  show_attempt_counter?: boolean;
  show_score_counter?: boolean;
  reaction_zoom?: number;
  caption?: {
    enabled?: boolean;
    font_size?: number;
    bottom?: number;
  };
  event_badge?: {
    enabled?: boolean;
    font_size?: number;
    top?: number;
  };
};

export type ShortProps = {
  videoSrc: string;
  durationInFrames: number;
  fps: number;
  events: EventCue[];
  captions: CaptionCue[];
  style: StyleConfig;
};

const activeCue = <T extends {start: number; end: number}>(items: T[], time: number): T | undefined =>
  items.find((item) => time >= item.start && time < item.end);

const badgeText = (label: string): string | null => {
  if (label === 'score') return 'SCORE!';
  if (label === 'miss') return 'MISS';
  if (label === 'attempt') return 'GO!';
  return null;
};

export const BattleBoxShort: React.FC<ShortProps> = ({videoSrc, events, captions, style}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const time = frame / fps;

  const accent = style.accent ?? '#D7FF35';
  const danger = style.danger ?? '#FF5D5D';
  const textColor = style.text ?? '#FFFFFF';
  const panel = style.panel ?? 'rgba(8, 12, 10, 0.88)';
  const shadow = style.shadow ?? 'rgba(0, 0, 0, 0.55)';

  const event = activeCue(events, time);
  const caption = activeCue(captions, time);
  const reaction = events.find((item) => item.label === 'reaction' && time >= item.start && time < item.end);
  const scoreCount = events.filter((item) => item.label === 'score' && item.start <= time).length;
  const attemptCount = events.filter((item) => item.label === 'attempt' && item.start <= time).length;

  let zoom = 1;
  if (reaction) {
    const duration = Math.max(0.08, reaction.end - reaction.start);
    const progress = Math.min(1, Math.max(0, (time - reaction.start) / duration));
    const pulse = interpolate(progress, [0, 0.35, 1], [0, 1, 0], {
      easing: Easing.inOut(Easing.quad),
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
    });
    zoom = 1 + ((style.reaction_zoom ?? 1.045) - 1) * pulse;
  }

  const badge = event ? badgeText(event.label) : null;
  const badgeColor = event?.label === 'miss' ? danger : accent;

  return (
    <AbsoluteFill style={{backgroundColor: '#000000', overflow: 'hidden'}}>
      {videoSrc ? (
        <OffthreadVideo
          src={staticFile(videoSrc)}
          style={{
            width: '100%',
            height: '100%',
            objectFit: 'cover',
            transform: `scale(${zoom})`,
          }}
        />
      ) : null}

      {style.show_brand !== false ? (
        <div
          style={{
            position: 'absolute',
            top: 74,
            left: 54,
            padding: '12px 20px',
            borderRadius: 16,
            background: panel,
            color: accent,
            fontFamily: 'Arial Black, Arial, sans-serif',
            fontSize: 36,
            letterSpacing: 2,
            boxShadow: `0 8px 24px ${shadow}`,
          }}
        >
          {style.brand ?? 'BATTLE BOX'}
        </div>
      ) : null}

      {(style.show_attempt_counter !== false || style.show_score_counter !== false) ? (
        <div
          style={{
            position: 'absolute',
            top: 72,
            right: 54,
            display: 'flex',
            gap: 12,
            fontFamily: 'Arial Black, Arial, sans-serif',
            fontSize: 32,
            color: textColor,
          }}
        >
          {style.show_attempt_counter !== false ? (
            <div style={{padding: '12px 18px', borderRadius: 16, background: panel}}>TRY {attemptCount}</div>
          ) : null}
          {style.show_score_counter !== false ? (
            <div style={{padding: '12px 18px', borderRadius: 16, background: accent, color: '#0A0D0B'}}>
              SCORE {scoreCount}
            </div>
          ) : null}
        </div>
      ) : null}

      {style.event_badge?.enabled !== false && badge ? (
        <div
          style={{
            position: 'absolute',
            top: style.event_badge?.top ?? 180,
            left: 0,
            right: 0,
            textAlign: 'center',
            color: badgeColor,
            fontFamily: 'Arial Black, Arial, sans-serif',
            fontSize: style.event_badge?.font_size ?? 90,
            textShadow: `0 8px 24px ${shadow}`,
            WebkitTextStroke: '2px rgba(0,0,0,0.45)',
          }}
        >
          {badge}
        </div>
      ) : null}

      {style.caption?.enabled !== false && caption ? (
        <div
          style={{
            position: 'absolute',
            left: 70,
            right: 70,
            bottom: style.caption?.bottom ?? 150,
            display: 'flex',
            justifyContent: 'center',
          }}
        >
          <div
            style={{
              maxWidth: 940,
              padding: '16px 28px',
              borderRadius: 20,
              background: panel,
              color: textColor,
              fontFamily: 'Arial Black, Arial, sans-serif',
              fontSize: style.caption?.font_size ?? 64,
              lineHeight: 1.08,
              textAlign: 'center',
              textShadow: `0 4px 14px ${shadow}`,
            }}
          >
            {caption.text}
          </div>
        </div>
      ) : null}
    </AbsoluteFill>
  );
};
