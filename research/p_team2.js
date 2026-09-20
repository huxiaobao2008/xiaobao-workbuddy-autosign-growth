(async () => {
  const out = {};
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 90);

  await closeOverlays(3);
  await openNewTask();
  await sleep(1200);
  const entry = Array.from(document.querySelectorAll('button.conversation-list-tab-button'))
    .find(b => T(b).indexOf('专家') !== -1);
  realClick(entry);
  await sleep(1500);
  for (let i = 0; i < 20; i++) { if (document.querySelector('.ec-list-tab')) break; await sleep(800); }
  const before = taskTitles();
  const teamTab = Array.from(document.querySelectorAll('.ec-list-tab')).find(e => T(e) === '专家团');
  realClick(teamTab);
  await sleep(3000);

  const sb = Array.from(document.querySelectorAll('button')).filter(b => T(b).indexOf('召唤') !== -1 && isVisible(b));
  out.n = sb.length;
  // 取第一个团队的完整名字
  const card0 = sb[0].closest('.ec-expert-card');
  out.teamName0 = card0 ? T(card0).slice(0, 40) : null;
  realClick(sb[0]);
  await sleep(3000);

  // 弹层结构
  const dlg = Array.from(document.querySelectorAll('.wb-modal, [class*=dialog], [role=dialog]'))
    .filter(isVisible).filter(e => /积分消耗|知悉/.test(T(e))).sort((a,b)=>a.querySelectorAll('*').length-b.querySelectorAll('*').length)[0] || null;
  out.dlgFound = !!dlg;
  if (dlg) {
    out.dlgCls = dlg.className.toString().slice(0, 90);
    out.checkboxes = Array.from(dlg.querySelectorAll('input[type=checkbox]')).map(c => ({
      cls: c.className.toString().slice(0, 60), checked: c.checked,
      parentCls: (c.parentElement ? c.parentElement.className.toString().slice(0, 70) : null) }));
    out.dlgButtons = Array.from(dlg.querySelectorAll('button')).map(b => ({
      t: T(b).slice(0, 20), cls: b.className.toString().slice(0, 70), disabled: !!b.disabled }));
    // 尝试勾选
    const cbLabel = dlg.querySelector('label') || dlg.querySelector('[class*=checkbox]');
    out.cbLabelCls = cbLabel ? cbLabel.className.toString().slice(0, 70) : null;
    if (cbLabel) { realClick(cbLabel); await sleep(600); }
    out.afterCheck = Array.from(dlg.querySelectorAll('input[type=checkbox]')).map(c => c.checked);
    // 点「继续使用」
    const go = Array.from(dlg.querySelectorAll('button')).find(b => /继续使用/.test(T(b)));
    out.goFound = !!go;
    out.goDisabled = go ? !!go.disabled : null;
    if (go && !go.disabled) {
      realClick(go);
      await sleep(6000);
    }
  }
  out.after = {
    stillDialog: !!Array.from(document.querySelectorAll('.wb-modal')).filter(isVisible).filter(e => /积分消耗/.test(T(e))).length,
    hasComposer: !!document.querySelector('[contenteditable=true]'),
    hasView: !!document.querySelector('.cr-message-list-viewport'),
    stillExpert: !!document.querySelector('.ec-list-tab'),
    newTitles: taskTitles().filter(t => before.indexOf(t) === -1),
    body: (document.querySelector('.cr-message-list-viewport') || document.body).innerText.replace(/\s+/g, ' ').slice(0, 400)
  };
  return out;
})()
