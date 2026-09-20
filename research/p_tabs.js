(async () => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const vis = e => { const r = e.getBoundingClientRect(); return r.width > 4 && r.height > 4; };
  const click = (el) => { const r = el.getBoundingClientRect();
    for (const t of ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click']) {
      el.dispatchEvent(new (t.startsWith('pointer') ? PointerEvent : MouseEvent)(t,
        { bubbles: true, cancelable: true, view: window, clientX: r.x + r.width / 2, clientY: r.y + r.height / 2, button: 0, buttons: 1 }));
    } };
  window.__st = [];
  const st = s => window.__st.push(s);
  const snap = () => ({
    tab: [...document.querySelectorAll('.ec-list-tab.is-active')].map(T)[0] || null,
    cards: document.querySelectorAll('.ec-expert-card').length,
    empty: !!document.querySelector('.cb-overview-empty'),
    cat: [...document.querySelectorAll('.ec-category-tab.is-active')].map(T)[0] || null,
    firstCards: [...document.querySelectorAll('.ec-expert-card')].map(T).slice(0, 3)
  });
  const out = {};
  await openNewTask(); await sleep(1500); st('newTask');
  if (!document.querySelector('.ec-list-tab')) {
    const e = [...document.querySelectorAll('button.conversation-list-tab-button')].find(b => T(b).indexOf('专家') !== -1);
    if (e) { click(e); st('clickSide'); await sleep(2500); }
  }
  for (let i = 0; i < 20; i++) { if (document.querySelector('.ec-list-tab')) break; await sleep(700); }
  st('page');
  out.initial = snap();

  // A. 点「专家」tab
  const tExp = [...document.querySelectorAll('.ec-list-tab')].find(x => T(x) === '专家');
  if (tExp) { click(tExp); st('clickExpertTab'); await sleep(3000); }
  out.afterExpertTab = snap();

  // B. 点「全部」分类
  const cAll = [...document.querySelectorAll('.ec-category-tab')].filter(vis).find(x => T(x) === '全部');
  if (cAll) { click(cAll); st('clickCatAll'); await sleep(3000); }
  out.afterCatAll = snap();

  // C. 点另一个分类（内容创作）
  const cCat = [...document.querySelectorAll('.ec-category-tab')].filter(vis).find(x => T(x) === '内容创作');
  if (cCat) { click(cCat); st('clickCatContent'); await sleep(3500); }
  out.afterCatContent = snap();

  // D. 再点「专家团」tab
  const tTeam = [...document.querySelectorAll('.ec-list-tab')].find(x => T(x) === '专家团');
  if (tTeam) { click(tTeam); st('clickTeamTab'); await sleep(3500); }
  out.afterTeamTab = snap();
  st('done');
  out.st = window.__st;
  return out;
})
