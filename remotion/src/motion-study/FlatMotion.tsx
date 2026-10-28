import React from 'react';
import {useCurrentFrame, useVideoConfig} from 'remotion';
import {motionState, palette as c} from './timing';

type Props = {width: number; height: number};

export const FlatMotion = ({width, height}: Props) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const m = motionState(frame, fps);
  const w = 220 + m.box * 120 - m.server * 110;
  const h = 300 - m.box * 60 + m.server * 110;
  const x = 500 - w / 2;
  const y = 383 - h / 2 + (1 - m.entrance) * 70;
  const book = 1 - m.box;
  const box = m.box * (1 - m.server);

  return <svg width={width} height={height} viewBox="0 0 1000 800" role="img" aria-label="Книга превращается в посылку и серверную систему">
    <defs>
      <linearGradient id="flat-body" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stopColor={c.amber}/><stop offset="1" stopColor="#C8793D"/>
      </linearGradient>
    </defs>
    <g transform="translate(500 400) scale(1.2) translate(-500 -400)">
    <ellipse cx="500" cy="630" rx={170 + m.network * 190} ry="15" fill="#071A17" opacity="0.6"/>
    <g opacity={m.network}>
      <path d="M500 525 V585 H225 V418 M500 585 H775 V418" fill="none" stroke={c.mint} strokeWidth="3" strokeDasharray="7 10"/>
      {[225,775].map((cx, i) => <g key={cx} opacity={m.network} style={{translate:`${(1-m.network)*(i===0?100:-100)}px 0`}}>
        <rect x={cx-68} y="310" width="136" height="244" rx="12" fill="#1A3A32" stroke={c.mint} strokeWidth="3"/>
        {[0,1,2,3].map(n=><g key={n}><rect x={cx-47} y={333+n*48} width="94" height="32" rx="3" fill="#294B3F"/><circle cx={cx+30} cy={349+n*48} r="4" fill={c.mint}/></g>)}
      </g>)}
      {[0,1,2,3,4].map(n => {
        const u = ((m.seconds * 0.34 + n * 0.2) % 1);
        return <circle key={n} cx={225+u*550} cy="585" r="5" fill={c.mint}/>;
      })}
    </g>
    <g opacity={m.entrance} style={{translate:`0 ${Math.sin(m.seconds*1.3)*4}px`}}>
      <rect x={x+11} y={y+11} width={w} height={h} rx="14" fill="#061C17"/>
      <rect x={x} y={y} width={w} height={h} rx="12" fill="url(#flat-body)"/>
      <rect x={x} y={y} width={w} height={h} rx="12" fill="#204B3F" opacity={m.server}/>
      <g opacity={book}>
        <rect x={x+16} y={y+12} width="15" height={h-24} rx="4" fill="#9E4C25"/>
        <path d={`M${x+48} ${y+44} H${x+w-36} M${x+48} ${y+60} H${x+w-62}`} stroke={c.paper} strokeWidth="6"/>
        <text x={x+48} y={y+173} fontSize="65" fontWeight="800" fill={c.ink} fontFamily="Arial">01</text>
        <path d={`M${x+48} ${y+h-47} H${x+w-38}`} stroke={c.ink} strokeWidth="4"/>
        <rect x={x+w-13} y={y+10} width="12" height={h-20} fill={c.paper}/>
      </g>
      <g opacity={box}>
        <rect x="479" y={y} width="42" height={h} fill="#F9D5A4"/>
        <path d={`M${x} ${y+36} H${x+w}`} stroke="#A85B30" strokeWidth="3"/>
        <rect x={x+30} y={y+h-85} width="85" height="56" rx="4" fill={c.paper}/>
        <path d={`M${x+42} ${y+h-68} H${x+95} M${x+42} ${y+h-55} H${x+78}`} stroke={c.ink} strokeWidth="3"/>
      </g>
      <g opacity={m.server}>
        {[0,1,2,3,4].map(n=><g key={n}>
          <rect x={x+19} y={y+23+n*61} width={w-38} height="45" rx="5" fill="#102F27" stroke="#5A8671" strokeWidth="2"/>
          <path d={`M${x+35} ${y+39+n*61} H${x+w-59} M${x+35} ${y+48+n*61} H${x+w-59}`} stroke="#517761" strokeWidth="3"/>
          <circle cx={x+w-36} cy={y+46+n*61} r="5" fill={c.mint}/>
        </g>)}
      </g>
    </g>
    <path d="M350 665 H650" stroke={c.line} strokeWidth="2"/>
    </g>
  </svg>;
};
