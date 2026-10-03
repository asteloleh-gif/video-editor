# AstelFam Editor v0.1

Browser editor for reviewing and correcting AI-generated AstelFam Shorts.

- Video stays local in the browser.
- Split/delete/reorder/trim video clips.
- Add and drag text directly on the 9:16 preview.
- Resize text and retime it on the timeline.
- Built-in AI draft for the current ~63s AstelFam test video.
- Save/load editable project JSON.
- Auto-save project state in localStorage.

The JSON is the contract between the browser editor and the existing Python/Remotion renderer.

## Local

cd editor
npm install
npm run dev

## Production build

npm run build
