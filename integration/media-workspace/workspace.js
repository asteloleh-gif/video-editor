/* Local preparation adapter for the existing owner-supplied Canvas.
 * These cards are real Mac artifacts; they are not Hub publication plans.
 */
(() => {
  'use strict';
  const page = document.createElement('section'); page.className = 'page'; page.id = 'page-astel-preparation';
  document.querySelector('.content').append(page);
  const nav = document.createElement('button'); nav.className = 'nav'; nav.dataset.page = 'astel-preparation'; nav.textContent = '▶ Черновики с Mac';
  document.querySelector('.sidegroup').prepend(nav);
  // The original Canvas captures these arrays at startup. Extend its own
  // navigation so existing sections and the new preparation view hide correctly.
  if(typeof navs!=='undefined')navs.unshift(nav);
  if(typeof pages!=='undefined')pages.push(page);
  const old = document.querySelector('[data-page="distribution"]'); if (old) old.textContent = '▷ Hub · учебный экран';
  const connect = document.getElementById('dc-connect'); if (connect) {connect.disabled = true; connect.title = 'Для серверного Hub нужен существующий защищённый Telegram-backend';}
  let state = {stories: [], jobs: []}, selected = null, busy = false, error = '';
  const notes = new Map(); const pendingKey = 'astel-canvas-editorial-pending-v1';
  try {const saved=JSON.parse(localStorage.getItem(pendingKey)||'null');if(saved&&typeof saved.story_id==='string'&&typeof saved.digest==='string'&&typeof saved.note==='string'&&saved.note.length<=2000){selected=saved.story_id;notes.set(saved.digest,saved.note);}} catch {localStorage.removeItem(pendingKey);}
  const el = (tag, cls, text) => {const n=document.createElement(tag); if(cls)n.className=cls; if(text!==undefined)n.textContent=text; return n;};
  const button = (text, action, cls='action') => {const n=el('button',cls,text);n.type='button';n.onclick=action;return n;};
  async function api(path, options) {
    const response = await fetch(path,{credentials:'same-origin',cache:'no-store',redirect:'error',...options});
    const value = await response.json();
    if (!response.ok) throw Error(value.error || 'Локальная библиотека недоступна. Обновите страницу.');
    return value;
  }
  async function refresh() {
    try {state = await api('/api/astel-workspace');error='';if(!state.stories.some(s=>s.artifact_job_id===selected))selected=state.stories[0]?.artifact_job_id||null;render();}
    catch (e) {error=e.message;render();}
  }
  async function review(card, decision, note) {
    if(busy)return;busy=true;error='';
    let request;
    try {
      const saved = localStorage.getItem(pendingKey);
      request = saved ? JSON.parse(saved) : {request_id:crypto.randomUUID(),story_id:card.artifact_job_id,digest:card.digest,decision,note};
      if(saved && (request.story_id!==card.artifact_job_id||request.digest!==card.digest||request.decision!==decision||request.note!==note))throw Error('Есть неподтверждённое сохранение замечания. Повторите прежнее действие после обновления страницы.');
      localStorage.setItem(pendingKey,JSON.stringify(request));render();
      await api('/api/astel-workspace/review',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(request)});
      localStorage.removeItem(pendingKey);await refresh();
    } catch(e) {error=e.message;if(/rejected|conflict/i.test(error))localStorage.removeItem(pendingKey);}
    finally {busy=false;render();}
  }
  function detail(card) {
    const d=el('article','aw-detail');d.append(el('div','ey','РЕАЛЬНЫЙ ЧЕРНОВИК / MAC'),el('h3','',card.title));
    d.append(el('p','muted',`Версия ${card.revision} · ${card.artifact.duration.toFixed(1)} с · ${card.voice.profile}`));
    if(card.state==='superseded')d.append(el('div','notice','Есть новая версия. Решения по этой версии больше не принимаются.'));
    const film=el('div','aw-film'),video=el('video');video.controls=true;video.preload='metadata';video.playsInline=true;video.src=`/api/astel-workspace/stories/${card.artifact_job_id}/video.mp4`;video.setAttribute('aria-label','Видео точной версии черновика');
    video.onerror=()=>{error='MP4 не открылся. Версия могла измениться или Mac недоступен.';const n=el('p','aw-error',error);d.append(n);};
    const text=el('div');text.append(el('h4','','Сценарий'),el('div','aw-script',card.script),el('p','aw-hash',`SHA-256 MP4: ${card.artifact.sha256}`),el('p','aw-hash',`Story digest: ${card.digest}`));
    const cardLink=el('a','linkbtn','Скачать карточку JSON');cardLink.href=`/api/astel-workspace/stories/${card.artifact_job_id}/card`;cardLink.download=`Astel-review-${card.artifact_job_id}.json`;text.append(cardLink);
    text.append(el('p','muted','Субтитры: автоматический черновик, требуют проверки. Сценарий и кадры правятся в OpenReel → Материалы и истории → Для Canvas → Новая версия.'));
    for(const source of card.sources){const s=el('div','aw-source');s.append(el('strong','',source.author+' · '+source.license));const url=window.AstelDistributionCore?.publicUrl(source.sourceUrl);if(url){const a=el('a','','Открыть исходник');a.href=url;a.target='_blank';a.rel='noopener noreferrer';s.append(el('br'),a);}text.append(s);}
    film.append(video,text);d.append(film);
    const r=el('div','aw-review');r.append(el('h4','','Просмотр черновика'),el('p','muted','Это оценка видео для дальнейшей работы. Она не создаёт план Hub и не разрешает публикацию.'));
    const latest=card.editorial_reviews?.[0];if(latest)r.append(el('div','aw-status',(latest.decision==='draft_accepted'?'Черновик принят для дальнейшей работы.':'Запрошена правка.')+(latest.note?' '+latest.note:'')));
    const label=el('label','','Замечание к этой версии'),note=el('textarea','aw-note');note.maxLength=2000;note.value=notes.get(card.digest)||'';note.setAttribute('aria-label','Замечание к видеочерновику');note.oninput=()=>notes.set(card.digest,note.value);label.append(note);r.append(label);
    const actions=el('div','aw-buttons');const change=button('Вернуть на правку',()=>review(card,'changes_requested',notes.get(card.digest)||''));const accept=button('Принять черновик',()=>review(card,'draft_accepted',notes.get(card.digest)||''));
    change.disabled=accept.disabled=busy||card.state==='superseded';actions.append(change,accept);r.append(actions,el('p','aw-hash','Hub: не передан · разрешение публикации: отсутствует'));d.append(r);return d;
  }
  function render() {
    page.querySelectorAll('video').forEach(v=>v.pause());page.replaceChildren();
    const header=el('div','aw-head'),intro=el('div');intro.append(el('div','ey','LAZY DISTRIBUTION / ПОДГОТОВКА'),el('h2','aw-title','Черновики из OpenReel'));header.append(intro,button('Обновить черновики',refresh));page.append(header);
    page.append(el('div','notice','Локальная библиотека на этом Mac. Видео и замечания реальные; это подготовка материала, а не очередь публикаций Hub. При выключенном Mac локальное превью недоступно.'));
    if(error)page.append(el('p','aw-error',error));
    const layout=el('div','aw-layout'),list=el('div','aw-list');
    for(const card of state.stories){const b=button('',()=>{selected=card.artifact_job_id;render();},'aw-card');b.setAttribute('aria-pressed',String(selected===card.artifact_job_id));const decision=card.editorial_reviews?.[0]?.decision;const status=card.state==='superseded'?'Предыдущая версия':decision==='changes_requested'?'Нужна правка':decision==='draft_accepted'?'Принят для дальнейшей работы':'Ожидает просмотра';b.append(el('strong','',card.title),el('small','',`Версия ${card.revision} · ${Math.round(card.artifact.duration)} с`),el('small','',status));list.append(b);}
    layout.append(list);const card=state.stories.find(s=>s.artifact_job_id===selected);layout.append(card?detail(card):el('div','aw-detail','Готовых черновиков пока нет. Соберите историю в OpenReel.'));page.append(layout);
    const jobs=el('div','aw-jobs');jobs.append(el('h4','','Последние задания'));for(const job of state.jobs.slice(0,6))jobs.append(el('div','',`${job.phase} · ${Math.round(job.progress*100)}%${job.error?' · '+job.error:''}`));page.append(jobs);
  }
  nav.onclick=()=>{if(typeof go==='function')go('astel-preparation');void refresh();};
  nav.click();
  // Refresh preserves ongoing video playback and draft remarks.
  setInterval(()=>{if(!document.hidden&&page.classList.contains('active')&&!busy&&!Array.from(page.querySelectorAll('video')).some(v=>!v.paused)&&!notes.size)void refresh();},60000);
})();
