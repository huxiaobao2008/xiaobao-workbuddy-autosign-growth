(() => {
  const page = document.querySelector('.automation-main-page');
  if (!page) return { err: 'not on automation page' };
  const vis = el => { const r = el.getBoundingClientRect(); return r.width > 8 && r.height > 8; };
  const rect = e => { const r = e.getBoundingClientRect();
    return [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)]; };
  // 找包含任务名的卡片
  const cards = Array.from(page.querySelectorAll('*')).filter(vis)
    .filter(e => (e.innerText || '').indexOf('自动刷任务测试') >= 0
              && e.querySelectorAll('*').length < 60)
    .sort((a, b) => a.querySelectorAll('*').length - b.querySelectorAll('*').length);
  const card = cards[0];
  const out = { found: !!card, text: page.innerText.replace(/\s+/g, ' ').slice(0, 400) };
  if (card) {
    out.cardCls = String(card.className).slice(0, 100);
    out.cardRect = rect(card);
    out.buttons = Array.from(card.querySelectorAll('button,[class*=icon],[class*=more],[class*=action]'))
      .filter(vis).map(b => ({ tag: b.tagName, cls: String(b.className).slice(0, 80),
                               t: (b.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 20), r: rect(b) }));
    out.html = card.outerHTML.slice(0, 1200);
  }
  out.topButtons = Array.from(page.querySelectorAll('button')).filter(vis)
    .map(b => (b.innerText || '').replace(/\s+/g, ' ').trim()).filter(Boolean).slice(0, 30);
  return out;
})
