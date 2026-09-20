(async () => {
  const out = { tries: [] };
  const vis = el => { const r = el.getBoundingClientRect(); return r.width > 8 && r.height > 8; };
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 60);
  const edText = () => {
    const e = document.querySelector('[contenteditable=true]');
    return e ? (e.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 200) : null;
  };
  const clickExact = async (t) => {
    const el = Array.from(document.querySelectorAll('button, [role=button], div, span'))
      .filter(e => vis(e) && T(e) === t)
      .sort((a, b) => a.querySelectorAll('*').length - b.querySelectorAll('*').length)[0] || null;
    if (!el) return false;
    realClick(el);
    await sleep(2000);
    return true;
  };

  await closeOverlays();
  await openNewTask();
  await sleep(1500);
  out.scene = await setScene('设计创意');
  await sleep(1500);

  for (const cat of ['网站设计', '视觉海报', 'PPT设计']) {
    const hit = await clickExact(cat);
    const rec = { cat: cat, clicked: hit, ed: edText() };
    const labels = Array.from(document.querySelectorAll('button, [role=button], [class*=item], [class*=card]'))
      .filter(vis).map(e => T(e)).filter(t => t && t.length <= 30);
    rec.labels = Array.from(new Set(labels)).slice(0, 40);
    rec.cls = Array.from(new Set(Array.from(document.querySelectorAll('*'))
      .map(e => e.className && e.className.toString()).filter(Boolean)
      .flatMap(c => c.split(/\s+/)).filter(c => /canvas|design|artifact|preview|poster|iframe/i.test(c)))).slice(0, 30);
    out.tries.push(rec);
    await openNewTask();
    await sleep(1200);
    await setScene('设计创意');
    await sleep(1200);
  }
  return out;
})()
