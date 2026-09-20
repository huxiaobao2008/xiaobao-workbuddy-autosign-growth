(async (title) => {
  const out = {};
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 200);

  await closeOverlays(3);
  await openNewTask();
  await sleep(1200);
  const items = Array.from(document.querySelectorAll('.conversation-section-tasks .conversation-item'));
  const it = items.find(e => T(e).indexOf(title) !== -1);
  out.found = !!it;
  if (!it) { out.have = items.map(e => T(e).slice(0, 30)); return out; }
  realClick(it);
  await sleep(4000);

  out.view = {
    bodyTop: (document.querySelector('.cr-message-list-viewport') || document.body).innerText
               .replace(/\s+/g, ' ').slice(0, 700),
    hasViewport: !!document.querySelector('.cr-message-list-viewport'),
    hasArtifact: !!document.querySelector('[class*=artifact], [class*=canvas], [class*=preview]'),
    artifactCls: Array.from(new Set(Array.from(document.querySelectorAll('[class*=artifact], [class*=canvas]'))
      .map(e => e.className.toString().split(' ')[0]))).slice(0, 30),
    tabs: Array.from(document.querySelectorAll('button, [role=tab]')).filter(isVisible)
            .map(T).filter(t => t && t.length <= 16).slice(0, 30),
    iframes: Array.from(document.querySelectorAll('iframe')).map(f => (f.src || '').slice(0, 80))
  };
  return out;
})()
