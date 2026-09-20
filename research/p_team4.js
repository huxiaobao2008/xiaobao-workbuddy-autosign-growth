(async () => {
  const out = {};
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 100);

  await closeOverlays(3);
  await openNewTask();
  await sleep(1200);
  const entry = Array.from(document.querySelectorAll('button.conversation-list-tab-button'))
    .find(b => T(b).indexOf('专家') !== -1);
  realClick(entry);
  await sleep(1500);
  for (let i = 0; i < 20; i++) { if (document.querySelector('.ec-list-tab')) break; await sleep(800); }
  const teamTab = Array.from(document.querySelectorAll('.ec-list-tab')).find(e => T(e) === '专家团');
  realClick(teamTab);
  await sleep(3000);
  const sb = Array.from(document.querySelectorAll('button')).filter(b => T(b).indexOf('召唤') !== -1 && isVisible(b));
  realClick(sb[0]);
  await sleep(3000);

  const ov = document.querySelector('.ec-team-summon-confirm-overlay');
  out.ovFound = !!ov;
  if (!ov) return out;
  out.ovHtml = ov.outerHTML.replace(/\s+/g, ' ').slice(0, 1800);
  out.inputs = Array.from(ov.querySelectorAll('input')).map(i => ({
    type: i.type, cls: i.className.toString().slice(0, 70), checked: i.checked }));
  out.checkEls = Array.from(ov.querySelectorAll('[class*=check]')).map(e => ({
    tag: e.tagName.toLowerCase(), cls: e.className.toString().slice(0, 70), t: T(e).slice(0, 24) }));
  out.ackEls = Array.from(ov.querySelectorAll('*')).filter(e => e.children.length <= 1 && /我已知悉并确认/.test(T(e)))
    .map(e => ({ tag: e.tagName.toLowerCase(), cls: (e.className||'').toString().slice(0, 70), t: T(e).slice(0, 30) }));

  // 尝试 1：直接点 input 的 label 容器
  const cb = ov.querySelector('input[type=checkbox]') || ov.querySelector('input');
  if (cb) {
    const wrap = cb.closest('label') || cb.parentElement;
    out.wrapCls = wrap ? wrap.className.toString().slice(0, 70) : null;
    realClick(wrap || cb);
    await sleep(800);
    out.after1 = cb.checked;
    const go = Array.from(ov.querySelectorAll('button')).find(b => /继续使用/.test(T(b)));
    out.goDisabled1 = go ? !!go.disabled : null;
  }
  return out;
})()
