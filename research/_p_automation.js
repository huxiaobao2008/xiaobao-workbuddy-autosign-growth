(async () => {
  const out = { parts: [] };
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const vis = el => { const r = el.getBoundingClientRect(); return r.width > 8 && r.height > 8; };
  const norm = s => (s || '').replace(/\s+/g, '');

  function clickSidebar(t) {
    const b = Array.from(document.querySelectorAll('.conversation-list-tab-button'))
      .find(e => norm(T(e)) === norm(t));
    if (!b) return null;
    realClick(b); return T(b);
  }

  // 清掉可能残留的弹窗
  for (let i = 0; i < 4; i++) {
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    await sleep(400);
  }

  clickSidebar('定时任务');
  await sleep(2500);
  const add = Array.from(document.querySelectorAll('button')).filter(vis).find(e => T(e).indexOf('添加定时任务') !== -1);
  if (add) { realClick(add); await sleep(2600); }

  const modal = document.querySelector('.wb-modal');
  out.modalFound = !!modal;
  if (modal) {
    out.fields = [];
    modal.querySelectorAll('input, textarea, [contenteditable=true], select').forEach(el => {
      out.fields.push({
        tag: el.tagName.toLowerCase(),
        type: el.type || '',
        ph: el.placeholder || '',
        val: (el.value !== undefined ? el.value : T(el)).slice(0, 40),
        cls: el.className.toString().slice(0, 90)
      });
    });
    out.buttons = [];
    modal.querySelectorAll('button').forEach(b => {
      if (!vis(b)) return;
      out.buttons.push({ t: T(b).slice(0, 24), cls: b.className.toString().slice(0, 80) });
    });
    // 关键区块的 html 片段（帮助定位「提示词」输入区）
    out.html = modal.innerHTML.replace(/\s+/g, ' ').slice(0, 2600);
  }
  return out;
})()
