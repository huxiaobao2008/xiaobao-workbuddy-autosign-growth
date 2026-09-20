(async () => {
  const out = {};
  const vis = el => { const r = el.getBoundingClientRect(); return r.width > 8 && r.height > 8; };
  const dumpEd = (tag) => Array.from(document.querySelectorAll('[contenteditable=true]'))
    .map((e, i) => ({ i: i, tag: tag, vis: vis(e),
                      cls: e.className.toString().slice(0, 70),
                      rect: (r => [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)])(e.getBoundingClientRect()),
                      ph: e.getAttribute('data-placeholder') || e.getAttribute('placeholder'),
                      t: (e.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 40) }));

  await closeOverlays();
  await openNewTask();
  await sleep(1500);
  out.editors_home = dumpEd('home');
  out.scene = await setScene('设计创意');
  await sleep(1800);
  out.editors_design = dumpEd('design');
  out.activeIs = document.activeElement ? document.activeElement.className.toString().slice(0, 60) : null;
  return out;
})()
