// ── Category picker: a tab per preprint source ──────────────
// Each enabled source contributes a collapsible category tree. Category codes
// are only unique within a source, so every checkbox carries a "source:code"
// token and the hidden input submits those.
//
// With one source registered the tab bar is hidden and the tree renders flat.

const _sourcesEl = document.getElementById('cat-sources-data');
const _initialEl = document.getElementById('cat-initial-data');

// [{name, label, tree}] in registry order.
const SOURCES = _sourcesEl ? JSON.parse(_sourcesEl.textContent) : [];
const MULTI_SOURCE = SOURCES.length > 1;

// Prefer the server-rendered selection; fall back to the hidden input so
// selections survive a form re-render (e.g., a validation error).
let INITIAL = _initialEl ? JSON.parse(_initialEl.textContent) : [];
if (INITIAL.length === 0) {
  const hiddenEl = document.getElementById('id_categories');
  const hidden = hiddenEl ? hiddenEl.value.trim() : '';
  if (hidden) INITIAL = hidden.split(',').map(s => s.trim()).filter(Boolean);
}
const initialSet = new Set(INITIAL);

/* Token the server parses back into {source: [codes]}. Split on the first
   colon only, since a source's own codes may contain one. */
function token(sourceName, code) {
  return sourceName + ':' + code;
}

function sourceByName(name) {
  return SOURCES.find(s => s.name === name);
}

function sourceLabelOf(name) {
  const s = sourceByName(name);
  return (s && s.label) || name;
}

/* Sources this profile starts with: any with a pre-selected category, else
   just the first registered one so the form is never empty. */
function initialSourceNames() {
  const named = SOURCES
    .map(s => s.name)
    .filter(name => INITIAL.some(t => t.startsWith(name + ':')));
  if (named.length) return named;
  return SOURCES.length ? [SOURCES[0].name] : [];
}

const added = initialSourceNames();
let activeSource = added[0] || null;

/* ── Build the tree ────────────────────────────────────────── */

function hasSelectedDescendant(node, sourceName) {
  if (!node.children || !node.children.length) {
    return initialSet.has(token(sourceName, node.value));
  }
  return node.children.some(c => hasSelectedDescendant(c, sourceName));
}

function buildTree(nodes, container, sourceName) {
  nodes.forEach(node => {
    const hasChildren = node.children && node.children.length > 0;
    const div = document.createElement('div');
    div.style.marginLeft = '1.25rem';

    if (hasChildren) {
      const details = document.createElement('details');
      // Expand groups that have any pre-selected descendant (recursive)
      details.open = hasSelectedDescendant(node, sourceName);
      details.className = 'cat-group';

      const summary = document.createElement('summary');
      summary.style.cssText = 'cursor:pointer; font-weight:600; font-size:.88rem; margin:.25rem 0; user-select:none;';
      summary.textContent = node.label;
      details.appendChild(summary);

      const inner = document.createElement('div');
      buildTree(node.children, inner, sourceName);
      details.appendChild(inner);
      div.appendChild(details);
    } else {
      const value = token(sourceName, node.value);
      const label = document.createElement('label');
      label.style.cssText = 'display:flex; align-items:center; gap:.5rem; padding:.3rem 0; font-size:.85rem; cursor:pointer;';
      label.className = 'cat-leaf';
      label.dataset.value = value;
      label.dataset.search = (node.label + ' ' + node.value).toLowerCase();

      const cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.value = value;
      cb.className = 'cat-cb';
      cb.dataset.source = sourceName;
      cb.dataset.code = node.value;
      cb.style.cssText = 'flex-shrink:0; width:1rem; height:1rem; margin:0;';
      if (initialSet.has(value)) cb.checked = true;
      cb.addEventListener('change', () => { syncHidden(); renderTags(); });
      label.appendChild(cb);
      label.appendChild(document.createTextNode(node.label));
      div.appendChild(label);
    }

    container.appendChild(div);
  });
}

/* ── Tabs and panels ──────────────────────────────────────── */

function panelFor(sourceName) {
  return document.getElementById('cat-panel-' + sourceName);
}

function ensurePanel(sourceName) {
  let panel = panelFor(sourceName);
  if (panel) return panel;

  const source = sourceByName(sourceName);
  if (!source) return null;

  panel = document.createElement('div');
  panel.className = 'tab-panel';
  panel.id = 'cat-panel-' + sourceName;
  panel.setAttribute('role', 'tabpanel');
  panel.setAttribute('aria-labelledby', 'cat-tab-' + sourceName);
  buildTree(source.tree, panel, sourceName);
  document.getElementById('cat-source-panels').appendChild(panel);
  return panel;
}

function setActiveSource(sourceName) {
  activeSource = sourceName;
  document.querySelectorAll('#cat-source-panels .tab-panel').forEach(p => {
    p.classList.toggle('active', p.id === 'cat-panel-' + sourceName);
  });
  document.querySelectorAll('#cat-source-tabs .tab-btn').forEach(b => {
    const on = b.dataset.source === sourceName;
    b.classList.toggle('active', on);
    b.setAttribute('aria-selected', on ? 'true' : 'false');
  });
  // The search box is shared but filters one tree at a time; say which.
  const input = document.getElementById('cat-search-input');
  if (input && !input.value) {
    input.placeholder = MULTI_SOURCE
      ? 'Search ' + sourceLabelOf(sourceName) + ' categories…'
      : 'Search categories…';
  }
}

/* Drop a source: clear its selections, then remove its tab and panel. */
function removeSource(sourceName) {
  const panel = panelFor(sourceName);
  if (panel) {
    panel.querySelectorAll('.cat-cb:checked').forEach(cb => { cb.checked = false; });
    panel.remove();
  }
  /* Forget the server-rendered selection too. */
  [...initialSet]
    .filter(t => t.startsWith(sourceName + ':'))
    .forEach(t => initialSet.delete(t));

  const i = added.indexOf(sourceName);
  if (i !== -1) added.splice(i, 1);
  // The remove control is hidden at one source, so this is belt-and-braces —
  // but a fallback tab still needs its panel built before it can be shown.
  if (!added.length && SOURCES.length) added.push(SOURCES[0].name);
  added.forEach(name => ensurePanel(name));

  syncHidden();
  renderTags();
  renderTabs();
  setActiveSource(added.includes(activeSource) ? activeSource : added[0]);
}

function addSource(sourceName) {
  if (added.includes(sourceName) || !sourceByName(sourceName)) return;
  added.push(sourceName);
  ensurePanel(sourceName);
  renderTabs();
  setActiveSource(sourceName);
}

function renderTabs() {
  const bar = document.getElementById('cat-source-tabs');
  if (!MULTI_SOURCE) {
    bar.hidden = true;
    return;
  }
  bar.hidden = false;
  bar.innerHTML = '';

  added.forEach(name => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'tab-btn';
    btn.id = 'cat-tab-' + name;
    btn.dataset.source = name;
    btn.setAttribute('role', 'tab');
    btn.setAttribute('aria-controls', 'cat-panel-' + name);
    btn.addEventListener('click', () => setActiveSource(name));

    const text = document.createElement('span');
    text.textContent = sourceLabelOf(name);
    btn.appendChild(text);

    // Match count while searching, so hits on other tabs are not hidden.
    const count = document.createElement('span');
    count.className = 'cat-tab-count';
    count.style.cssText = 'margin-left:.3rem; opacity:.7; font-size:.78rem;';
    btn.appendChild(count);

    // Add button and listener to remove a source tab.
    if (added.length > 1) {
      const x = document.createElement('span');
      x.textContent = '×';
      x.setAttribute('role', 'button');
      x.setAttribute('aria-label', 'Remove ' + sourceLabelOf(name));
      x.title = 'Remove ' + sourceLabelOf(name);
      x.style.cssText = 'margin-left:.4rem; opacity:.6; cursor:pointer;';
      x.addEventListener('click', e => { e.stopPropagation(); removeSource(name); });
      btn.appendChild(x);
    }

    bar.appendChild(btn);
  });

  const remaining = SOURCES.filter(s => !added.includes(s.name));
  if (remaining.length) {
    /* A native select keeps this accessible and needs no popup code; the
       first option acts as the button label. */
    const wrap = document.createElement('div');
    wrap.className = 'form-group';
    wrap.id = 'cat-add-source-wrap';
    wrap.style.cssText = 'margin:0 0 .25rem .5rem; align-self:center;';

    const picker = document.createElement('select');
    picker.id = 'cat-add-source';
    picker.setAttribute('aria-label', 'Add a preprint source');
    const placeholder = document.createElement('option');
    placeholder.value = '';
    placeholder.textContent = '+ Add a source';
    picker.appendChild(placeholder);
    remaining.forEach(s => {
      const opt = document.createElement('option');
      opt.value = s.name;
      opt.textContent = s.label;
      picker.appendChild(opt);
    });
    picker.addEventListener('change', () => {
      const chosen = picker.value;
      picker.value = '';
      if (chosen) addSource(chosen);
    });

    wrap.appendChild(picker);
    bar.appendChild(wrap);
  }
}

/* ── Sync hidden input ─────────────────────────────────────── */

function syncHidden() {
  const checked = [...document.querySelectorAll('.cat-cb:checked')].map(c => c.value);
  document.getElementById('id_categories').value = checked.join(',');
}

/* ── Tag rendering ─────────────────────────────────────────── */

function renderTags() {
  const tagsEl = document.getElementById('cat-tags');
  const checked = [...document.querySelectorAll('.cat-cb:checked')];
  tagsEl.innerHTML = '';
  checked.forEach(cb => {
    const code = cb.dataset.code;
    /* Codes repeat across servers, so name the source when there is more
       than one. */
    const text = MULTI_SOURCE
      ? sourceLabelOf(cb.dataset.source) + ' · ' + code
      : code;

    const tag = document.createElement('span');
    tag.className = 'tag';
    tag.style.cssText = 'display:inline-flex; align-items:center; gap:.2rem; font-size:.78rem; padding:.1rem .4rem;';
    tag.textContent = text;

    const x = document.createElement('button');
    x.type = 'button';
    x.style.cssText = 'background:none; border:none; cursor:pointer; font-size:.85rem; padding:0; line-height:1; color:inherit; opacity:.7;';
    x.textContent = '×';
    x.title = 'Remove ' + text;
    x.addEventListener('click', e => {
      e.stopPropagation();
      cb.checked = false;
      cb.dispatchEvent(new Event('change'));
    });
    tag.appendChild(x);
    tagsEl.appendChild(tag);
  });

  // Update placeholder visibility
  const input = document.getElementById('cat-search-input');
  input.placeholder = checked.length > 0 ? '' : 'Search categories…';
}

/* ── Search/filter ─────────────────────────────────────────── */

/* Count matches per added source so inactive tabs can advertise their hits. */
function updateTabCounts(q) {
  document.querySelectorAll('#cat-source-tabs .tab-btn').forEach(btn => {
    const countEl = btn.querySelector('.cat-tab-count');
    if (!countEl) return;
    if (!q) { countEl.textContent = ''; return; }
    const panel = panelFor(btn.dataset.source);
    const hits = panel
      ? [...panel.querySelectorAll('.cat-leaf')].filter(l => l.dataset.search.includes(q)).length
      : 0;
    countEl.textContent = '(' + hits + ')';
  });
}

function filterCategories(query) {
  const q = query.toLowerCase().trim();
  // Only the visible tree is filtered; other tabs report counts instead.
  const scope = panelFor(activeSource) || document;
  const leaves = scope.querySelectorAll('.cat-leaf');
  const groups = scope.querySelectorAll('.cat-group');

  if (!q) {
    // Show everything, restore collapse state
    leaves.forEach(l => l.style.display = 'flex');
    groups.forEach(g => {
      g.style.display = '';
      // Collapse groups that have no checked children
      const hasChecked = g.querySelector('.cat-cb:checked');
      if (!hasChecked) g.open = false;
    });
    updateTabCounts('');
    return;
  }

  // Filter leaves
  leaves.forEach(l => {
    const match = l.dataset.search.includes(q);
    l.style.display = match ? 'flex' : 'none';
  });

  // Show/hide groups based on whether they have visible leaves
  groups.forEach(g => {
    const visibleLeaves = g.querySelectorAll('.cat-leaf:not([style*="display: none"])');
    if (visibleLeaves.length > 0) {
      g.style.display = '';
      g.open = true;  // expand to show matches
    } else {
      g.style.display = 'none';
    }
  });

  updateTabCounts(q);
}

/* ── Init ──────────────────────────────────────────────────── */

document.addEventListener('DOMContentLoaded', () => {
  added.forEach(name => ensurePanel(name));
  renderTabs();
  if (activeSource) setActiveSource(activeSource);
  syncHidden();
  renderTags();

  // Wire up search input
  const searchInput = document.getElementById('cat-search-input');
  searchInput.addEventListener('input', () => {
    filterCategories(searchInput.value);
  });

  // Clear search on Escape
  searchInput.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
      searchInput.value = '';
      filterCategories('');
    }
    // Prevent form submit on Enter inside search
    if (e.key === 'Enter') {
      e.preventDefault();
    }
  });
});
