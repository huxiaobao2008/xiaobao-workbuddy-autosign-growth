(async () => {
  const out = {};
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 120);

  // 进专家中心
  for (let a = 0; a < 3; a++) {
    if (document.querySelector('.ec-list-tab')) break;
    await openNewTask(); await sleep(1100);
    const e = Array.from(document.querySelectorAll('button.conversation-list-tab-button')).find(b => T(b).indexOf('专家') !== -1);
    realClick(e); await sleep(1600);
    for (let i = 0; i < 20; i++) { if (document.querySelector('.ec-list-tab')) break; await sleep(700); }
  }
  const before = taskTitles();
  out.beforeTitles = before;

  const cards = Array.from(document.querySelectorAll('.ec-expert-card'));
  out.nCards = cards.length;
  const btn = cards[0].querySelector('.ec-card-summon-btn');
  out.btnTxt = T(btn).slice(0, 20);
  realClick(btn);

  // 逐拍观察 8 秒
  const frames = [];
  for (let i = 0; i < 8; i++) {
    await sleep(1000);
    frames.push({
      t: i + 1,
      href: location.href.slice(-70),
      ecPage: !!document.querySelector('.ec-list-tab'),
      hasComposer: !!document.querySelector('[contenteditable=true]'),
      hasView: !!document.querySelector('.cr-message-list-viewport'),
      viewportText: (document.querySelector('.cr-message-list-viewport') || {}).innerText
                    ? document.querySelector('.cr-message-list-viewport').innerText.replace(/\s+/g, ' ').slice(0, 220) : null,
      newTitles: taskTitles().filter(x => before.indexOf(x) === -1),
      modal: Array.from(document.querySelectorAll('.wb-modal, [class*=overlay]')).filter(isVisible).map(e => T(e).slice(0, 80)).filter(Boolean)
    });
  }
  out.frames = frames;
  return out;
})()
