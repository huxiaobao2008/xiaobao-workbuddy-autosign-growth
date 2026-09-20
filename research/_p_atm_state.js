(async () => {
  const out = { modal: !!document.querySelector('.wb-modal') };
  const modal = document.querySelector('.wb-modal');
  if (!modal) return out;
  out.text = (modal.innerText || '').replace(/\s+/g, ' ').slice(0, 700);
  out.buttons = [];
  modal.querySelectorAll('button').forEach(b => {
    const r = b.getBoundingClientRect();
    out.buttons.push({
      t: (b.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 20),
      cls: b.className.toString().slice(0, 90),
      disabled: !!b.disabled, aria: b.getAttribute('aria-disabled'),
      w: Math.round(r.width), h: Math.round(r.height)
    });
  });
  out.fields = [];
  modal.querySelectorAll('input, [contenteditable=true]').forEach(el => {
    out.fields.push({
      tag: el.tagName.toLowerCase(), cls: el.className.toString().slice(0, 70),
      val: el.value !== undefined ? el.value : (el.innerText || '').slice(0, 60),
      disabled: !!el.disabled, ro: !!el.readOnly
    });
  });
  return out;
})()
