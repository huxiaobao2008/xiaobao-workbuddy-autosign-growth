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

  const go = Array.from(document.querySelectorAll('button')).filter(isVisible).find(b => /继续使用/.test(T(b)));
  out.goFound = !!go;
  if (go) {
    out.goTxt = T(go).slice(0, 20);
    out.goDisabled = !!go.disabled;
    out.goCls = go.className.toString().slice(0, 90);
    // 向上找容器
    let p = go, chain = [];
    for (let i = 0; i < 8 && p; i++) {
      chain.push({ tag: p.tagName.toLowerCase(), cls: (p.className||'').toString().slice(0, 80),
                   nInput: p.querySelectorAll ? p.querySelectorAll('input').length : -1 });
      p = p.parentElement;
    }
    out.chain = chain;
    const root = go.closest('div[class*=dialog], div[class*=Dialog], div[class*=modal], div[class*=Modal]') || go.parentElement.parentElement.parentElement;
    out.rootCls = root ? root.className.toString().slice(0, 90) : null;
    out.rootInputs = root ? Array.from(root.querySelectorAll('input')).map(i => ({
      type: i.type, cls: i.className.toString().slice(0, 60), checked: i.checked })) : [];
    out.rootLabels = root ? Array.from(root.querySelectorAll('label')).map(l => ({
      cls: l.className.toString().slice(0, 60), t: T(l).slice(0, 30) })) : [];
    out.rootButtons = root ? Array.from(root.querySelectorAll('button')).map(b => ({
      t: T(b).slice(0, 20), cls: b.className.toString().slice(0, 80), disabled: !!b.disabled })) : [];
    // 「我已知悉并确认」元素
    const ack = root ? Array.from(root.querySelectorAll('*')).filter(e => e.children.length === 0 && /我已知悉并确认/.test(T(e))) : [];
    out.ackEls = ack.map(e => ({ tag: e.tagName.toLowerCase(), cls: (e.className||'').toString().slice(0, 70) }));
    // 尝试多种勾选方式
    if (out.rootInputs.length) {
      const cb = root.querySelector('input');
      realClick(cb); await sleep(600);
      out.checkedAfterInput = cb.checked;
    } else if (ack.length) {
      let a = ack[0];
      for (let i = 0; i < 4 && a; i++) { if ((a.className||'').toString() && /check|radio|box/i.test(a.className.toString())) break; a = a.parentElement; }
      out.ackClickTarget = a ? (a.className||'').toString().slice(0, 70) : null;
      if (a) { realClick(a); await sleep(700); }
    }
    out.goDisabled2 = !!go.disabled;
    out.goCls2 = go.className.toString().slice(0, 90);
  }
  return out;
})()
