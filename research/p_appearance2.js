(async () => {
  const out = {};
  const vis = el => { const r = el.getBoundingClientRect(); return r.width > 8 && r.height > 8; };
  const T = el => (el.innerText || el.getAttribute('title') || '').replace(/\s+/g, ' ').trim().slice(0, 50);

  await closeOverlays();
  await openNewTask();
  await sleep(1200);

  const um = document.querySelector('.user-menu-trigger');
  realClick(um); await sleep(1400);
  const item = document.querySelector('.user-menu-item--appearance');
  out.found = !!item;
  if (!item) return out;
  realClick(item);
  await sleep(2500);

  out.panelCls = Array.from(new Set(Array.from(document.querySelectorAll('*'))
    .map(e => e.className && e.className.toString()).filter(Boolean)
    .flatMap(c => c.split(/\s+/)).filter(c => /appearance|theme|skin/i.test(c)))).slice(0, 40);
  out.labels = Array.from(document.querySelectorAll('button, [role=button], [class*=card], [class*=item], [class*=option], [class*=theme]'))
    .filter(vis).map(e => T(e)).filter(t => t).slice(0, 60);
  out.themes = Array.from(document.querySelectorAll('[class*=theme], [class*=appearance]'))
    .filter(vis).map(e => ({ t: T(e).slice(0, 30), cls: e.className.toString().slice(0, 80) })).slice(0, 40);
  out.hasHp = !!Array.from(document.querySelectorAll('*')).find(e => vis(e) && T(e).indexOf('和平精英') !== -1);
  return out;
})()
