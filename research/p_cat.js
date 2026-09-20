(async () => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const vis = e => { const r = e.getBoundingClientRect(); return r.width > 4 && r.height > 4; };
  const click = (el) => { const r = el.getBoundingClientRect();
    for (const t of ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click']) {
      el.dispatchEvent(new (t.startsWith('pointer') ? PointerEvent : MouseEvent)(t,
        { bubbles: true, cancelable: true, view: window, clientX: r.x + r.width / 2, clientY: r.y + r.height / 2, button: 0, buttons: 1 }));
    } };
  window.__st = []; const st = s => window.__st.push(s);
  const snap = (tag) => {
    const g = document.querySelector('.ec-expert-grid');
    const cnt = document.querySelector('.ec-expert-count');
    return { tag, count: cnt ? T(cnt) : null,
             items: document.querySelectorAll('.ec-expert-grid-item').length,
             cards: document.querySelectorAll('.ec-expert-card').length,
             summon: document.querySelectorAll('.ec-card-summon-btn').length,
             gridLen: g ? g.innerHTML.length : -1 };
  };
  await openNewTask(); await sleep(1200); st('newTask');
  if (!document.querySelector('.ec-list-tab')) {
    const e = [...document.querySelectorAll('button.conversation-list-tab-button')].find(b => T(b).indexOf('专家') !== -1);
    if (e) { click(e); st('clickSide'); await sleep(2500); }
  }
  for (let i = 0; i < 20; i++) { if (document.querySelector('.ec-list-tab')) break; await sleep(700); }
  st('page');
  const out = { base: snap('base'), steps: [] };
  for (const cat of ['全部', '内容创作', '腾讯专家', 'OPC·一人公司']) {
    const el = [...document.querySelectorAll('.ec-category-tab')].filter(vis).find(x => T(x) === cat);
    if (!el) { out.steps.push({ cat, err: 'notfound' }); continue; }
    click(el); st('cat:' + cat);
    await sleep(3000);
    out.steps.push(snap(cat));
  }
  // 再尝试滚动虚拟列表
  const sc = document.querySelector('.ec-main-scroll');
  if (sc) { sc.scrollTop = 200; await sleep(1200); sc.scrollTop = 0; await sleep(800); }
  out.afterScroll = snap('afterScroll');
  out.st = window.__st;
  return out;
})
