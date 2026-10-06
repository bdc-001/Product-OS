import React, {useLayoutEffect, useRef} from 'react';
import {AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame} from 'remotion';
import {FilmRoot, SceneLayer} from './World';
import type {FilmProps, Scene} from './Film';

type PiiScene = Scene & {treatment: string; cueFrames: Record<string, number>; demoFrame?: number};
const ease = Easing.bezier(.16, 1, .3, 1);

function plateFor(scene: PiiScene, frame: number): string {
  const type = scene.treatment;
  const progress = scene.frames ? frame / scene.frames : 0;
  const cue = (key: string, fallback: number) => scene.cueFrames?.[key] ?? fallback;
  if (type === 'every') return frame >= cue('word', 18) ? 'plate-03.jpg' : 'plate-02.jpg';
  if (type === 'introduce') return frame >= cue('pii', 24) ? 'plate-10.jpg' : 'plate-09.jpg';
  if (type === 'select') return progress < .28 ? 'plate-11.jpg' : progress < .62 ? 'plate-12.jpg' : 'plate-13.jpg';
  if (type === 'surfaces') return progress < .34 ? 'plate-14.jpg' : progress < .68 ? 'plate-15.jpg' : 'plate-16.jpg';
  const stills: Record<string, string> = {
    remember: 'plate-01.jpg', scatter: 'plate-04.jpg', moment: 'plate-05.jpg', personal: 'plate-06.jpg',
    repeat: 'plate-07.jpg', preserve: 'plate-08.jpg', products: 'plate-17.jpg', transcript: 'plate-18.jpg',
    replace: 'plate-18.jpg', audio: 'plate-19.jpg', quality: 'plate-20.jpg', manager: 'plate-21.jpg',
    privacy: 'plate-22.jpg', experience: 'plate-23.jpg', brand: 'plate-24.jpg',
  };
  return stills[type] || 'plate-01.jpg';
}

function Shot({scene, index}: {scene: PiiScene; index: number}) {
  const frame = useCurrentFrame();
  const ref = useRef<HTMLDivElement>(null);
  const type = scene.treatment;
  const dark = index <= 6;
  const solid = type === 'select' || type === 'surfaces';
  const caption = scene.captions.find(c => frame >= c.from && frame < c.to);
  const zoom = interpolate(frame, [0, scene.frames], [1, 1.045], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ease});
  useLayoutEffect(() => {
    if (frame !== scene.frames - 2 || !ref.current) return;
    const parent = ref.current.getBoundingClientRect();
    if (parent.width === 0 || parent.height === 0) return;
    const boxes = Array.from(ref.current.querySelectorAll<HTMLElement>('[data-pii-text]')).map(e => ({r: e.getBoundingClientRect(), text: e.textContent}));
    for (const {r, text} of boxes) if (r.left < parent.left - 1 || r.right > parent.right + 1 || r.top < parent.top - 1 || r.bottom > parent.bottom + 1)
      throw new Error(`PII shot ${index + 1}: text outside frame: ${text}`);
    for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
      const a = boxes[i].r, b = boxes[j].r;
      if (Math.min(a.right, b.right) - Math.max(a.left, b.left) > 3 && Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 3)
        throw new Error(`PII shot ${index + 1}: text overlaps: ${boxes[i].text} / ${boxes[j].text}`);
    }
  }, [frame, index, scene.frames]);
  return (
    <AbsoluteFill ref={ref} style={{background: 'transparent', overflow: 'hidden'}}>
      <Img src={staticFile(plateFor(scene, frame))} style={{width: 1920, height: 1080, objectFit: 'cover', transform: `scale(${zoom})`, transformOrigin: 'center center'}}/>
      {caption && (
        <div data-pii-text style={{position: 'absolute', left: 160, right: 160, bottom: 62, textAlign: 'center', fontSize: 42, lineHeight: 1.4, color: dark || solid ? '#F1F1F1' : '#151515'}}>
          <span style={{padding: '9px 20px', borderRadius: 10, background: dark || solid ? '#06132CDD' : '#EEF4FFF0'}}>{caption.text}</span>
  </div>
      )}
    </AbsoluteFill>
  );
}

export const PiiFilm: React.FC<FilmProps> = ({scenes, audio, audioFrom = 3, portrait, craft, title, durationInFrames, preview}) => {
  if (portrait) throw new Error('This supplied storyboard is composed for 16:9. Render the landscape version.');
  return (
    <FilmRoot scenes={scenes} audio={audio} audioFrom={audioFrom} portrait={false} craft={craft} title={title || 'PII Masking'} durationInFrames={durationInFrames} preview={preview} chrome={false} photographic="conversation.jpg">
      {scenes.map((s, i) => <SceneLayer key={i} index={i} scene={s} total={scenes.length}><Shot scene={s as PiiScene} index={i}/></SceneLayer>)}
    </FilmRoot>
  );
};
