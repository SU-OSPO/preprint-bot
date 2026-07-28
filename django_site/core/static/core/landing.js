// Landing page live feed: streams real arXiv papers into #lp-feed, ranked by a
// (demo) match score. Loaded with `defer`, so the DOM is ready on execution.
(function () {
  // Real arXiv papers — titles link to their live abstract pages. Scores are
  // illustrative (this panel previews the product UI).
  var POOL = [
    { id: "2512.20963", title: "Generalization of Diffusion Models Arises with a Balanced Representation Space", authors: "Zekai Zhang et al.", cats: "cs.LG", score: 0.63 },
    { id: "2502.01684", title: "Predict, Cluster, Refine: A Joint Embedding Predictive Self-Supervised Framework for Graph Representation Learning", authors: "Srinitish Srinivasan, Omkumar CU", cats: "cs.LG", score: 0.58 },
    { id: "2510.10572", title: "Understanding Self-supervised Contrastive Learning through Supervised Objectives", authors: "Byeongchan Lee", cats: "cs.LG", score: 0.71 },
    { id: "2510.08374", title: "Contrastive Self-Supervised Learning at the Edge: An Energy Perspective", authors: "Fernanda Fam\u00e1 et al.", cats: "cs.LG", score: 0.55 },
    { id: "2512.21102", title: "Shared Representation Learning for High-Dimensional Multi-Task Forecasting under Resource Contention in Cloud-Native Backends", authors: "Zixiao Huang et al.", cats: "cs.LG", score: 0.66 },
    { id: "2503.11101", title: "A Survey on Self-supervised Contrastive Learning for Multimodal Text-Image Analysis", authors: "Asifullah Khan et al.", cats: "cs.LG", score: 0.74 },
    { id: "2409.04607", title: "Self-Supervised Contrastive Learning for Videos using Differentiable Local Alignment", authors: "Keyne Oei et al.", cats: "cs.CV", score: 0.61 },
    { id: "2205.11508", title: "Contrastive and Non-Contrastive Self-Supervised Learning Recover Global and Local Spectral Embedding Methods", authors: "Randall Balestriero et al.", cats: "cs.LG", score: 0.69 },
    { id: "2507.17454", title: "C3RL: Rethinking the Combination of Channel-independence and Channel-mixing from Representation Learning", authors: "Shusen Ma et al.", cats: "cs.LG", score: 0.64 },
    { id: "2511.08544", title: "LeJEPA: Provable and Scalable Self-Supervised Learning Without the Heuristics", authors: "Randall Balestriero, Yann LeCun", cats: "cs.LG", score: 0.77 },
    { id: "2403.09809", title: "Self-Supervised Learning for Time Series: Contrastive or Generative?", authors: "Ziyu Liu et al.", cats: "cs.LG", score: 0.60 },
    { id: "2410.05711", title: "TimeDART: A Diffusion Autoregressive Transformer for Self-Supervised Time Series Representation", authors: "Daoyu Wang et al.", cats: "cs.LG", score: 0.72 },
    { id: "2411.10087", title: "PFML: Self-Supervised Learning of Time-Series Data Without Representation Collapse", authors: "Einari Vaaras et al.", cats: "cs.LG", score: 0.57 },
    { id: "2303.01034", title: "Multi-Task Self-Supervised Time-Series Representation Learning", authors: "Heejeong Choi et al.", cats: "cs.LG", score: 0.68 },
    { id: "2405.05959", title: "Self-Supervised Learning of Time Series Representation via Diffusion Process and Imputation-Interpolation-Forecasting Mask", authors: "Zineb Senane et al.", cats: "cs.LG", score: 0.75 }
  ];
  var MAX = 5;            // papers shown at once
  var MAX_INSERTS = 15;   // stop streaming after this many total

  // Spinner + scanning counter (ambient "aliveness").
  var spinEl = document.getElementById('lp-spin');
  var countEl = document.getElementById('lp-count');
  if (spinEl) { var glyphs = ['-', '\\', '|', '/'], gi = 0; setInterval(function () { spinEl.textContent = glyphs[gi = (gi + 1) % 4]; }, 130); }
  if (countEl) { var n = 1284; setInterval(function () { n += Math.random() < 0.5 ? 1 : 2; countEl.textContent = n.toLocaleString('en-US'); }, 900); }

  var feed = document.getElementById('lp-feed');
  if (!feed) return;

  var visible = [];   // [{ p, score, el }], kept sorted high → low once full
  var poolIdx = 0;
  var inserted = 0;

  function esc(s) { var d = document.createElement('div'); d.textContent = s; return d.innerHTML; }

  function makeCard(p) {
    var card = document.createElement('div');
    card.className = 'lp-paper';
    card.innerHTML =
      '<div class="lp-paper-main">' +
        '<a class="lp-paper-title" href="https://arxiv.org/abs/' + esc(p.id) + '" target="_blank" rel="noopener noreferrer">' + esc(p.title) + '</a>' +
        '<div class="lp-paper-meta">arXiv:' + esc(p.id) + ' \u00b7 ' + esc(p.authors) + ' \u00b7 ' + esc(p.cats) + '</div>' +
        '<div class="lp-bar"><div class="lp-bar-fill"></div></div>' +
      '</div>' +
      '<div class="lp-score">' +
        '<div class="lp-score-num">0.00</div>' +
        '<div class="lp-score-label">Match</div>' +
      '</div>';
    return card;
  }

  // Count a new card's score up from 0 while its bar fills.
  function animateScore(card, target) {
    var numEl = card.querySelector('.lp-score-num');
    var barEl = card.querySelector('.lp-bar-fill');
    var start = performance.now(), dur = 850;
    (function step(now) {
      var t = Math.min(1, (now - start) / dur);
      var v = target * (1 - Math.pow(1 - t, 3));  // ease-out cubic
      numEl.textContent = v.toFixed(2);
      barEl.style.width = (v * 100) + '%';
      if (t < 1) requestAnimationFrame(step);
      else numEl.textContent = target.toFixed(2);
    })(performance.now());
  }

  function insert(p) {
    // The list is always shown in rank order; the pool's seed scores aren't
    // monotonic, so even the first five reshuffle as they slot in by rank.
    var filling = visible.length < MAX;

    var score = p.score;
    if (!filling) {
      var lowest = Math.min.apply(null, visible.map(function (v) { return v.score; }));
      if (score <= lowest) score = Math.min(0.92, lowest + 0.02 + Math.random() * 0.06);
    }

    // FLIP: remember where the current cards are before reordering.
    var firstTop = {};
    visible.forEach(function (v) { firstTop[v.p.id] = v.el.getBoundingClientRect().top; });

    var entry = { p: p, score: score, el: makeCard(p) };
    visible.push(entry);
    visible.sort(function (a, b) { return b.score - a.score; });
    var removed = visible.length > MAX ? visible.pop() : null;

    // Park the outgoing card at the end (so it isn't stranded at the top),
    // then reorder the DOM in place to match the list order.
    if (removed) feed.appendChild(removed.el);
    visible.forEach(function (v, idx) {
      if (feed.children[idx] !== v.el) feed.insertBefore(v.el, feed.children[idx] || null);
    });

    // Displaced cards glide from their old position to the new one (FLIP).
    var moveMs = 600;
    visible.forEach(function (v) {
      if (v === entry) return;
      var was = firstTop[v.p.id];
      if (was == null) return;
      var dy = was - v.el.getBoundingClientRect().top;
      if (dy) {
        v.el.animate(
          [{ transform: 'translateY(' + dy + 'px)' }, { transform: 'none' }],
          { duration: moveMs, easing: 'cubic-bezier(.2,0,0,1)' }
        );
      }
    });

    // New card holds invisible until the others have moved out of the way,
    // then fades in as its score counts up (avoids the brief collision).
    entry.el.animate(
      [{ opacity: 0, offset: 0 }, { opacity: 0, offset: 0.4 }, { opacity: 1, offset: 1 }],
      { duration: moveMs + 60, easing: 'ease', fill: 'forwards' }
    );
    animateScore(entry.el, entry.score);

    // The outgoing (lowest) card fades out where it sat.
    if (removed) {
      var wasR = firstTop[removed.p.id];
      var dyR = (wasR != null) ? wasR - removed.el.getBoundingClientRect().top : 0;
      removed.el.style.pointerEvents = 'none';
      removed.el.animate(
        [{ opacity: 0.85, transform: 'translateY(' + dyR + 'px)' }, { opacity: 0, transform: 'translateY(' + dyR + 'px)' }],
        { duration: 320, easing: 'ease' }
      ).onfinish = function () { removed.el.remove(); };
    }
  }

  // Stream papers in one at a time, skipping any already on screen.
  (function tick() {
    var tries = 0;
    var p;
    do { p = POOL[poolIdx++ % POOL.length]; tries++; }
    while (visible.some(function (v) { return v.p.id === p.id; }) && tries <= POOL.length);
    insert(p);
    inserted++;
    if (inserted >= MAX_INSERTS) return;   // stop after enough papers
    setTimeout(tick, visible.length < MAX ? 900 : 1900);
  })();
})();
