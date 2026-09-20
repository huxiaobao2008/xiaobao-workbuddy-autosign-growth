(async (action) => {
  const out = {};
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 90);

  await closeOverlays(3);
  await openNewTask();
  await sleep(1500);
  out.scene = await setScene('设计创意');
  await sleep(2500);

  const items = Array.from(document.querySelectorAll('.quick-actions__item')).filter(isVisible);
  out.items = items.map(e => T(e));

  const it = items.find(e => T(e) === action) || items[0];
  out.clicked = it ? T(it) : null;
  if (!it) return out;
  realClick(it);
  await sleep(3500);

  const ed = document.querySelector('[contenteditable=true]');
  out.after = {
    edText: ed ? (ed.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 200) : null,
    chips: Array.from(document.querySelectorAll('.phrase-content-wrapper, [class*=chip]'))
             .map(x => (x.innerText || '').replace(/\s+/g, ' ').trim()).filter(Boolean).slice(0, 10),
    scene: Array.from(document.querySelectorAll('.wb-scene-tabs__pill'))
             .filter(p => /--active/.test(p.className.toString())).map(T),
    sendBtn: !!(document.querySelector('button.cr-send-button')),
    bodyTop: (document.body.innerText || '').replace(/\s+/g, ' ').slice(0, 300)
  };
  return out;
})()
