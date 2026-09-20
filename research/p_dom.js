(async () => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const vis = e => { const r = e.getBoundingClientRect(); return r.width > 4 && r.height > 4; };
  const click = (el) => { const r = el.getBoundingClientRect();
    for (const t of ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click']) {
      el.dispatchEvent(new (t.startsWith('pointer') ? PointerEvent : MouseEvent)(t,
        { bubbles: true, cancelable: true, view: window, clientX: r.x + r.width / 2, clientY: r.y + r.height / 2, button: 0, buttons: 1 }));
    } };
  await openNewTask(); await sleep(1200);
  if (!document.querySelector('.ec-list-tab')) {
    const e = [...document.querySelectorAll('button.conversation-list-tab-button')].find(b => T(b).indexOf('专家') !== -1);
    if (e) { click(e); await sleep(2500); }
  }
  for (let i = 0; i < 20; i++) { if (document.querySelector('.ec-list-tab')) break; await sleep(700); }
  // 找到「暂无内容」的容器，往上爬，dump 每层的 class 与子元素 class 抽样
  const emp = document.querySelector('.cb-overview-empty');
  const chain = [];
  let cur = emp;
  for (let i = 0; i < 8 && cur; i++) {
    chain.push({ cls: (cur.className || '').toString().slice(0, 70),
                 kids: [...cur.children].map(c => (c.className || '').toString().slice(0, 50)).slice(0, 10),
                 txt: T(cur).slice(0, 50) });
    cur = cur.parentElement;
  }
  const q = sel => document.querySelectorAll(sel).length;
  return {
    chainToEmpty: chain,
    counts: {
      expertCard: q('.ec-expert-card'), grid: q('.ec-expert-grid'), gridItem: q('.ec-expert-grid-item'),
      summon: q('.ec-card-summon-btn'), teams: q('.teams-container'),
      cards: q('[class*=card]'), items: q('[class*=item]'),
      myExpert: q('[class*=my-expert]'), scene: q('[class*=scene]'),
      anyEc: q('[class^=ec-],[class*=" ec-"]')
    },
    ecClasses: [...new Set([...document.querySelectorAll('[class*=ec-]')]
      .flatMap(e => (e.className || '').toString().split(/\s+/))
      .filter(c => c.startsWith('ec-')))].slice(0, 40),
    emptyVisible: emp ? vis(emp) : null
  };
})
