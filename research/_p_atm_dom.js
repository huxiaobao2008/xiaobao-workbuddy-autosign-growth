(() => {
  const modal = document.querySelector('.wb-modal');
  if (!modal) return { modal: false };
  const out = { modal: true, html: modal.outerHTML.slice(0, 6000) };
  // 所有输入控件
  out.inputs = Array.from(modal.querySelectorAll('input,textarea,[contenteditable=true]'))
    .map(e => ({ tag: e.tagName, cls: String(e.className).slice(0, 60),
                 ph: e.placeholder || null, val: (e.value !== undefined ? e.value : (e.innerText||'')).slice(0, 60),
                 disabled: !!e.disabled }));
  // 所有按钮
  out.buttons = Array.from(modal.querySelectorAll('button')).map(b => ({
    t: (b.innerText||'').trim().slice(0, 20),
    cls: String(b.className).slice(0, 70),
    disabled: !!b.disabled,
    aria: b.getAttribute('aria-disabled')
  }));
  // 触发器
  out.triggers = Array.from(modal.querySelectorAll('[class*=trigger],[class*=select]'))
    .map(e => ({ cls: String(e.className).slice(0, 70), t: (e.innerText||'').replace(/\s+/g,' ').trim().slice(0, 60) }));
  return out;
})
