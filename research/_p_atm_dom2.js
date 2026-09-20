(async () => {
  closeOverlays(3); await sleep(600);
  if (!document.querySelector('.automation-main-page')) { clickSidebar('定时任务'); await sleep(3000); }
  let add = null;
  for (let i = 0; i < 12 && !add; i++) { add = findBtn(document, '添加定时任务'); if (!add) await sleep(700); }
  if (!add) return { err: '没有添加按钮' };
  realClick(add); await sleep(3000);
  const modal = document.querySelector('.wb-modal');
  if (!modal) return { err: '对话框没开' };
  const out = {};
  out.inputs = Array.from(modal.querySelectorAll('input,textarea,[contenteditable=true]'))
    .map(e => ({ tag: e.tagName, cls: String(e.className).slice(0, 70),
                 ph: e.placeholder || null,
                 val: (e.value !== undefined ? e.value : (e.innerText||'')).slice(0, 50),
                 ro: !!e.readOnly, dis: !!e.disabled }));
  out.buttons = Array.from(modal.querySelectorAll('button')).map(b => ({
    t: (b.innerText||'').trim().slice(0, 16), cls: String(b.className).slice(0, 90),
    dis: !!b.disabled, aria: b.getAttribute('aria-disabled') }));
  out.triggers = Array.from(modal.querySelectorAll('[class*=trigger]'))
    .map(e => ({ cls: String(e.className).slice(0, 80), t: (e.innerText||'').replace(/\s+/g,' ').trim().slice(0, 70) }));
  // 找 footer/操作区
  const foot = Array.from(modal.querySelectorAll('div')).filter(d => d.querySelector('button') &&
    (d.innerText||'').indexOf('确定') >= 0).sort((a,b)=>a.querySelectorAll('*').length-b.querySelectorAll('*').length)[0];
  out.footerCls = foot ? String(foot.className).slice(0, 90) : null;
  return out;
})
