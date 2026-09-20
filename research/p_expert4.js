(async () => {
  const out = { steps: [] };
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 70);

  await closeOverlays(3);
  await openNewTask();
  await sleep(1200);
  const entry = Array.from(document.querySelectorAll('button.conversation-list-tab-button'))
    .find(b => T(b).indexOf('专家') !== -1);
  realClick(entry);
  await sleep(1500);
  for (let i = 0; i < 20; i++) { if (document.querySelector('.ec-expert-card')) break; await sleep(900); }

  // 1) ec-list-tabs 明细
  out.listTabs = Array.from(document.querySelectorAll('.ec-list-tab'))
    .map(e => ({ t: T(e), cls: e.className.toString().slice(0, 70) }));
  out.listActions = Array.from(document.querySelectorAll('.ec-list-actions *'))
    .filter(isVisible).map(e => ({ t: T(e), cls: e.className.toString().slice(0, 60) }))
    .filter(x => x.t).slice(0, 20);

  // 2) 分类 tab 明细
  out.catTabs = Array.from(document.querySelectorAll('.ec-category-tab'))
    .map(e => ({ t: T(e), cls: e.className.toString().slice(0, 70) }));

  // 3) 特色场景（可能是"专家团"）
  out.scenes = Array.from(document.querySelectorAll('.ec-featured-scene-card'))
    .map(e => {
      const nm = e.querySelector('.ec-featured-scene-name');
      const exps = Array.from(e.querySelectorAll('.ec-featured-scene-expert-name')).map(x => T(x));
      const btn = Array.from(e.querySelectorAll('button')).map(b => T(b));
      return { name: nm ? T(nm) : T(e).slice(0, 30), experts: exps, buttons: btn };
    });

  // 4) 逐个点分类 tab，收集专家名（找"轻量云"）
  out.byCat = {};
  const cats = Array.from(document.querySelectorAll('.ec-category-tab'));
  for (let i = 0; i < cats.length && i < 12; i++) {
    const c = cats[i];
    const cn = T(c);
    realClick(c);
    await sleep(1800);
    const names = Array.from(document.querySelectorAll('.ec-expert-card'))
      .map(x => T(x).slice(0, 40));
    out.byCat[cn] = names.slice(0, 30);
    if (out.byCat[cn].some(n => /轻量云/.test(n))) out.lighthouseCat = cn;
  }
  return out;
})()
