(async () => {
  const out = { steps: [] };
  const vis = el => { const r = el.getBoundingClientRect(); return r.width > 8 && r.height > 8; };
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 60);
  const dump = (name, extra) => {
    const labs = [];
    document.querySelectorAll('button, [role=button], a, [class*=tab], [class*=card], [class*=item]')
      .forEach(el => { if (vis(el)) { const t = T(el); if (t && t.length <= 34) labs.push(t); } });
    const cls = Array.from(new Set(Array.from(document.querySelectorAll('*'))
      .map(e => e.className && e.className.toString()).filter(Boolean)
      .flatMap(c => c.split(/\s+/))
      .filter(c => /buddy|template|expert|skill|library|playbook|automation|appear|canvas|design|switcher|store/i.test(c))));
    out.steps.push(Object.assign({ name: name, labs: Array.from(new Set(labs)).slice(0, 70), cls: cls.slice(0, 60) }, extra || {}));
  };

  await openNewTask();
  await sleep(1500);

  // 找「发现应用」：先按类名，再按文本兜底
  let btn = Array.from(document.querySelectorAll('button.industry-template-switcher__trigger')).find(vis);
  out.found_by = btn ? 'class' : null;
  if (!btn) {
    btn = Array.from(document.querySelectorAll('button'))
      .filter(e => vis(e) && T(e).indexOf('发现应用') !== -1)
      .sort((a, b) => a.querySelectorAll('*').length - b.querySelectorAll('*').length)[0] || null;
    out.found_by = btn ? 'text' : null;
  }
  out.sidebar_collapsed = !!document.querySelector('.sidebar-next--left-collapsed');
  out.btn_html = btn ? btn.outerHTML.slice(0, 200) : null;

  if (!btn) {
    dump('no-button');
    return out;
  }
  realClick(btn);
  await sleep(2500);
  const hit = Array.from(document.querySelectorAll('*'))
    .filter(el => vis(el) && /企鹅教师助手|美图设计室|发现应用/.test(T(el)))
    .map(el => ({ t: T(el), tag: el.tagName.toLowerCase(), cls: el.className.toString().slice(0, 90) }));
  dump('after-open-switcher', { hits: hit.slice(0, 16) });
  return out;
})()
