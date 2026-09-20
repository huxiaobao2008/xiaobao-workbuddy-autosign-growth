(async () => {
  const out = {};
  const vis = el => { const r = el.getBoundingClientRect(); return r.width > 8 && r.height > 8; };
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const want = '和平精英';

  await closeOverlays();
  await openNewTask();
  await sleep(1200);
  realClick(document.querySelector('.user-menu-trigger')); await sleep(1400);
  realClick(document.querySelector('.user-menu-item--appearance')); await sleep(2500);

  const nameEls = Array.from(document.querySelectorAll('.appearance-card__name'));
  out.names = nameEls.map(e => T(e));
  const target = nameEls.find(e => T(e).indexOf(want) !== -1);
  if (!target) return Object.assign(out, { err: '找不到主题 ' + want });

  // 往上找可点的卡片
  let clickTarget = target;
  for (let i = 0; i < 4; i++) {
    const p = clickTarget.parentElement;
    if (!p || !/appearance/.test(p.className.toString())) break;
    clickTarget = p;
  }
  out.clickTargetCls = clickTarget.className.toString().slice(0, 90);
  realClick(clickTarget);
  await sleep(3000);
  out.selected = Array.from(document.querySelectorAll('.appearance-card--selected'))
    .map(c => T(c.querySelector('.appearance-card__name') || c));
  out.bodyCls = document.body.className.slice(0, 120);
  return out;
})()
