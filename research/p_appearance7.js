(async () => {
  const out = {};
  const vis = el => { const r = el.getBoundingClientRect(); return r.width > 8 && r.height > 8; };
  const T = el => (el.innerText || el.getAttribute('title') || el.getAttribute('aria-label') || '')
      .replace(/\s+/g, ' ').trim().slice(0, 40);
  const want = '和平精英';

  await closeOverlays();
  await openNewTask();
  await sleep(1200);
  realClick(document.querySelector('.user-menu-trigger')); await sleep(1400);
  realClick(document.querySelector('.user-menu-item--appearance')); await sleep(2500);

  const panel = document.querySelector('.appearance-panel') || document.body;
  out.buttons = Array.from(panel.querySelectorAll('button')).filter(vis)
    .map(b => ({ t: T(b), cls: b.className.toString().slice(0, 80) }));
  out.allText = (panel.innerText || '').replace(/\s+/g, ' ').slice(0, 600);

  const cell = Array.from(document.querySelectorAll('.appearance-card-cell')).find(c => T(c).indexOf(want) !== -1);
  if (cell) {
    const btn = cell.querySelector('button.appearance-card');
    realClick(btn);
    await sleep(3500);
    out.afterClick = {
      pressed: btn.getAttribute('aria-pressed'),
      panelText: (document.querySelector('.appearance-panel') || {}).innerText ?
                 document.querySelector('.appearance-panel').innerText.replace(/\s+/g, ' ').slice(0, 400) : null,
      barButtons: Array.from(document.querySelectorAll('.appearance-preview *, .appearance-panel button'))
        .filter(vis).map(b => ({ t: T(b), cls: b.className.toString().slice(0, 70) })).slice(0, 20),
      bodySkin: Array.from(document.querySelectorAll('[class*=skin], [class*=theme-]'))
        .map(e => e.className.toString().slice(0, 60)).slice(0, 10)
    };
  }
  out.closed = (await closeOverlays()).closed;
  return out;
})()
