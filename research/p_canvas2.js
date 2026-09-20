(async () => {
  const out = {};
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 70);

  await closeOverlays(3);
  await openNewTask();
  await sleep(1600);

  out.sceneTabs = Array.from(document.querySelectorAll('.wb-scene-tabs__pill'))
    .filter(isVisible).map(p => ({ t: T(p), active: /--active/.test(p.className.toString()) }));

  out.scene = await setScene('设计创意');
  await sleep(2500);

  // 场景切换后，首页有哪些元素
  out.afterScene = {
    tabs: Array.from(document.querySelectorAll('.wb-scene-tabs__pill')).filter(isVisible)
            .map(p => ({ t: T(p), active: /--active/.test(p.className.toString()) })),
    placeholder: Array.from(document.querySelectorAll('[contenteditable=true], textarea'))
                   .map(e => e.getAttribute('placeholder') || e.getAttribute('data-placeholder') || null),
    chips: Array.from(document.querySelectorAll('[class*=chip], [class*=pill], [class*=tag]'))
             .filter(isVisible).map(e => T(e)).filter(t => t && t.length <= 24).slice(0, 40),
    cards: Array.from(document.querySelectorAll('[class*=card], [class*=item], [class*=template], [class*=tile]'))
             .filter(isVisible).map(e => T(e)).filter(t => t && t.length <= 30).slice(0, 40),
    classes: Array.from(new Set(Array.from(document.querySelectorAll('*'))
      .map(e => e.className && e.className.toString()).filter(Boolean)
      .flatMap(c => c.split(/\s+/))
      .filter(c => /scene|design|canvas|poster|prompt|starter|suggest/i.test(c)))).slice(0, 60),
    buttons: Array.from(document.querySelectorAll('button')).filter(isVisible).map(T).filter(Boolean).slice(0, 40)
  };

  // 是否有「网站设计/视觉海报/PPT设计」这类分类
  const cat = Array.from(document.querySelectorAll('*')).filter(isVisible)
    .filter(e => e.children.length <= 2 && /^(网站设计|视觉海报|PPT设计|海报设计|名片)$/.test(T(e)))
    .map(e => ({ t: T(e), cls: e.className.toString().slice(0, 60) }));
  out.categories = cat;

  return out;
})()
