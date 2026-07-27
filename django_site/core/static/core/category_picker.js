// ── Category picker with search and collapsible groups ──────
// Renders ARXIV_CATEGORY_TREE as nested <details> with checkboxes.
// Groups are collapsed by default; groups with any pre-selected
// descendant leaf are expanded (recursive). A search input filters
// categories and shows selected ones as removable tags.

const _catTreeEl = document.getElementById('category-tree');
const TREE = JSON.parse(_catTreeEl.dataset.tree);
// Prefer data-initial; fall back to the hidden input so selections survive a
// server-side form re-render (e.g., a validation error).
let INITIAL = JSON.parse(_catTreeEl.dataset.initial || '[]');
if (INITIAL.length === 0) {
  const hiddenEl = document.getElementById('id_categories');
  const hidden = hiddenEl ? hiddenEl.value.trim() : '';
  if (hidden) INITIAL = hidden.split(',').map(s => s.trim()).filter(Boolean);
}
const initialSet = new Set(INITIAL);

/* ── Build the tree ────────────────────────────────────────── */

function hasSelectedDescendant(node) {
  if (!node.children || !node.children.length) return initialSet.has(node.value);
  return node.children.some(c => hasSelectedDescendant(c));
}

function buildTree(nodes, container) {
  nodes.forEach(node => {
    const hasChildren = node.children && node.children.length > 0;
    const div = document.createElement('div');
    div.style.marginLeft = '1.25rem';

    if (hasChildren) {
      const details = document.createElement('details');
      // Expand groups that have any pre-selected descendant (recursive)
      const hasSelected = hasSelectedDescendant(node);
      details.open = hasSelected;
      details.className = 'cat-group';

      const summary = document.createElement('summary');
      summary.style.cssText = 'cursor:pointer; font-weight:600; font-size:.88rem; margin:.25rem 0; user-select:none;';
      summary.textContent = node.label;
      details.appendChild(summary);

      const inner = document.createElement('div');
      buildTree(node.children, inner);
      details.appendChild(inner);
      div.appendChild(details);
    } else {
      const label = document.createElement('label');
      label.style.cssText = 'display:flex; align-items:center; gap:.5rem; padding:.3rem 0; font-size:.85rem; cursor:pointer;';
      label.className = 'cat-leaf';
      label.dataset.value = node.value;
      label.dataset.search = (node.label + ' ' + node.value).toLowerCase();

      const cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.value = node.value;
      cb.className = 'cat-cb';
      cb.style.cssText = 'flex-shrink:0; width:1rem; height:1rem; margin:0;';
      if (initialSet.has(node.value)) cb.checked = true;
      cb.addEventListener('change', () => { syncHidden(); renderTags(); });
      label.appendChild(cb);
      label.appendChild(document.createTextNode(node.label));
      div.appendChild(label);
    }

    container.appendChild(div);
  });
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
    const tag = document.createElement('span');
    tag.className = 'tag';
    tag.style.cssText = 'display:inline-flex; align-items:center; gap:.2rem; font-size:.78rem; padding:.1rem .4rem;';
    tag.textContent = cb.value;

    const x = document.createElement('button');
    x.type = 'button';
    x.style.cssText = 'background:none; border:none; cursor:pointer; font-size:.85rem; padding:0; line-height:1; color:inherit; opacity:.7;';
    x.textContent = '\u00d7';
    x.title = 'Remove ' + cb.value;
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
  input.placeholder = checked.length > 0 ? '' : 'Search categories\u2026';
}

/* ── Search/filter ─────────────────────────────────────────── */

function filterCategories(query) {
  const q = query.toLowerCase().trim();
  const leaves = document.querySelectorAll('.cat-leaf');
  const groups = document.querySelectorAll('.cat-group');

  if (!q) {
    // Show everything, restore collapse state
    leaves.forEach(l => l.style.display = 'flex');
    groups.forEach(g => {
      g.style.display = '';
      // Collapse groups that have no checked children
      const hasChecked = g.querySelector('.cat-cb:checked');
      if (!hasChecked) g.open = false;
    });
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
}

/* ── Init ──────────────────────────────────────────────────── */

document.addEventListener('DOMContentLoaded', () => {
  const root = document.getElementById('category-tree');
  buildTree(TREE, root);
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
