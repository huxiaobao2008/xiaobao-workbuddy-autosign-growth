(async () => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const vis = e => { const r = e.getBoundingClientRect(); return r.width > 4 && r.height > 4; };
  const click = (el) => { const r = el.getBoundingClientRect();
    for (const t of ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click']) {
      el.dispatchEvent(new (t.startsWith('pointer') ? PointerEvent : MouseEvent)(t,
        { bubbles: true, cancelable: true, view: window, clientX: r.x + r.width / 2, clientY: r.y + r.height / 2, button: 0, buttons: 1 }));
    } };
  const T0 = Date.now();
  window.__t = []; const st = s => window.__t.push(s + '=' + (Date.now() - T0));
  st('start');
  for (let i = 1; i <= 5; i++) { await sleep(700); st('sleep' + i); }
  st('sleepsDone');
  await openNewTask(); st('newTask');
  if (!document.querySelector('.ec-list-tab')) {
    const e = [...document.querySelectorAll('button.conversation-list-tab-button')].find(b => T(b).indexOf('专家') !== -1);
    if (e) { click(e); st('clickSide'); await sleep(2500); }
  }
  st('afterSide');
  for (let i = 0; i < 20; i++) { if (document.querySelector('.ec-list-tab')) break; await sleep(700); }
  st('page');
  const el = [...document.querySelectorAll('.ec-category-tab')].filter(vis).find(x => T(x) === '内容创作');
  if (el) { click(el); st('clickCat'); await sleep(3000); }
  st('afterCat');
  const g = document.querySelector('.ec-expert-grid');
  return { t: window.__t, cards: document.querySelectorAll('.ec-expert-card').length,
           items: document.querySelectorAll('.ec-expert-grid-item').length,
           gridLen: g ? g.innerHTML.length : -1,
           count: (document.querySelector('.ec-expert-count') || {}).innerText || null };
})
