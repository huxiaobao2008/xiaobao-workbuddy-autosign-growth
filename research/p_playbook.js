(async () => {
  const out = { steps: [] };
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 80);

  await closeOverlays(3);
  await openNewTask();
  await sleep(1500);

  const sub = Array.from(document.querySelectorAll('.conversation-list-tab-button-sub'))
    .find(e => T(e).indexOf('灵感') !== -1);
  out.subFound = !!sub;
  out.subCls = sub ? sub.className.toString() : null;
  if (!sub) return out;
  realClick(sub);

  // 逐拍观察 12 秒
  const frames = [];
  for (let i = 0; i < 8; i++) {
    await sleep(1500);
    frames.push({
      t: (i + 1) * 1.5,
      url: location.href.slice(-70),
      activeTab: (document.querySelector('.conversation-list-tab-button-sub.active, .conversation-list-tab-button.active') || {}).innerText || null,
      playbookCards: Array.from(document.querySelectorAll('.wb-related-playbooks__card, [class*=playbook-card], [class*=inspiration-card]')).length,
      titles: Array.from(document.querySelectorAll('.wb-related-playbooks__card-title, [class*=playbook] [class*=title]')).map(T).slice(0, 8),
      home: !!document.querySelector('.wb-home-composer__chips'),
      sceneTabs: Array.from(document.querySelectorAll('.wb-scene-tabs__pill')).length
    });
  }
  out.frames = frames;

  // 页面主内容
  out.mainCls = Array.from(new Set(Array.from(document.querySelectorAll('[class*=inspiration], [class*=playbook], [class*=idea], [class*=explore]'))
    .map(e => e.className.toString().split(' ')[0]))).slice(0, 50);
  out.bodySnippet = (document.body.innerText || '').replace(/\s+/g, ' ').slice(0, 800);
  return out;
})()
