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

  // 专家团 tab
  const teamTab = Array.from(document.querySelectorAll('.ec-list-tab')).find(e => T(e) === '专家团');
  realClick(teamTab);
  await sleep(3000);

  // 团队卡片结构
  const teamGrid = document.querySelector('.teams-grid-scroll-content, .teams-content-wrapper, .teams-container');
  out.teamGridCls = teamGrid ? teamGrid.className.toString() : null;
  // 所有含召唤按钮的元素，取其最近的"卡片"祖先
  const summonBtns = Array.from(document.querySelectorAll('button')).filter(b => T(b).indexOf('召唤') !== -1 && isVisible(b));
  out.nSummon = summonBtns.length;
  if (summonBtns.length) {
    let p = summonBtns[0];
    const chain = [];
    for (let i = 0; i < 6 && p; i++) { chain.push({ tag: p.tagName.toLowerCase(), cls: (p.className || '').toString().slice(0, 80) }); p = p.parentElement; }
    out.chain = chain;
    out.cardCls = chain.map(c => c.cls).find(c => /card/i.test(c)) || null;
  }
  out.allTeamCardCls = Array.from(new Set(summonBtns.map(b => {
    let p = b; for (let i = 0; i < 6 && p; i++) { p = p.parentElement; if (p && /card/i.test((p.className||'').toString())) return p.className.toString().split(' ')[0]; }
    return null;
  }).filter(Boolean)));

  // 点第一个团队的召唤
  if (summonBtns.length) {
    out.firstTeamName = T(summonBtns[0].closest('[class*=card]') || summonBtns[0]);
    realClick(summonBtns[0]);
    await sleep(5000);
    out.afterSummon = {
      href: location.href.slice(0, 100),
      hasComposer: !!document.querySelector('[contenteditable=true]'),
      hasView: !!document.querySelector('.cr-message-list-viewport'),
      stillExpertPage: !!document.querySelector('.ec-expert-card, .ec-list-tab'),
      newTitles: taskTitles().filter(t => before.indexOf(t) === -1),
      bodySnippet: (document.querySelector('.cr-message-list-viewport') || document.body).innerText.replace(/\s+/g, ' ').slice(0, 400),
      dialogs: Array.from(document.querySelectorAll('.wb-modal, [class*=dialog]')).filter(isVisible).map(e => T(e).slice(0, 120))
    };
  }
  return out;
})()
