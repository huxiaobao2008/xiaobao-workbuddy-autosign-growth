(() => {
  const rows = Array.from(document.querySelectorAll('div.atm-row'));
  return rows.map(row => {
    const rect = x => { const r = x.getBoundingClientRect();
      return [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)]; };
    const vis = el => { const r = el.getBoundingClientRect(); return r.width > 4 && r.height > 4; };
    const name = row.querySelector('.atm-row-name');
    return {
      name: name ? name.innerText.trim() : null,
      rowRect: rect(row),
      buttons: Array.from(row.querySelectorAll('button,[class*=icon],[class*=more],[class*=switch],[role=menuitem],[class*=menu]'))
        .map(b => ({ tag: b.tagName, cls: String(b.className).slice(0, 85), vis: vis(b),
                     t: (b.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 20), r: rect(b) })),
      right: (() => { const rr = row.querySelector('[class*=atm-row-right]');
        return rr ? { cls: String(rr.className).slice(0, 90), html: rr.outerHTML.slice(0, 800) } : null; })()
    };
  });
})
