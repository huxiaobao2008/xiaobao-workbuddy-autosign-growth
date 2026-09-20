(async () => {
  const out = {};
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const want = '和平精英';

  await closeOverlays();
  await openNewTask();
  await sleep(1200);
  realClick(document.querySelector('.user-menu-trigger')); await sleep(1400);
  realClick(document.querySelector('.user-menu-item--appearance')); await sleep(2500);

  const cells = Array.from(document.querySelectorAll('.appearance-card-cell'));
  const cell = cells.find(c => T(c).indexOf(want) !== -1);
  if (!cell) return { err: '找不到 ' + want, cells: cells.map(c => T(c)) };
  const btn = cell.querySelector('button.appearance-card');
  out.before = { pressed: btn.getAttribute('aria-pressed'), cls: btn.className.toString().slice(0, 70) };
  realClick(btn);
  await sleep(3500);
  out.pressed = btn.getAttribute('aria-pressed');
  out.selected = Array.from(document.querySelectorAll('.appearance-card-cell'))
    .filter(c => { const b = c.querySelector('button.appearance-card'); return b && b.getAttribute('aria-pressed') === 'true'; })
    .map(c => T(c));
  out.bodyCls = document.body.className.slice(0, 100);
  // 关掉设置弹窗
  out.closed = (await closeOverlays()).closed;
  return out;
})()
