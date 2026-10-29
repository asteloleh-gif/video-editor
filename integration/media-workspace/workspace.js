/* Local preparation and simulation handoff for the owner-supplied Canvas.
 * The Hub remains the owner of delivery plans and publication approval.
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
  const old = document.querySelector('[data-page="distribution"]'); if (old) {old.textContent = '▷ Очередь Hub';const show=old.onclick;old.onclick=()=>{show?.();window.AstelCanvasDistribution?.connect();};}
  let state = {stories: [], jobs: [], handoffs: []}, selected = null, busy = false, error = '', lastRefresh = 0;
  const notes = new Map(); const pendingKey = 'astel-canvas-editorial-pending-v1';
  const drafts = new Map(); const handoffKey = 'astel-canvas-handoff-pending-v1';
  try {const saved=JSON.parse(localStorage.getItem(pendingKey)||'null');if(saved&&typeof saved.story_id==='string'&&typeof saved.digest==='string'&&typeof saved.note==='string'&&saved.note.length<=2000){selected=saved.story_id;notes.set(saved.digest,saved.note);}} catch {localStorage.removeItem(pendingKey);}
  const el = (tag, cls, text) => {const n=document.createElement(tag); if(cls)n.className=cls; if(text!==undefined)n.textContent=text; return n;};
  const button = (text, action, cls='action') => {const n=el('button',cls,text);n.type='button';n.onclick=action;return n;};
  async function api(path, options) {
    const response = await fetch(path,{credentials:'same-origin',cache:'no-store',redirect:'error',...options});
    const value = await response.json();
    if (!response.ok) throw Error(value.error || 'Локальная библиотека недоступна. Обновите страницу.');
    return value;
  }
  window.AstelMacMedia=Object.create(null);window.AstelMacTitles=Object.create(null);
  window.AstelMacHubReader=Object.freeze({
    async list(){const seen=new Set(),rows=new Map();let cursor=null;for(let page=0;page<40;page++){const result=window.AstelDistributionCore.inbox(await api('/api/astel-workspace/hub/inbox'+(cursor?'?cursor='+encodeURIComponent(cursor):'')),'copilot');for(const item of result.items)rows.set(item.id,item);if(!result.nextCursor)return [...rows.values()];if(seen.has(result.nextCursor))throw Error('PAGINATION_LOOP');seen.add(result.nextCursor);cursor=result.nextCursor;}throw Error('INBOX_TOO_LARGE');},
    async plan(id){if(!/^[a-f0-9]{64}$/.test(id))throw Error('INVALID_PLAN_ID');const p=window.AstelDistributionCore.normalize(await api('/api/astel-workspace/hub/plans/'+id),'copilot');if(p.id!==id||!p.full)throw Error('PLAN_IDENTITY_MISMATCH');return p;},
    async metrics(){return window.AstelDistributionCore.metrics(await api('/api/astel-workspace/hub/metrics'));}
  });
  async function refresh() {
    try {state = await api('/api/astel-workspace');lastRefresh=Date.now();error='';for(const card of state.stories){const hash='sha256:'+card.artifact.sha256;window.AstelMacMedia[hash]='/api/astel-workspace/stories/'+encodeURIComponent(card.artifact_job_id)+'/video.mp4';window.AstelMacTitles[hash]=card.title;}if(!state.stories.some(s=>s.artifact_job_id===selected))selected=state.stories[0]?.artifact_job_id||null;render();}
    catch (e) {error=e.message;render();}
  }
  async function sendHandoff(card, draft) {
    if(busy)return;busy=true;error='';
    try {
      const payload={story_id:card.artifact_job_id,digest:card.digest,account_key:draft.account_key,text:draft.text,scheduled_at:new Date(draft.when).toISOString()};
      const saved=localStorage.getItem(handoffKey);const request=saved?JSON.parse(saved):{request_id:crypto.randomUUID(),...payload};
      if(saved&&Object.keys(payload).some(k=>request[k]!==payload[k]))throw Error('Предыдущая передача ещё не подтверждена. Повторите её прежние настройки.');
      localStorage.setItem(handoffKey,JSON.stringify(request));
      await api('/api/astel-workspace/hub/submit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(request)});
      localStorage.removeItem(handoffKey);await refresh();
    }catch(e){error=e.message;if(/rejected/i.test(error))localStorage.removeItem(handoffKey);}finally{busy=false;render();}
  }
  async function handoffAction(action, jobId) {
    if(busy)return;busy=true;error='';
    try{await api('/api/astel-workspace/hub/'+action,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({job_id:jobId})});await refresh();}
    catch(e){error=e.message;}finally{busy=false;render();}
  }
  async function mediaAccess(item){
    if(busy)return;busy=true;error='';
    try{await api('/api/astel-workspace/hub/media-access',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({job_id:item.job_id,story_digest:item.story_digest,artifact_sha256:item.artifact_sha256,consent:'anyone-with-link-readonly-final-mp4'})});await refresh();}
    catch(e){error=e.message;}finally{busy=false;render();}
  }
  async function reconnectDrive(){
    if(busy)return;busy=true;error='';
    try{await api('/api/astel-workspace/drive/reauthorize',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});await refresh();}
    catch(e){error=e.message;}finally{busy=false;render();}
  }
  function handoffPanel(card) {
    const panel=el('section','aw-review');panel.append(el('h4','','Передача в Lazy Distribution Hub'),el('p','muted','Создаём только тестовый черновик simulation. Эта кнопка не согласует материал, не запускает расписание и не публикует пост. MP4 сначала загружается в приватную папку доставки.'));
    const linked=(state.handoffs||[]).filter(h=>h.story_id===card.artifact_job_id&&h.story_digest===card.digest);
    for(const item of linked){panel.append(el('div','aw-status',item.submitted?`Hub подтвердил ${item.hub_state||'черновик'} · версия доставки ${item.revision}`:'Передача ожидает подтверждения'),el('p','aw-hash','Plan ID: '+item.expected_plan_id),el('p','muted',item.media_ready?'Копия MP4 доступна для чтения по ссылке.':'Копия MP4 приватная. Для серверного чтения нужен отдельный доступ к этому файлу; публикация остаётся выключена.'));panel.append(button('Проверить статус в Hub',()=>handoffAction('status',item.job_id)));}
    for(const item of linked.filter(i=>i.submitted&&i.media_ready))panel.append(button('Проверить весь MP4 на сервере',()=>workspaceAction('hub/preflight',{job_id:item.job_id})),button('Передать на согласование в Canvas',()=>workspaceAction('hub/request-review',{job_id:item.job_id})));
    for(const item of linked.filter(i=>i.server_preflight?.state==='verified'))panel.append(el('p','aw-status',`Сервер подтвердил весь MP4 · ${item.server_preflight.bytes.toLocaleString()} байт · SHA-256 совпадает`));
    for(const item of linked.filter(i=>i.submitted&&!i.media_ready)){const consent=el('input');consent.type='checkbox';const label=el('label','muted');label.append(consent,document.createTextNode(' Разрешаю любому, у кого есть ссылка, читать только эту готовую копию MP4 с моим синтезированным голосом, чтобы сервер Hub мог её получить. Папка и исходники остаются приватными.'));const grant=button('Разрешить чтение этой копии MP4',()=>mediaAccess(item));grant.disabled=true;consent.onchange=()=>{grant.disabled=busy||!consent.checked;};panel.append(el('p','aw-hash','Разрешение для SHA-256: '+item.artifact_sha256),label,grant);}
    const jobs=state.jobs.filter(j=>j.kind==='handoff'&&j.story_id===card.artifact_job_id);for(const job of jobs.slice(0,3)){panel.append(el('p',job.error?'aw-error':'muted',job.phase+' · '+Math.round(job.progress*100)+'%'+(job.error?' · '+job.error:'')));if(job.status==='failed')panel.append(button('Продолжить передачу',()=>handoffAction('retry',job.id)));}
    if(jobs.some(j=>j.status==='failed')){const auth=state.drive_authorization||{};if(auth.state==='authorizing'&&/^http:\/\/127\.0\.0\.1:[0-9]{1,5}\/authorize$/.test(auth.url||'')){const a=el('a','linkbtn','Открыть повторный вход Google Drive');a.href=auth.url;a.target='_blank';a.rel='noopener noreferrer';panel.append(a,el('p','muted','Вход использует прежнее подключение drive.file. Завершите его в Google, затем нажмите «Продолжить передачу».'));}else{panel.append(button('Повторно войти в Google Drive',reconnectDrive));if(auth.state==='completed')panel.append(el('p','aw-status','Вход завершён. Нажмите «Продолжить передачу».'));}}
    let draft=drafts.get(card.digest);
    if(!draft){const future=new Date(Date.now()+86400000);future.setMinutes(future.getMinutes()-future.getTimezoneOffset());draft={account_key:card.voice.profile==='oleh-en'?'leoakastel:instagram':'astel.u:instagram',text:card.title,when:future.toISOString().slice(0,16)};try{const p=JSON.parse(localStorage.getItem(handoffKey)||'null');if(p&&p.digest===card.digest){const date=new Date(p.scheduled_at);date.setMinutes(date.getMinutes()-date.getTimezoneOffset());draft={account_key:p.account_key,text:p.text,when:date.toISOString().slice(0,16)};}}catch{}drafts.set(card.digest,draft);}
    const accountLabel=el('label','','Аккаунт тестового черновика'),account=el('select','aw-field');account.setAttribute('aria-label','Аккаунт Hub');for(const key of ['astel.u:instagram','leoakastel:instagram','astel.us:instagram']){const option=el('option','',key);option.value=key;account.append(option);}account.value=draft.account_key;account.onchange=()=>{draft.account_key=account.value;};accountLabel.append(account);
    const textLabel=el('label','','Подпись черновика'),text=el('textarea','aw-note');text.maxLength=2200;text.value=draft.text;text.setAttribute('aria-label','Подпись для Hub');text.oninput=()=>{draft.text=text.value;};textLabel.append(text);
    const timeLabel=el('label','','Время тестового слота (часовой пояс этого браузера)'),when=el('input','aw-field');when.type='datetime-local';when.value=draft.when;when.setAttribute('aria-label','Время тестового слота Hub');when.onchange=()=>{draft.when=when.value;};timeLabel.append(when);
    const send=button('Передать тестовый черновик в Hub',()=>sendHandoff(card,draft));send.disabled=busy||card.state==='superseded'||jobs.some(j=>!['ready','failed','cancelled'].includes(j.status));
    panel.append(accountLabel,textLabel,timeLabel,send);return panel;
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
  async function workspaceAction(path, body){
    if(busy)return;busy=true;error='';
    try{await api('/api/astel-workspace/'+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});await refresh();}
    catch(e){error=e.message;}finally{busy=false;render();}
  }
  function field(labelText, input){const label=el('label','',labelText);input.classList.add('aw-field');label.append(input);return label;}
  function select(values){const input=el('select');for(const [value,title] of values){const option=el('option','',title);option.value=value;input.append(option);}return input;}
  function discoveryPanel(){
    const panel=el('details','aw-review');panel.append(el('summary','','Темы и библиотека материалов'));
    panel.append(el('p','muted','Поиск работает на этом Mac в фоне. YouTube сохраняет ссылки для изучения; доступные файлы Commons добавляются в библиотеку по вашему выбору.'));
    const query=el('input');query.maxLength=200;const interval=select([['60','Раз в час'],['360','Раз в 6 часов'],['1440','Раз в сутки']]);
    panel.append(field('Тема',query),field('Частота',interval),button('Следить за темой',()=>workspaceAction('watch',{id:crypto.randomUUID(),query:query.value,providers:['commons','youtube'],interval_minutes:Number(interval.value),enabled:true})));
    for(const watch of state.discovery?.watches||[]){const row=el('div','aw-source');row.append(el('strong','',watch.query),el('p','muted',`${watch.enabled?'Включён':'Остановлен'} · каждые ${watch.interval_minutes} мин`),button(watch.enabled?'Остановить поиск':'Возобновить поиск',()=>workspaceAction('watch',{id:watch.id,query:watch.query,providers:watch.providers,interval_minutes:watch.interval_minutes,enabled:!watch.enabled})));panel.append(row);}
    for(const item of (state.discovery?.ranked||[]).slice(0,20)){const row=el('div','aw-source');row.append(el('strong','',item.title),el('p','muted',item.views_per_hour===null?'Пока недостаточно замеров роста':`${Math.round(item.views_per_hour)} просмотров/час · ${item.growth_evidence.hours.toFixed(1)} ч между замерами`));const url=window.AstelDistributionCore?.publicUrl(item.url);if(url){const a=el('a','','Исходник');a.href=url;a.target='_blank';a.rel='noopener noreferrer';row.append(a);}if(item.downloadable)row.append(button('Добавить файл в библиотеку',()=>workspaceAction('jobs',{id:crypto.randomUUID(),kind:'acquire',payload:{candidate_id:item.id}})));panel.append(row);}
    return panel;
  }
  function correctionPanel(card){
    const panel=el('details','aw-review');panel.append(el('summary','','Правка по таймкоду и настройка стиля'));
    const category=select([['editing','Монтаж'],['voice','Голос'],['captions','Субтитры'],['sources','Материал'],['motion','Моушн']]);const start=el('input'),end=el('input');for(const input of [start,end]){input.type='number';input.min='0';input.max=String(card.artifact.duration);input.step='.1';}start.value='0';end.value=String(Math.min(5,card.artifact.duration));const note=el('textarea');note.maxLength=2000;
    const motion=select([['gentle','Мягкое движение фото'],['static','Статичные фото']]),titles=select([['scene','Заголовок каждой сцены'],['none','Без заголовков сцен']]),size=el('input');size.type='number';size.min='44';size.max='76';size.value=String(state.styles?.active?.settings?.caption_size||52);
    panel.append(field('Что исправить',category),field('Секунды от',start),field('До',end),field('Замечание',note),field('Движение',motion),field('Заголовки',titles),field('Размер субтитров',size),button('Запомнить правку этой версии',()=>workspaceAction('correction',{id:crypto.randomUUID(),story_id:card.artifact_job_id,digest:card.digest,category:category.value,start:Number(start.value),end:Number(end.value),note:note.value,suggestion:{image_motion:motion.value,title_mode:titles.value,caption_size:Number(size.value)}})));
    for(const item of (state.styles?.corrections||[]).filter(x=>x.story_id===card.artifact_job_id&&x.digest===card.digest))panel.append(el('p','muted',`${item.start}–${item.end} с · ${item.category}: ${item.note}`));
    panel.append(el('p','muted','Замечания к голосу сохраняются для доработки. Эти настройки меняют только движение фото, заголовки и размер субтитров.'));
    return panel;
  }
  function stylePanel(){
    const panel=el('details','aw-review');panel.append(el('summary','','Стиль следующих роликов'),el('p','muted','Сейчас: '+(state.styles?.active?.name||'Astel default')));
    const corrections=(state.styles?.corrections||[]).filter(x=>x.suggestion).slice(0,30),latest=corrections[0];
    if(latest)panel.append(button('Сохранить вариант из последней правки',()=>workspaceAction('style/propose',{id:crypto.randomUUID(),name:'Astel · '+new Date().toLocaleDateString(),correction_ids:[latest.id],settings:latest.suggestion})));
    for(const version of state.styles?.versions||[]){const row=el('div','aw-source');row.append(el('strong','',version.name),el('p','muted',JSON.stringify(version.settings)));if(version.digest===state.styles?.active?.digest)row.append(el('span','aw-status','Используется'));else row.append(button('Использовать для новых роликов',()=>workspaceAction('style/activate',{request_id:crypto.randomUUID(),id:version.id,digest:version.digest,expected_active_digest:state.styles?.active?.digest||null})));panel.append(row);}return panel;
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
    change.disabled=accept.disabled=busy||card.state==='superseded';actions.append(change,accept);r.append(actions,el('p','aw-hash','Редакторское решение не является разрешением на публикацию.'));d.append(r,correctionPanel(card),handoffPanel(card));return d;
  }
  function render() {
    page.querySelectorAll('video').forEach(v=>v.pause());page.replaceChildren();
    const header=el('div','aw-head'),intro=el('div');intro.append(el('div','ey','LAZY DISTRIBUTION / ПОДГОТОВКА'),el('h2','aw-title','Черновики из OpenReel'));header.append(intro,button('Обновить черновики',refresh));page.append(header);
    page.append(el('div','notice','Локальная библиотека на этом Mac. Видео и замечания реальные; это подготовка материала, а не очередь публикаций Hub. При выключенном Mac локальное превью недоступно.'));
    const runtime=state.runtime;if(runtime){page.append(el('p',runtime.healthy?'aw-status':'aw-error',(runtime.healthy?'Фоновая служба работает':'Фоновая служба требует проверки')+(Number.isFinite(runtime.unfinished)?' · в очереди '+runtime.unfinished:'')+(runtime.disk_free_bytes?' · свободно '+(runtime.disk_free_bytes/1024**3).toFixed(1)+' GiB':'')+(runtime.warnings?.length?' · '+runtime.warnings.join(', '):'')));}
    if(error)page.append(el('p','aw-error',error));
    page.append(discoveryPanel(),stylePanel());
    const layout=el('div','aw-layout'),list=el('div','aw-list');
    for(const card of state.stories){const b=button('',()=>{selected=card.artifact_job_id;render();},'aw-card');b.setAttribute('aria-pressed',String(selected===card.artifact_job_id));const decision=card.editorial_reviews?.[0]?.decision;const status=card.state==='superseded'?'Предыдущая версия':decision==='changes_requested'?'Нужна правка':decision==='draft_accepted'?'Принят для дальнейшей работы':'Ожидает просмотра';b.append(el('strong','',card.title),el('small','',`Версия ${card.revision} · ${Math.round(card.artifact.duration)} с`),el('small','',status));list.append(b);}
    layout.append(list);const card=state.stories.find(s=>s.artifact_job_id===selected);layout.append(card?detail(card):el('div','aw-detail','Готовых черновиков пока нет. Соберите историю в OpenReel.'));page.append(layout);
    const jobs=el('div','aw-jobs');jobs.append(el('h4','','Последние задания'));for(const job of state.jobs.slice(0,6))jobs.append(el('div','',`${job.phase} · ${Math.round(job.progress*100)}%${job.error?' · '+job.error:''}`));page.append(jobs);
  }
  nav.onclick=()=>{if(typeof go==='function')go('astel-preparation');void refresh();};
  nav.click();
  // Refresh preserves ongoing video playback and draft remarks.
  setInterval(()=>{const running=state.jobs.some(j=>j.kind==='handoff'&&!['ready','failed','cancelled'].includes(j.status));if(Date.now()-lastRefresh>=(running?1800:60000)&&!document.hidden&&page.classList.contains('active')&&!busy&&!Array.from(page.querySelectorAll('video')).some(v=>!v.paused)&&!page.contains(document.activeElement?.matches('textarea,input,select')?document.activeElement:null))void refresh();},2000);
})();
