import React from 'react';
import {ThreeCanvas} from '@remotion/three';
import {Color} from 'three';
import {useCurrentFrame, useVideoConfig} from 'remotion';
import {motionState, palette as c} from './timing';

type Props = {width: number; height: number};
type RackProps = {x: number; amount: number};

const SatelliteRack = ({x, amount}: RackProps) => <group position={[x*amount,-0.12,-1.25]} scale={0.68*amount+0.001}>
  <mesh castShadow><boxGeometry args={[1.35,2.65,1.15]}/><meshStandardMaterial color="#275344" roughness={0.48}/></mesh>
  {[0,1,2,3,4].map(n=><group key={n} position={[0,.97-n*.48,.59]}>
    <mesh><boxGeometry args={[1.09,.34,.06]}/><meshStandardMaterial color="#112D26"/></mesh>
    <mesh position={[.38,0,.04]}><sphereGeometry args={[.035,8,8]}/><meshStandardMaterial color={c.mint} emissive={c.mint} emissiveIntensity={0.5}/></mesh>
  </group>)}
</group>;

export const VolumeMotion = ({width, height}: Props) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const m = motionState(frame, fps);
  const book = 1-m.box;
  const box = m.box*(1-m.server);
  const w = 1.85+m.box*.55-m.server*.85;
  const h = 2.6-m.box*.65+m.server*.9;
  const d = .38+m.box*1.35-m.server*.35;
  const color = new Color(c.amber).lerp(new Color('#2C6550'),m.server);

  return <ThreeCanvas width={width} height={height} orthographic shadows="soft"
    camera={{position:[5,3.3,8],zoom:Math.min(width,height)*.18,near:.1,far:60}}
    onCreated={({camera})=>camera.lookAt(0,-.1,0)}
    gl={{antialias:true,alpha:true}} dpr={1}>
    <ambientLight intensity={1.4}/>
    <directionalLight position={[3,7,5]} intensity={3.2} color="#FFE6C4" castShadow shadow-mapSize={[1024,1024]} shadow-camera-left={-7} shadow-camera-right={7} shadow-camera-top={7} shadow-camera-bottom={-7} shadow-bias={-.001}/>
    <pointLight position={[-4,2,3]} intensity={24} color={c.mint}/>
    <directionalLight position={[-4,3,-4]} intensity={2.2} color="#B7D8E7"/>
    <mesh rotation={[-Math.PI/2,0,0]} position={[0,-1.83,0]} receiveShadow>
      <planeGeometry args={[200,200]}/><shadowMaterial transparent opacity={.3}/>
    </mesh>
    <group position={[0,(1-m.entrance)*1.5+.04*Math.sin(m.seconds*1.3),0]}
      rotation={[0,-.28+m.box*.55+m.server*.35,0]} scale={.8+.2*m.entrance}>
      <mesh castShadow receiveShadow><boxGeometry args={[w,h,d]}/><meshStandardMaterial color={color} roughness={.38} metalness={.08}/></mesh>
      <group scale={[book+.001,book+.001,book+.001]}>
        <mesh position={[.035,0,0]}><boxGeometry args={[w-.13,h-.12,d+.06]}/><meshStandardMaterial color={c.paper} roughness={.85}/></mesh>
        <mesh position={[0,0,d/2+.055]} castShadow><boxGeometry args={[w+.025,h+.025,.06]}/><meshStandardMaterial color={c.amber} roughness={.45}/></mesh>
        <mesh position={[0,0,-d/2-.055]}><boxGeometry args={[w+.025,h+.025,.06]}/><meshStandardMaterial color="#C47941"/></mesh>
        <mesh position={[-w/2+.045,0,.04]}><boxGeometry args={[.12,h,.5]}/><meshStandardMaterial color="#A65E32"/></mesh>
        <mesh position={[.05,.65,d/2+.094]}><boxGeometry args={[1.15,.045,.012]}/><meshStandardMaterial color={c.paper}/></mesh>
        <mesh position={[-.11,.49,d/2+.094]}><boxGeometry args={[.83,.045,.012]}/><meshStandardMaterial color={c.paper}/></mesh>
      </group>
      <group scale={[box+.001,box+.001,box+.001]}>
        <mesh position={[0,0,d/2+.014]}><boxGeometry args={[.32,h+.01,.018]}/><meshStandardMaterial color="#F1CA95" roughness={.78}/></mesh>
        <mesh position={[0,h/2+.012,0]}><boxGeometry args={[.32,.022,d+.02]}/><meshStandardMaterial color="#F1CA95" roughness={.78}/></mesh>
        <mesh position={[-.58,-.53,d/2+.027]}><boxGeometry args={[.6,.4,.018]}/><meshStandardMaterial color={c.paper}/></mesh>
        <mesh position={[-.6,-.47,d/2+.043]}><boxGeometry args={[.38,.025,.006]}/><meshStandardMaterial color={c.ink}/></mesh>
      </group>
      <group scale={[m.server+.001,m.server+.001,m.server+.001]}>
        {[0,1,2,3,4].map(n=><group key={n} position={[0,1.04-n*.51,d/2+.025]}>
          <mesh><boxGeometry args={[1.25,.37,.055]}/><meshStandardMaterial color="#0F2B24" roughness={.32} metalness={.32}/></mesh>
          {[0,1,2].map(j=><mesh key={j} position={[-.17,.07-j*.065,.035]}><boxGeometry args={[.65,.018,.016]}/><meshStandardMaterial color="#57816C"/></mesh>)}
          <mesh position={[.43,0,.055]}><sphereGeometry args={[.032,10,10]}/><meshStandardMaterial color={c.mint} emissive={c.mint} emissiveIntensity={1}/></mesh>
        </group>)}
      </group>
    </group>
    <SatelliteRack x={-2.2} amount={m.network}/>
    <SatelliteRack x={2.2} amount={m.network}/>
    {[0,1,2,3,4,5].map(n=>{
      const u=(m.seconds*.32+n/6)%1;
      return <mesh key={n} position={[-2.2+4.4*u,-1.68,-.6]} scale={m.network*.055+.001}>
        <sphereGeometry args={[1,8,8]}/><meshStandardMaterial color={c.mint} emissive={c.mint} emissiveIntensity={.7}/>
      </mesh>;
    })}
  </ThreeCanvas>;
};
