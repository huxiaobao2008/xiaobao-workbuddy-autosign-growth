(async () => {
  const out = {};
  const vis = el => { const r = el.getBoundingClientRect(); return r.width > 8 && r.height > 8; };
  const T = el => (el.innerText || el.getAttribute('title') || '').replace(/\s+/g, ' ').trim().slice(0, 40);

  await closeOverlays();
  await openNewTask();
  await sleep(1500);
  out.leftLibraryView = !!document.querySelector('iframe');

  // A) 左下角用户菜单
  const um = document.querySelector('.user-menu-trigger');
  if (um) { realClick(um); await sleep(1500); }
  out.userMenu = Array.from(document.querySelectorAll('[class*=user-menu] *, [class*=popover] *, [class*=dropdown] *'))
    .filter(vis).map(e => ({ t: T(e), cls: e.className.toString().slice(0, 70) }))
    .filter(o => o.t).slice(0, 40);
  document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
  await sleep(800);

  // B) 顶部 menubar 的文件菜单
  const mb = Array.from(document.querySelectorAll('.menubar-menu-button, [class*=menubar] button'))
    .filter(vis).map(e => ({ t: T(e), cls: e.className.toString().slice(0, 70) }));
  out.menubar = mb.slice(0, 10);
  if (mb.length) {
    const first = Array.from(document.querySelectorAll('.menubar-menu-button, [class*=menubar] button')).filter(vis)[0];
    realClick(first); await sleep(1200);
    out.menubarOpen = Array.from(document.querySelectorAll('[class*=menu] *')).filter(vis)
      .map(e => T(e)).filter(t => t && t.length <= 20).slice(0, 40);
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    await sleep(600);
  }
  // C) 找「外观/主题/设置」类元素
  out.hits = Array.from(document.querySelectorAll('*'))
    .filter(e => vis(e) && /^(外观|主题|设置|偏好)$/.test(T(e)))
    .map(e => ({ t: T(e), tag: e.tagName.toLowerCase(), cls: e.className.toString().slice(0, 70) })).slice(0, 20);
  return out;
})()
