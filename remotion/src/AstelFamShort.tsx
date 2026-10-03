import React from 'react';
import {
  AbsoluteFill,
  Easing,
  OffthreadVideo,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import type {ShortProps} from './Short';

type AstelFamStyle = ShortProps['style'] & {
  secondary?: string;
  astelfam?: {
    show_title?: boolean;
    title?: string;
    emoji_reactions?: boolean;
    caption_max_width?: number;
    caption_bottom?: number;
  };
};

const activeCue = <T extends {start: number; end: number}>(items: T[], time: number): T | undefined =>
  items.find((item) => time >= item.start && time < item.end);

const eventCopy = (label: string): {text: string; emoji: string} | null => {
  if (label === 'attempt') return {text: 'LET\'S GO!', emoji: '⚡'};
  if (label === 'score') return {text: 'YES!', emoji: '🔥'};
  if (label === 'miss') return {text: 'NOOO!', emoji: '💀'};
  if (label === 'reaction') return {text: 'LOL', emoji: '😂'};
  return null;
};

const splitCaption = (text: string) => {
  const words = text.trim().split(/\s+/).filter(Boolean);
  if (words.length <= 1) return {lead: text.trim(), punch: ''};
  const punchCount = words.length >= 7 ? 2 : 1;
  return {
    lead: words.slice(0, -punchCount).join(' '),
    punch: words.slice(-punchCount).join(' '),
  };
};

export const AstelFamShort: React.FC<ShortProps> = ({videoSrc, events, captions, style}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const time = frame / fps;
  const cfg = style as AstelFamStyle;

  const accent = cfg.accent ?? '#FFD84D';
  const secondary = cfg.secondary ?? '#80F3D2';
  const danger = cfg.danger ?? '#FF6B7A';
  const textColor = cfg.text ?? '#FFFFFF';
  const panel = cfg.panel ?? 'rgba(12, 12, 16, 0.76)';
  const shadow = cfg.shadow ?? 'rgba(0, 0, 0, 0.62)';

  const event = activeCue(events, time);
  const caption = activeCue(captions, time);
  const reaction = events.find((item) => item.label === 'reaction' && time >= item.start && time < item.end);
  const copy = event ? eventCopy(event.label) : null;

  let zoom = 1;
  if (reaction) {
    const duration = Math.max(0.12, reaction.end - reaction.start);
    const progress = Math.min(1, Math.max(0, (time - reaction.start) / duration));
    const pulse = interpolate(progress, [0, 0.22, 0.62, 1], [0, 1, 0.82, 0], {
      easing: Easing.inOut(Easing.cubic),
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
    });
    zoom = 1 + ((cfg.reaction_zoom ?? 1.07) - 1) * pulse;
  }

  const captionStartFrame = caption ? Math.round(caption.start * fps) : frame;
  const captionLocalFrame = Math.max(0, frame - captionStartFrame);
  const captionIn = spring({
    fps,
    frame: captionLocalFrame,
    config: {damping: 18, stiffness: 260, mass: 0.72},
    durationInFrames: Math.max(1, Math.round(fps * 0.32)),
  });
  const captionExit = caption
    ? interpolate(caption.end - time, [0, 0.12], [0, 1], {
        extrapolateLeft: 'clamp',
        extrapolateRight: 'clamp',
      })
    : 0;
  const captionMotion = captionIn * captionExit;

  const eventStartFrame = event ? Math.round(event.start * fps) : frame;
  const eventLocalFrame = Math.max(0, frame - eventStartFrame);
  const eventPop = spring({
    fps,
    frame: eventLocalFrame,
    config: {damping: 11, stiffness: 330, mass: 0.62},
    durationInFrames: Math.max(1, Math.round(fps * 0.38)),
  });

  const flash = event?.label === 'score' || event?.label === 'miss'
    ? interpolate(eventLocalFrame, [0, fps * 0.08, fps * 0.32], [0, 0.9, 0], {
        extrapolateLeft: 'clamp',
        extrapolateRight: 'clamp',
        easing: Easing.out(Easing.quad),
      })
    : 0;

  const captionParts = caption ? splitCaption(caption.text) : null;
  const badgeColor = event?.label === 'miss' ? danger : accent;

  return (
    <AbsoluteFill style={{backgroundColor: '#000', overflow: 'hidden'}}>
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

      <AbsoluteFill
        style={{
          pointerEvents: 'none',
          boxShadow: `inset 0 0 0 18px rgba(255,255,255,${flash * 0.18})`,
          opacity: flash,
        }}
      />

      {cfg.astelfam?.show_title !== false ? (
        <div
          style={{
            position: 'absolute',
            top: 68,
            left: '50%',
            transform: 'translateX(-50%)',
            padding: '10px 20px',
            borderRadius: 999,
            background: 'rgba(0,0,0,0.58)',
            backdropFilter: 'blur(10px)',
            color: textColor,
            fontFamily: 'Arial Black, Arial, sans-serif',
            fontSize: 26,
            letterSpacing: 2.4,
            boxShadow: `0 10px 30px ${shadow}`,
            whiteSpace: 'nowrap',
          }}
        >
          {cfg.astelfam?.title ?? cfg.brand ?? 'ASTEL FAM'}
        </div>
      ) : null}

      {copy ? (
        <div
          style={{
            position: 'absolute',
            top: cfg.event_badge?.top ?? 170,
            left: 60,
            right: 60,
            display: 'flex',
            justifyContent: 'center',
            transform: `scale(${0.68 + eventPop * 0.32}) rotate(${(1 - eventPop) * -5}deg)`,
            opacity: Math.min(1, eventPop * 1.15),
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 16,
              padding: '12px 28px 14px',
              borderRadius: 24,
              background: 'rgba(0,0,0,0.70)',
              boxShadow: `0 12px 34px ${shadow}`,
              border: `3px solid ${badgeColor}`,
              color: textColor,
              fontFamily: 'Arial Black, Arial, sans-serif',
              fontSize: cfg.event_badge?.font_size ?? 72,
              lineHeight: 1,
              textShadow: `0 5px 16px ${shadow}`,
            }}
          >
            <span style={{fontSize: '0.82em'}}>{copy.emoji}</span>
            <span>{copy.text}</span>
          </div>
        </div>
      ) : null}

      {reaction && cfg.astelfam?.emoji_reactions !== false ? (
        <>
          {[
            {left: 90, top: 480, rotate: -14, delay: 0},
            {right: 84, top: 620, rotate: 13, delay: 3},
            {left: 150, bottom: 520, rotate: 9, delay: 6},
          ].map((item, index) => {
            const emojiPop = spring({
              fps,
              frame: Math.max(0, eventLocalFrame - item.delay),
              config: {damping: 10, stiffness: 280, mass: 0.65},
            });
            return (
              <div
                key={index}
                style={{
                  position: 'absolute',
                  left: item.left,
                  right: item.right,
                  top: item.top,
                  bottom: item.bottom,
                  fontSize: 88,
                  transform: `scale(${emojiPop}) rotate(${item.rotate}deg)`,
                  filter: `drop-shadow(0 8px 14px ${shadow})`,
                }}
              >
                😂
              </div>
            );
          })}
        </>
      ) : null}

      {cfg.caption?.enabled !== false && caption && captionParts ? (
        <div
          style={{
            position: 'absolute',
            left: 64,
            right: 64,
            bottom: cfg.astelfam?.caption_bottom ?? cfg.caption?.bottom ?? 150,
            display: 'flex',
            justifyContent: 'center',
            opacity: captionMotion,
            transform: `translateY(${(1 - captionMotion) * 34}px) scale(${0.9 + captionMotion * 0.1})`,
          }}
        >
          <div
            style={{
              maxWidth: cfg.astelfam?.caption_max_width ?? 900,
              padding: '16px 26px 19px',
              borderRadius: 26,
              background: panel,
              boxShadow: `0 14px 38px ${shadow}`,
              border: '1px solid rgba(255,255,255,0.14)',
              color: textColor,
              fontFamily: 'Arial Black, Arial, sans-serif',
              fontSize: cfg.caption?.font_size ?? 60,
              lineHeight: 1.02,
              textAlign: 'center',
              textShadow: `0 4px 14px ${shadow}`,
            }}
          >
            {captionParts.lead ? <span>{captionParts.lead} </span> : null}
            {captionParts.punch ? (
              <span
                style={{
                  display: 'inline-block',
                  color: event?.label === 'miss' ? danger : event?.label === 'reaction' ? secondary : accent,
                  transform: `scale(${0.96 + captionMotion * 0.04})`,
                }}
              >
                {captionParts.punch}
              </span>
            ) : null}
          </div>
        </div>
      ) : null}
    </AbsoluteFill>
  );
};
