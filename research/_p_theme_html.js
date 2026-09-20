(async () => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const out = { cells: [] };
  document.querySelectorAll('.appearance-card-cell').forEach(el => {
    out.cells.push({
      name: T(el),
      cls: el.className.toString(),
      html: el.outerHTML.replace(/\s+/g, ' ').slice(0, 420)
    });
  });
  out.count = out.cells.length;
  return out;
})()
