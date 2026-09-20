(async () => {
  const out = { steps: [], views: [] };
  const visible = el => { const r = el.getBoundingClientRect(); return r.width > 8 && r.height > 8; };
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();

  function dumpPanel(tag, maxLen) {
    const pops = Array.from(document.querySelectorAll('[class*=popover], [class*=modal], [class*=drawer], [class*=panel], [class*=dialog]'))
      .filter(visible)
      .filter(p => !/menubar/.test(p.className.toString()));
    out.views.push({
      tag: tag,
      panels: pops.map(p => ({ cls: p.className.toString().slice(0, 80), txt: T(p).slice(0, maxLen || 700) })).slice(0, 6),
      clickable: (() => {
        const acc = [];
        pops.forEach(p => p.querySelectorAll('button, [role=menuitem], [role=option], [class*=item], li').forEach(el => {
          if (!visible(el)) return;
          const t = T(el);
          if (t && t.length <= 26) acc.push(t);
        }));
        return Array.from(new Set(acc)).slice(0, 70);
      })()
    });
  }

  const openUserMenu = async () => {
    // 先按 Esc 关掉可能开着的浮层
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    await sleep(500);
    const trig = document.querySelector('.user-menu-trigger');
    if (!trig) return false;
    realClick(trig);
    await sleep(1600);
    return true;
  };

  // ---- 1) 用户菜单 -> 外观 ----
  await openUserMenu();
  const ap = Array.from(document.querySelectorAll('.user-menu-item--appearance, .user-menu-item'))
    .find(el => T(el).indexOf('外观') === 0);
  out.steps.push('appearance item found=' + !!ap);
  if (ap) { realClick(ap); await sleep(2200); dumpPanel('after-click-外观'); }

  // ---- 2) 回到首页，再开菜单 -> 设置 ----
  await openUserMenu();
  const st = Array.from(document.querySelectorAll('.user-menu-item')).find(el => T(el) === '设置');
  out.steps.push('settings item found=' + !!st);
  if (st) { realClick(st); await sleep(2400); dumpPanel('after-click-设置', 1800); }

  return out;
})()
