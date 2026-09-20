(async () => {
  const out = {};
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  await closeOverlays();
  await openNewTask();
  await sleep(1200);
  realClick(document.querySelector('.user-menu-trigger')); await sleep(1400);
  realClick(document.querySelector('.user-menu-item--appearance')); await sleep(2500);

  const nameEls = Array.from(document.querySelectorAll('.appearance-card__name'));
  const target = nameEls.find(e => T(e).indexOf('和平精英') !== -1);
  if (!target) return { err: 'no target' };
  // 祖先链
  out.chain = [];
  let n = target;
  for (let i = 0; i < 8 && n; i++) {
    out.chain.push({ tag: n.tagName.toLowerCase(), cls: n.className.toString().slice(0, 80),
                     kids: n.children.length, txtLen: (n.innerText || '').length });
    n = n.parentElement;
  }
  out.targetHTML = target.outerHTML.slice(0, 400);
  out.parentHTML = target.parentElement ? target.parentElement.outerHTML.slice(0, 900) : null;
  const cell = target.closest('[class*=appearance-card-cell]');
  out.cellHTML = cell ? cell.outerHTML.slice(0, 1200) : null;
  out.gridChildren = Array.from((document.querySelector('.appearance-card-grid') || document.body).children)
    .slice(0, 3).map(c => ({ cls: c.className.toString().slice(0, 70), html: c.outerHTML.slice(0, 300) }));
  return out;
})()
