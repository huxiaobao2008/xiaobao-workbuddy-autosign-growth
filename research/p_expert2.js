(async () => {
  const out = { steps: [] };
  const vis = el => { const r = el.getBoundingClientRect(); return r.width > 8 && r.height > 8; };
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 44);

  await closeOverlays();
  await openNewTask();
  await sleep(1200);
  const before = taskTitles();

  const entry = Array.from(document.querySelectorAll('button.conversation-list-tab-button'))
    .find(b => T(b).indexOf('专家') !== -1);
  realClick(entry);
  await sleep(3000);

  const card = document.querySelector('.ec-expert-card');
  if (!card) return { err: 'no expert card' };
  out.cardTitle = T(card);
  const summon = card.querySelector('.ec-card-summon-btn')
    || Array.from(card.querySelectorAll('button')).find(b => /召唤/.test(T(b)));
  out.summonTxt = summon ? T(summon) : null;
  if (!summon) return Object.assign(out, { err: 'no summon btn', html: card.outerHTML.slice(0, 500) });
  realClick(summon);
  await sleep(4500);

  out.after = {
    href: location.href.slice(0, 90),
    hasComposer: !!document.querySelector('[contenteditable=true]'),
    hasView: !!document.querySelector('.cr-message-list-viewport'),
    newTitles: taskTitles().filter(t => before.indexOf(t) === -1),
    bodyText: (document.querySelector('.cr-message-list-viewport') || document.body).innerText.replace(/\s+/g, ' ').slice(0, 600),
    labels: Array.from(document.querySelectorAll('button, [class*=tab], [class*=chip]')).filter(vis)
              .map(e => T(e)).filter(t => t && t.length <= 24).slice(0, 40)
  };
  return out;
})()
