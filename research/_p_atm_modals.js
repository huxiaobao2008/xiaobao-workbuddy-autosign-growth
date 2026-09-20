(() => {
  const modals = Array.from(document.querySelectorAll('.wb-modal'));
  const oks = Array.from(document.querySelectorAll('.wb-modal button'))
    .filter(b => (b.innerText || '').trim() === '确定')
    .map(b => {
      const r = b.getBoundingClientRect();
      const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
      const top = document.elementFromPoint(cx, cy);
      return {
        x: Math.round(cx), y: Math.round(cy), w: Math.round(r.width), h: Math.round(r.height),
        vis: r.width > 8 && r.height > 8,
        inView: r.top >= 0 && r.bottom <= window.innerHeight && r.left >= 0 && r.right <= window.innerWidth,
        hit: !!(top && (top === b || b.contains(top))),
        hitTag: top ? top.tagName + '.' + String(top.className).slice(0, 40) : null,
        modalCls: String(b.closest('.wb-modal').className).slice(0, 80)
      };
    });
  return {
    modalCount: modals.length,
    modalCls: modals.map(m => String(m.className).slice(0, 90)),
    modalRects: modals.map(m => { const r = m.getBoundingClientRect(); return { x: Math.round(r.left), y: Math.round(r.top), w: Math.round(r.width), h: Math.round(r.height) }; }),
    okButtons: oks,
    iw: window.innerWidth, ih: window.innerHeight, dpr: window.devicePixelRatio
  };
})
