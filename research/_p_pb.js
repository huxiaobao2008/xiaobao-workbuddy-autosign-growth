(async () => {
  closeOverlays(2);
  await sleep(500);
  const btn = Array.from(document.querySelectorAll('.conversation-list-tab-button'))
    .find(e => /灵感/.test(e.innerText || ''));
  if (!btn) return { err: '找不到侧边栏「灵感」' };
  realClick(btn);
  await sleep(3000);
  const vis = el => { const r = el.getBoundingClientRect(); return r.width > 8 && r.height > 8; };
  const rect = e => { const r = e.getBoundingClientRect();
    return [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)]; };
  // 主区（排除侧边栏）
  const side = document.querySelector('.conversation-list');
  const main = document.querySelector('.main-content') || document.body;
  return {
    tabActive: Array.from(document.querySelectorAll('.conversation-list-tab-button.active'))
      .map(e => (e.innerText || '').replace(/\s+/g, ' ').trim()),
    mainTxt: (main.innerText || '').replace(/\s+/g, ' ').slice(0, 1200),
    cards: Array.from(document.querySelectorAll('[class*=card],[class*=item],[class*=case],[class*=inspir]'))
      .filter(vis).filter(e => (e.innerText || '').trim() && e.children.length <= 5)
      .map(e => ({ cls: String(e.className).slice(0, 70),
                   t: (e.innerText || '').replace(/\s+/g, ' ').slice(0, 60), r: rect(e) }))
      .slice(0, 30),
    buttons: Array.from(main.querySelectorAll('button')).filter(vis)
      .map(b => ({ t: (b.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 20), r: rect(b) }))
      .filter(b => b.t).slice(0, 25)
  };
})
