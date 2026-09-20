(async () => {
  const out = { steps: [] };
  const vis = el => { const r = el.getBoundingClientRect(); return r.width > 8 && r.height > 8; };
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 60);

  // 0) 关掉可能残留的弹窗/模态
  const modals = Array.from(document.querySelectorAll('[class*=modal], [class*=dialog], [class*=popover]'))
    .filter(vis).map(e => e.className.toString().slice(0, 70));
  out.modals = Array.from(new Set(modals));
  const closer = Array.from(document.querySelectorAll('button'))
    .filter(b => vis(b) && /关闭|取消|知道了|×/.test(T(b)))
    .map(b => ({ t: T(b), cls: b.className.toString().slice(0, 70) }));
  out.closers = closer.slice(0, 10);
  document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
  await sleep(500);

  // 1) 首页 → 设计创意模式
  await openNewTask();
  await sleep(1800);
  const chips = Array.from(document.querySelectorAll('[class*=chip], [class*=mode], [class*=scene], [class*=industry]'))
    .filter(vis).map(e => ({ t: T(e), cls: e.className.toString().slice(0, 80) }));
  out.chips = chips.filter(c => c.t && c.t.length < 24).slice(0, 20);

  const design = Array.from(document.querySelectorAll('button, [role=button], div, span'))
    .filter(e => vis(e) && T(e) === '设计创意')
    .sort((a, b) => a.querySelectorAll('*').length - b.querySelectorAll('*').length)[0] || null;
  out.designEl = design ? { tag: design.tagName.toLowerCase(), cls: design.className.toString().slice(0, 90) } : null;
  if (design) {
    realClick(design);
    await sleep(2500);
    // 模式切换后页面出现什么
    const after = Array.from(document.querySelectorAll('button, [role=button], [class*=card], [class*=item], [class*=chip]'))
      .filter(vis).map(e => T(e)).filter(t => t && t.length <= 30);
    out.afterDesign = Array.from(new Set(after)).slice(0, 60);
    out.composerHint = (document.querySelector('[contenteditable=true]') || {}).innerText || null;
    out.hasCanvasBtn = !!document.querySelector('[class*=canvas]');
    out.canvasCls = Array.from(new Set(Array.from(document.querySelectorAll('[class*=canvas]'))
      .map(e => e.className.toString().slice(0, 80)))).slice(0, 20);
  }
  return out;
})()
