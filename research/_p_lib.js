(async () => {
  closeOverlays(3);
  await sleep(600);
  if (!document.querySelector('.conversation-list-tab-button')) return { err: 'no sidebar' };
  clickSidebar('资料库');
  await sleep(3500);
  const vis = el => { const r = el.getBoundingClientRect(); return r.width > 8 && r.height > 8; };
  // 主内容区
  const main = document.querySelector('.main-content') || document.body;
  const rect = e => { const r = e.getBoundingClientRect();
    return [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)]; };
  return {
    txt: (main.innerText || '').replace(/\s+/g, ' ').slice(0, 1200),
    buttons: Array.from(document.querySelectorAll('button')).filter(vis)
      .map(b => ({ t: (b.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 24),
                   cls: String(b.className).slice(0, 70), r: rect(b) }))
      .filter(b => b.t).slice(0, 40),
    clickables: Array.from(document.querySelectorAll('a,[class*=item],[class*=node],[class*=card],[class*=doc]'))
      .filter(vis).filter(e => (e.innerText || '').trim() && e.children.length <= 4)
      .map(e => ({ tag: e.tagName, cls: String(e.className).slice(0, 70),
                   t: (e.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 50), r: rect(e) }))
      .slice(0, 40),
    url: location.href.slice(0, 200)
  };
})
