(async () => {
  const out = {};
  const modal = document.querySelector('.wb-modal');
  out.modal = !!modal;
  if (!modal) { out.dialogs = document.querySelectorAll('.wb-modal').length; return out; }
  const ok = Array.from(modal.querySelectorAll('button')).find(b => (b.innerText || '').trim() === '确定');
  out.okFound = !!ok;
  if (ok) {
    const r = ok.getBoundingClientRect();
    out.rect = { x: Math.round(r.left), y: Math.round(r.top), w: Math.round(r.width), h: Math.round(r.height) };
    const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
    const top = document.elementFromPoint(cx, cy);
    out.elementAtPoint = top ? { tag: top.tagName, cls: top.className.toString().slice(0, 80),
                                 txt: (top.innerText || '').slice(0, 20),
                                 isOk: top === ok || ok.contains(top) } : null;
    out.winH = window.innerHeight; out.winW = window.innerWidth;
  }
  // 是否有校验提示 / toast
  out.invalid = Array.from(modal.querySelectorAll('[class*=error], [class*=invalid], [aria-invalid=true]'))
    .filter(e => (e.innerText || '').trim()).map(e => (e.innerText || '').replace(/\s+/g, ' ').slice(0, 80));
  out.toasts = Array.from(document.querySelectorAll('[class*=toast], [class*=message], [class*=notification]'))
    .filter(e => { const r = e.getBoundingClientRect(); return r.width > 40 && r.height > 10 && (e.innerText || '').trim(); })
    .map(e => (e.innerText || '').replace(/\s+/g, ' ').slice(0, 120));
  out.modalText = (modal.innerText || '').replace(/\s+/g, ' ').slice(0, 600);
  return out;
})()
