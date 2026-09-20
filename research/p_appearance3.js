(async () => {
  const out = {};
  const vis = el => { const r = el.getBoundingClientRect(); return r.width > 8 && r.height > 8; };
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 40);

  await closeOverlays();
  await openNewTask();
  await sleep(1200);
  realClick(document.querySelector('.user-menu-trigger')); await sleep(1400);
  realClick(document.querySelector('.user-menu-item--appearance')); await sleep(2500);

  const names = () => Array.from(document.querySelectorAll('.appearance-card__name')).map(e => T(e));
  out.names = names();
  out.cards = Array.from(document.querySelectorAll('.appearance-card')).map(c => ({
    name: T(c.querySelector('.appearance-card__name') || c).slice(0, 20),
    cls: c.className.toString().slice(0, 90)
  }));

  const want = '和平精英';
  const card = Array.from(document.querySelectorAll('.appearance-card'))
    .find(c => T(c).indexOf(want) !== -1);
  out.found = !!card;
  if (!card) {
    // 试切「全部主题」筛选后再找
    const pill = Array.from(document.querySelectorAll('button, [role=button], div, span'))
      .filter(e => vis(e) && T(e) === '全部主题')
      .sort((a, b) => a.querySelectorAll('*').length - b.querySelectorAll('*').length)[0] || null;
    if (pill) { realClick(pill); await sleep(2000); out.namesAfterAll = names(); out.cardsAfterAll = Array.from(document.querySelectorAll('.appearance-card')).map(c => T(c.querySelector('.appearance-card__name') || c).slice(0, 20)); }
    return out;
  }
  realClick(card);
  await sleep(2500);
  out.after = { selected: Array.from(document.querySelectorAll('.appearance-card--selected')).map(c => T(c.querySelector('.appearance-card__name') || c)) };
  return out;
})()
