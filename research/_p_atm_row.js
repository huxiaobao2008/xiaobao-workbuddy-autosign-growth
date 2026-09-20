(() => {
  const name = document.querySelector('.atm-row-name');
  if (!name) return { err: 'no atm-row-name' };
  const rect = e => { const r = e.getBoundingClientRect();
    return [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)]; };
  const vis = el => { const r = el.getBoundingClientRect(); return r.width > 8 && r.height > 8; };
  // 向上找行容器
  let row = name;
  for (let i = 0; i < 6 && row.parentElement; i++) {
    row = row.parentElement;
    if (/atm-row($|\s)|atm-row\b|atm-list-item/.test(String(row.className))) break;
  }
  return {
    rowCls: String(row.className).slice(0, 100),
    rowHtml: row.outerHTML.slice(0, 1400),
    buttons: Array.from(row.querySelectorAll('button,[class*=icon],[class*=more],[class*=action],[class*=switch]'))
      .map(b => ({ tag: b.tagName, cls: String(b.className).slice(0, 80), vis: vis(b),
                   t: (b.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 20), r: rect(b) }))
  };
})
