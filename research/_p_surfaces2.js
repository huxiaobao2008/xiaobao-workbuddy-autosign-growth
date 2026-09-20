(async () => {
  const out = { parts: [] };
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const vis = el => { const r = el.getBoundingClientRect(); return r.width > 8 && r.height > 8; };
  const esc = () => document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));

  function clickSidebar(t) {
    const norm = s => (s || '').replace(/\s+/g, '');
    const b = Array.from(document.querySelectorAll('.conversation-list-tab-button'))
      .find(e => norm(T(e)) === norm(t)) ||
      Array.from(document.querySelectorAll('button')).filter(vis)
        .find(e => norm(T(e)) === norm(t));
    if (!b) return null;
    realClick(b);
    return T(b);
  }

  function dump(tag, len) {
    const pops = Array.from(document.querySelectorAll(
        '[class*=popover], [class*=modal], [class*=dialog], [class*=drawer], [class*=sheet]')).filter(vis);
    const inputs = [];
    document.querySelectorAll('input, textarea, select').forEach(el => {
      if (!vis(el)) return;
      inputs.push({ tag: el.tagName.toLowerCase(), ph: el.placeholder || '', val: (el.value || '').slice(0, 40),
                    cls: el.className.toString().slice(0, 60) });
    });
    const labels = [];
    document.querySelectorAll('button, [role=button], [class*=tab], [class*=item]').forEach(el => {
      if (!vis(el)) return;
      const t = T(el); if (t && t.length <= 26) labels.push(t);
    });
    out.parts.push({ tag: tag,
                     panels: pops.map(p => ({ cls: p.className.toString().slice(0, 80), txt: T(p).slice(0, len || 800) })).slice(0, 4),
                     inputs: inputs.slice(0, 25),
                     labels: Array.from(new Set(labels)).slice(0, 70) });
  }

  // ---------- 1) 定时任务 ----------
  out.parts.push({ tag: 'clickSidebar(定时任务)', r: clickSidebar('定时任务') });
  await sleep(2500);
  dump('定时任务页', 500);
  // 打开添加对话框
  const add = Array.from(document.querySelectorAll('button')).filter(vis).find(e => T(e).indexOf('添加') !== -1);
  out.parts.push({ tag: 'found 添加定时任务', r: add ? T(add) : null });
  if (add) { realClick(add); await sleep(2600); dump('添加定时任务对话框', 1200); esc(); await sleep(800); }

  // ---------- 2) 发现应用 -> 企鹅教师助手 ----------
  out.parts.push({ tag: 'clickSidebar(新建任务)', r: clickSidebar('新建任务') });
  await sleep(1500);
  const disc = Array.from(document.querySelectorAll('button')).filter(vis)
    .find(e => T(e) === '发现应用');
  out.parts.push({ tag: 'found 发现应用', r: disc ? 'yes' : null });
  if (disc) {
    realClick(disc); await sleep(2200);
    dump('发现应用弹层', 900);
    const qq = Array.from(document.querySelectorAll('*')).filter(vis)
      .filter(e => T(e).indexOf('企鹅教师助手') === 0 && e.children.length <= 3)
      .sort((a, b) => a.querySelectorAll('*').length - b.querySelectorAll('*').length);
    out.parts.push({ tag: 'found 企鹅教师助手', r: qq.length ? T(qq[0]).slice(0, 40) : null,
                     cls: qq.length ? qq[0].className.toString().slice(0, 80) : '' });
    if (qq.length) {
      realClick(qq[0]); await sleep(3500);
      dump('点企鹅教师助手之后', 700);
    }
  }

  // ---------- 3) 专家·技能·连接器 ----------
  out.parts.push({ tag: 'clickSidebar(专家·技能·连接器)', r: clickSidebar('专家·技能·连接器') });
  await sleep(2600);
  dump('专家中心首页', 700);
  const skillTab = Array.from(document.querySelectorAll('*')).filter(vis)
    .filter(e => T(e) === '技能' && e.children.length === 0)[0];
  out.parts.push({ tag: 'found 技能 tab', r: skillTab ? 'yes' : null });
  if (skillTab) {
    realClick(skillTab); await sleep(2600);
    dump('技能页', 900);
  }
  return out;
})()
