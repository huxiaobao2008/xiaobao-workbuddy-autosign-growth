(async () => {
  closeOverlays(3); await sleep(600);
  if (!document.querySelector('.automation-main-page')) { clickSidebar('定时任务'); await sleep(3000); }
  const page = document.querySelector('.automation-main-page');
  return {
    onPage: !!page,
    txt: page ? page.innerText.replace(/\s+/g, ' ').slice(0, 1200) : document.body.innerText.replace(/\s+/g,' ').slice(0,800),
    buttons: Array.from(document.querySelectorAll('button')).filter(wbVis).map(b => wbT(b)).filter(Boolean).slice(0, 40),
    sidebarTabs: Array.from(document.querySelectorAll('.conversation-list-tab-button')).filter(wbVis).map(b => wbT(b)).slice(0,20)
  };
})
