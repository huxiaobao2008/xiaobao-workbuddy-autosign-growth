(async () => {
  const out = {};
  const vis = el => { const r = el.getBoundingClientRect(); return r.width > 8 && r.height > 8; };
  const T = el => (el.innerText || el.getAttribute('placeholder') || '').replace(/\s+/g, ' ').trim().slice(0, 50);

  await closeOverlays();
  await openNewTask();
  await sleep(1500);
  out.scene = await setScene('设计创意');
  await sleep(1500);

  out.urlTail = location.href.slice(-160);
  out.editors = Array.from(document.querySelectorAll('[contenteditable=true], textarea, input[type=text]'))
    .map(e => ({ tag: e.tagName.toLowerCase(), cls: e.className.toString().slice(0, 80),
                 ph: e.getAttribute('placeholder'), t: T(e) }));
  out.buttons = Array.from(document.querySelectorAll('button')).filter(vis).map(b => T(b)).filter(Boolean).slice(0, 60);
  out.classes = Array.from(new Set(Array.from(document.querySelectorAll('*'))
    .map(e => e.className && e.className.toString()).filter(Boolean)
    .flatMap(c => c.split(/\s+/))
    .filter(c => /design|canvas|scene|prompt|template|poster|image|artifact|iframe|workbench/i.test(c)))).slice(0, 80);
  out.iframes = Array.from(document.querySelectorAll('iframe')).map(f => (f.src || '').slice(0, 120));
  out.cards = Array.from(document.querySelectorAll('[class*=card], [class*=item], [class*=tile]'))
    .filter(vis).map(e => T(e)).filter(t => t && t.length <= 28).slice(0, 60);
  return out;
})()
