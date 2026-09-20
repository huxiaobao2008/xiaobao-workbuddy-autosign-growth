(async (action, suggestion) => {
  const out = {};
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 120);

  await closeOverlays(3);
  await openNewTask();
  await sleep(1500);
  out.scene = await setScene('设计创意');
  await sleep(2500);

  const items = Array.from(document.querySelectorAll('.quick-actions__item')).filter(isVisible);
  const it = items.find(e => T(e) === action);
  if (it) { realClick(it); await sleep(3000); }

  // 建议词 chip（点击后会填进输入框）
  const cands = Array.from(document.querySelectorAll('*')).filter(isVisible)
    .filter(e => e.children.length <= 2 && T(e) === suggestion);
  out.suggFound = cands.length;
  out.suggCls = cands.slice(0, 3).map(e => ({ tag: e.tagName.toLowerCase(), cls: (e.className || '').toString().slice(0, 70) }));
  if (cands.length) {
    const target = cands[cands.length - 1];
    const clickable = target.closest('button, [class*=chip], [class*=tag], [role=button]') || target;
    out.clickedEl = { tag: clickable.tagName.toLowerCase(), cls: clickable.className.toString().slice(0, 70) };
    realClick(clickable);
    await sleep(3000);
  }
  const ed = document.querySelector('[contenteditable=true]');
  out.after = {
    edText: ed ? (ed.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 300) : null,
    edHTML: ed ? ed.innerHTML.replace(/\s+/g, ' ').slice(0, 300) : null,
    chips: Array.from(document.querySelectorAll('.phrase-content-wrapper')).map(x => T(x)),
    scene: Array.from(document.querySelectorAll('.wb-scene-tabs__pill'))
             .filter(p => /--active/.test(p.className.toString())).map(T)
  };
  return out;
})()
