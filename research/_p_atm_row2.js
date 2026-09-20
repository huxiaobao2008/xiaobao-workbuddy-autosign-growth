(() => {
  const name = document.querySelector('.atm-row-name');
  if (!name) return { err: 'no atm-row-name' };
  const chain = [];
  let e = name;
  for (let i = 0; i < 10 && e; i++) {
    chain.push({ tag: e.tagName, cls: String(e.className).slice(0, 110),
                 kids: e.querySelectorAll('*').length });
    e = e.parentElement;
  }
  // 找到行容器后列出所有后代 button
  const row = name.closest('[class*=atm-row]:not(.atm-row-main)')
           || name.closest('[class*=atm-item]') || name.closest('li');
  const rect = x => { const r = x.getBoundingClientRect();
    return [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)]; };
  const vis = el => { const r = el.getBoundingClientRect(); return r.width > 8 && r.height > 8; };
  return { chain: chain,
    rowCls: row ? String(row.className).slice(0, 110) : null,
    rowHtml: row ? row.outerHTML.slice(0, 2000) : null,
    rowButtons: row ? Array.from(row.querySelectorAll('button,[class*=icon],[class*=more],[class*=switch],[role=menuitem]'))
      .map(b => ({ tag: b.tagName, cls: String(b.className).slice(0, 80), vis: vis(b),
                   t: (b.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 20), r: rect(b) })) : null };
})
