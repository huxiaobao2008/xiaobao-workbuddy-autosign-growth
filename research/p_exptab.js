(async () => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const vis = e => { const r = e.getBoundingClientRect(); return r.width > 4 && r.height > 4; };
  const click = (el) => { const r = el.getBoundingClientRect();
    for (const t of ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click']) {
      el.dispatchEvent(new (t.startsWith('pointer') ? PointerEvent : MouseEvent)(t,
        { bubbles: true, cancelable: true, view: window, clientX: r.x + r.width / 2, clientY: r.y + r.height / 2, button: 0, buttons: 1 }));
    } };
  window.__st = []; const st = s => window.__st.push(s);
  await openNewTask(); await sleep(1500);
  if (!document.querySelector('.ec-list-tab')) {
    const e = [...document.querySelectorAll('button.conversation-list-tab-button')].find(b => T(b).indexOf('专家') !== -1);
    if (e) { click(e); await sleep(2500); }
  }
  for (let i = 0; i < 20; i++) { if (document.querySelector('.ec-list-tab')) break; await sleep(700); }
  st('page');
  const tExp = [...document.querySelectorAll('.ec-list-tab')].find(x => T(x) === '专家');
  if (tExp && tExp.className.toString().indexOf('is-active') === -1) { click(tExp); await sleep(3500); }
  st('expertTab');
  const q = sel => document.querySelectorAll(sel).length;
  await sleep(1500);
  return {
    st: window.__st,
    activeTab: [...document.querySelectorAll('.ec-list-tab.is-active')].map(T),
    nCard: q('.ec-expert-card'), nGrid: q('.ec-expert-grid'), nGridItem: q('.ec-expert-grid-item'),
    nSummon: q('.ec-card-summon-btn'), nTeamsContainer: q('.teams-container'),
    nFeatured: q('.ec-featured-scene-overlay'),
    empty: !!document.querySelector('.cb-overview-empty'),
    catTabs: [...document.querySelectorAll('.ec-category-tab')].map(T).slice(0, 22),
    activeCat: [...document.querySelectorAll('.ec-category-tab.is-active')].map(T),
    cards: [...document.querySelectorAll('.ec-expert-card')].map(e => T(e).slice(0, 40)).slice(0, 6),
    featuredTxt: [...document.querySelectorAll('.ec-featured-scene-overlay')].map(e => T(e).slice(0, 60)).slice(0, 12)
  };
})
