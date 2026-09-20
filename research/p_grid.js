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
  const g = document.querySelector('.ec-expert-grid');
  const gc = document.querySelector('.ec-grid-content');
  const sc = document.querySelector('.ec-main-scroll');
  const cnt = document.querySelector('.ec-expert-count');
  return {
    gridHTMLlen: g ? g.innerHTML.length : -1,
    gridChildTags: g ? [...g.children].map(c => c.tagName + '.' + (c.className || '').toString().slice(0, 40)).slice(0, 8) : null,
    gridContentHTMLlen: gc ? gc.innerHTML.length : -1,
    gridContentKids: gc ? [...gc.children].map(c => c.tagName + '.' + (c.className || '').toString().slice(0, 40)).slice(0, 8) : null,
    countTxt: cnt ? T(cnt) : null,
    scrollTop: sc ? sc.scrollTop : null,
    scrollH: sc ? sc.scrollHeight : null,
    clientH: sc ? sc.clientHeight : null,
    spinner: document.querySelectorAll('[class*=loading],[class*=spinner],[class*=skeleton]').length,
    gridContentHTML: gc ? gc.innerHTML.slice(0, 600) : (g ? g.innerHTML.slice(0, 600) : null)
  };
})
