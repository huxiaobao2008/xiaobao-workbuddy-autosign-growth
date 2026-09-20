(() => {
  const m = document.querySelector('.wb-modal');
  if (!m) return { modal: false };
  const ed = m.querySelector('[contenteditable=true]');
  if (!ed) return { modal: true, err: 'no editable' };
  const attrs = {};
  for (const a of ed.attributes) attrs[a.name] = a.value.slice(0, 120);
  return {
    tag: ed.tagName,
    cls: String(ed.className),
    attrs: attrs,
    childTags: Array.from(ed.children).map(c => c.tagName + '.' + String(c.className).slice(0, 40)),
    html: ed.innerHTML.slice(0, 800),
    innerText: (ed.innerText || '').slice(0, 120),
    // React fiber 信息
    reactKeys: Object.keys(ed).filter(k => k.startsWith('__react')).slice(0, 10),
    parentCls: ed.parentElement ? String(ed.parentElement.className).slice(0, 90) : null,
    grandCls: ed.parentElement && ed.parentElement.parentElement
      ? String(ed.parentElement.parentElement.className).slice(0, 90) : null,
    // 兄弟节点里是否有隐藏 textarea / input
    sibInputs: Array.from(m.querySelectorAll('textarea')).map(t => ({ cls: String(t.className).slice(0, 60), v: (t.value || '').slice(0, 40) }))
  };
})
