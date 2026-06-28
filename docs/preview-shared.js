// Shared gallery logic for the three design previews. Each preview page calls
// initGallery(opts) after defining #search, #sort, #grid, #count, #empty.
//   opts.indexed : prefix each card with its catalog index (datasheet variant)
//   opts.pad     : zero-pad width for that index (museum variant uses 4)
function initGallery(opts) {
  opts = opts || {};
  let catalog = { objects: [] };
  const $search = document.getElementById('search');
  const $sort = document.getElementById('sort');
  const $grid = document.getElementById('grid');
  const $empty = document.getElementById('empty');
  const $count = document.getElementById('count');

  function escapeHtml(s) {
    return s.replace(/[&<>"']/g, c => (
      { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }
  function highlight(text, q) {
    if (!q) return escapeHtml(text);
    const i = text.toLowerCase().indexOf(q);
    if (i < 0) return escapeHtml(text);
    return escapeHtml(text.slice(0, i)) +
      '<mark>' + escapeHtml(text.slice(i, i + q.length)) + '</mark>' +
      escapeHtml(text.slice(i + q.length));
  }

  function getFiltered() {
    const q = $search.value.toLowerCase().trim();
    let items = catalog.objects.filter(o =>
      !q || o.label.toLowerCase().includes(q) || o.id.toLowerCase().includes(q));
    const dir = $sort.value === 'za' ? -1 : 1;
    items.sort((a, b) => dir * a.label.localeCompare(b.label));
    return items;
  }

  function render() {
    const q = $search.value.toLowerCase().trim();
    const items = getFiltered();
    if ($count) $count.textContent = q
      ? `${items.length} / ${catalog.objects.length}`
      : `${catalog.objects.length} objects`;
    $grid.innerHTML = '';
    if (!items.length) { $empty.style.display = 'block'; return; }
    $empty.style.display = 'none';

    const frag = document.createDocumentFragment();
    items.forEach((obj, i) => {
      const card = document.createElement('div');
      card.className = 'card';
      card.tabIndex = 0;
      const go = () => { window.location.href = `viewer.html?id=${encodeURIComponent(obj.id)}`; };
      card.onclick = go;
      card.onkeydown = (e) => { if (e.key === 'Enter') go(); };

      const idx = opts.indexed
        ? `<span class="idx">#${String(i + 1)}</span>`
        : (opts.pad ? `<span class="num">${String(i + 1).padStart(opts.pad, '0')}</span>` : '');
      const thumb = obj.thumb
        ? `<img src="objects/${obj.id}/thumb.png" alt="${escapeHtml(obj.label)}" loading="lazy" onerror="this.parentElement.innerHTML='<div class=placeholder>&#9645;</div>'">`
        : '<div class="placeholder">&#9645;</div>';

      // Layout differs slightly per skin but all share .frame/.label/.id classes.
      if (opts.indexed) {
        card.innerHTML =
          `<div class="frame">${thumb}</div>` +
          `<div class="row"><span class="label">${highlight(obj.label, q)}</span>${idx}</div>` +
          `<div class="id">${highlight(obj.id, q)}</div>`;
      } else if (opts.pad) {
        card.innerHTML =
          `<div class="frame">${thumb}</div>` +
          `<div class="cap"><span class="label">${highlight(obj.label, q)}</span>${idx}</div>` +
          `<div class="id">${highlight(obj.id, q)}</div>`;
      } else {
        card.innerHTML =
          `<div class="frame">${thumb}</div>` +
          `<div class="info"><div class="label">${highlight(obj.label, q)}</div>` +
          `<div class="id">${highlight(obj.id, q)}</div></div>`;
      }
      frag.appendChild(card);
    });
    $grid.appendChild(frag);
  }

  $search.addEventListener('input', render);
  $sort.addEventListener('change', render);
  document.addEventListener('keydown', (e) => {
    if (e.key === '/' && document.activeElement !== $search) { e.preventDefault(); $search.focus(); }
    else if (e.key === 'Escape' && document.activeElement === $search) { $search.value = ''; render(); $search.blur(); }
  });

  fetch('catalog.json').then(r => r.json()).then(c => { catalog = c; render(); })
    .catch(() => { $empty.textContent = 'Failed to load catalog.json'; $empty.style.display = 'block'; });
}
