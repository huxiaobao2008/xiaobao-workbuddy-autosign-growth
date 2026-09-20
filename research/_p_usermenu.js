(async () => {
  const out = { steps: [] };
  const visible = el => { const r = el.getBoundingClientRect(); return r.width > 8 && r.height > 8; };
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();

  const trig = document.querySelector('.user-menu-trigger');
  if (!trig) return { err: '找不到 user-menu-trigger' };
  realClick(trig);
  await sleep(1800);

  // 弹出层：找所有新出现的浮层
  const popups = Array.from(document.querySelectorAll(
      '[class*=popover], [class*=dropdown], [class*=menu]:not(.codebuddy-menubar), [role=menu], [class*=popper]'))
    .filter(visible);
  out.popups = popups.map(p => ({
    cls: p.className.toString().slice(0, 90),
    txt: T(p).slice(0, 400)
  }));
  out.steps.push('clicked user-menu-trigger');

  // 弹层里所有可点项
  const items = [];
  popups.forEach(p => p.querySelectorAll('button, [role=menuitem], [class*=item], li, div').forEach(el => {
    if (!visible(el)) return;
    if (el.children.length > 0 && T(el).length > 40) return;
    const t = T(el);
    if (t && t.length <= 30) items.push({ t, cls: el.className.toString().slice(0, 80) });
  }));
  out.items = items.slice(0, 60);
  return out;
})()
