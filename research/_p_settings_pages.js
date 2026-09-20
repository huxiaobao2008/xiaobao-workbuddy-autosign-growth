(async () => {
  const out = { steps: [], views: [] };
  const visible = el => { const r = el.getBoundingClientRect(); return r.width > 8 && r.height > 8; };
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();

  function closeAll() {
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
  }
  function snap(tag, len) {
    const m = document.querySelector('.settings-modal');
    out.views.push({
      tag: tag,
      txt: m ? T(m).slice(0, len || 1500) : '(no settings modal)'
    });
  }
  async function openSettings() {
    closeAll(); await sleep(400);
    const trig = document.querySelector('.user-menu-trigger');
    realClick(trig); await sleep(1400);
    const st = Array.from(document.querySelectorAll('.user-menu-item')).find(el => T(el) === '设置');
    if (!st) return false;
    realClick(st); await sleep(2200);
    return true;
  }
  async function navTo(name) {
    const m = document.querySelector('.settings-modal');
    if (!m) return false;
    const el = Array.from(m.querySelectorAll('button, [class*=nav], [class*=item], li, div'))
      .filter(visible).filter(e => T(e) === name)
      .sort((a, b) => a.querySelectorAll('*').length - b.querySelectorAll('*').length)[0];
    if (!el) return false;
    realClick(el); await sleep(2000);
    return true;
  }

  out.steps.push('openSettings=' + await openSettings());
  out.steps.push('nav 个人主页=' + await navTo('个人主页'));
  snap('个人主页', 1600);

  out.steps.push('nav 套餐与积分=' + await navTo('套餐与积分'));
  snap('套餐与积分', 1600);

  out.steps.push('nav 应用管理=' + await navTo('应用管理'));
  snap('应用管理', 1200);

  closeAll();
  await sleep(400);
  return out;
})()
