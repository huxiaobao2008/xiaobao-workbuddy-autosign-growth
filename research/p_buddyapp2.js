(async () => {
  const out = { steps: [] };
  const vis = el => { const r = el.getBoundingClientRect(); return r.width > 8 && r.height > 8; };
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 60);
  const before = taskTitles();

  await openNewTask();
  await sleep(1500);
  const btn = Array.from(document.querySelectorAll('button.industry-template-switcher__trigger')).find(vis);
  if (!btn) return { err: 'no switcher button' };
  realClick(btn);
  await sleep(2500);

  // 找目标项（默认 企鹅教师助手）
  const want = '企鹅教师助手';
  const items = Array.from(document.querySelectorAll('.industry-template-switcher__item'));
  out.items = items.map(it => {
    const ti = it.querySelector('.industry-template-switcher__item-title');
    const act = it.querySelector('.industry-template-switcher__item-action-btn');
    return { title: ti ? T(ti) : null, hasAction: !!act,
             actionCls: act ? act.className.toString().slice(0, 80) : null };
  });
  const item = items.find(it => T(it).indexOf(want) !== -1);
  if (!item) return Object.assign(out, { err: '找不到 ' + want });
  const act = item.querySelector('.industry-template-switcher__item-action-btn') || item;
  out.clicked = { tag: act.tagName.toLowerCase(), cls: act.className.toString().slice(0, 90), txt: T(act) };
  realClick(act);
  await sleep(4000);

  out.href = location.href.slice(0, 120);
  out.hasComposer = !!document.querySelector('[contenteditable=true]');
  out.hasAgent = !!document.querySelector('.cr-agent');
  out.viewText = (document.querySelector('.cr-message-list-viewport') || document.body).innerText.slice(0, 500);
  out.newTitles = taskTitles().filter(t => before.indexOf(t) === -1);
  return out;
})()
