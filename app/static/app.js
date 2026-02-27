(function () {
  var activeSource = null;
  var activeJobScope = null;
  var activeSingleReelId = null;
  var activeSingleTrigger = null;

  document.addEventListener('click', function (e) {
    var transcriptBtn = e.target.closest('.transcript-toggle');
    if (transcriptBtn) {
      var id = transcriptBtn.getAttribute('data-transcript');
      if (!id) return;
      var panel = document.getElementById(id);
      if (!panel) return;
      panel.classList.toggle('hidden');
      var readLabel = transcriptBtn.getAttribute('data-read-label') || 'Read';
      var hideLabel = transcriptBtn.getAttribute('data-hide-label') || 'Hide';
      transcriptBtn.textContent = panel.classList.contains('hidden') ? readLabel : hideLabel;
      return;
    }

    var actionBtn = e.target.closest('.job-trigger');
    if (!actionBtn) return;

    var action = actionBtn.getAttribute('data-action');
    if (!action) return;

    if (action === 'generate-reel' || action === 'regenerate-reel') {
      var reelId = actionBtn.getAttribute('data-reel-id');
      if (!reelId) return;
      startJob('/api/reels/' + reelId + '/generate', action === 'regenerate-reel', {
        scope: 'single',
        reelId: reelId,
        triggerEl: actionBtn
      });
      return;
    }

    if (action === 'generate-all' || action === 'regenerate-all') {
      var profileId = actionBtn.getAttribute('data-profile-id');
      if (!profileId) return;
      startJob('/api/profiles/' + profileId + '/generate-all', action === 'regenerate-all', {
        scope: 'batch'
      });
    }
  });

  var dashboard = document.querySelector('[data-dashboard-page="true"]');
  if (!dashboard) return;

  var profileSearchForm = document.getElementById('profile-search-form');
  var profileSearchButton = document.getElementById('profile-search-button');
  var searchLoader = document.getElementById('search-loader');

  var statusText = document.getElementById('status-text');
  var statusMeta = document.getElementById('status-meta');
  var statusBar = document.getElementById('status-bar');
  var statusPill = document.getElementById('status-pill');

  var reelList = document.getElementById('reel-list');
  var emptyState = document.getElementById('empty-state');
  var searchInput = document.getElementById('search-input');
  var sortSelect = document.getElementById('sort-select');

  if (profileSearchForm) {
    profileSearchForm.addEventListener('submit', function (event) {
      if (profileSearchForm.dataset.submitting === '1') {
        event.preventDefault();
        return;
      }

      profileSearchForm.dataset.submitting = '1';
      if (profileSearchButton) {
        profileSearchButton.disabled = true;
        profileSearchButton.textContent = 'Searching...';
      }
      if (searchLoader) {
        searchLoader.classList.remove('hidden');
      }
      updateStatus('Fetching reels...', 'Loading profile metadata and thumbnails.', 10, 'working');
    });
  }

  function updateStatus(message, meta, percent, pill) {
    if (statusText && message) statusText.textContent = message;
    if (statusMeta && meta !== undefined) statusMeta.textContent = meta || '';
    if (statusBar && typeof percent === 'number') statusBar.style.width = percent + '%';
    if (statusPill && pill) statusPill.textContent = pill;
  }

  function setCardLoading(reelId, loading, triggerEl) {
    if (!reelId) return;
    var card = document.getElementById('reel-card-' + reelId);
    if (!card) return;

    card.classList.toggle('reel-card-loading', !!loading);
    var actionRow = card.querySelector('.reel-actions');
    var statusBadge = actionRow ? actionRow.querySelector('.status') : null;
    var buttons = card.querySelectorAll('.job-trigger[data-reel-id="' + reelId + '"]');

    if (loading) {
      buttons.forEach(function (btn) {
        btn.disabled = true;
      });
      if (triggerEl) {
        triggerEl.dataset.originalText = triggerEl.textContent;
        triggerEl.textContent = 'Generating...';
      }
      if (statusBadge) {
        statusBadge.textContent = 'processing';
        statusBadge.classList.remove('status-pending', 'status-completed', 'status-failed', 'status-skipped');
        statusBadge.classList.add('status-processing');
      }
      if (actionRow && !actionRow.querySelector('.reel-inline-loader')) {
        var loader = document.createElement('span');
        loader.className = 'reel-inline-loader';
        loader.innerHTML = '<span class=\"inline-spinner\" aria-hidden=\"true\"></span><span>Generating...</span>';
        actionRow.appendChild(loader);
      }
      return;
    }

    buttons.forEach(function (btn) {
      btn.disabled = false;
      if (btn.dataset.originalText) {
        btn.textContent = btn.dataset.originalText;
        delete btn.dataset.originalText;
      }
    });
    var existingLoader = actionRow ? actionRow.querySelector('.reel-inline-loader') : null;
    if (existingLoader) {
      existingLoader.remove();
    }
  }

  function getCards() {
    return Array.prototype.slice.call(reelList ? reelList.querySelectorAll('.reel-card') : []);
  }

  function applyFilter() {
    if (!searchInput || !reelList) return;
    var term = (searchInput.value || '').trim().toLowerCase();
    var cards = getCards();
    var visible = 0;
    cards.forEach(function (card) {
      var text = (card.textContent || '').toLowerCase();
      var match = !term || text.indexOf(term) !== -1;
      card.style.display = match ? '' : 'none';
      if (match) visible += 1;
    });

    if (emptyState) {
      if (visible === 0) {
        emptyState.textContent = term ? 'No reels match this search.' : 'No reels found for this profile.';
        emptyState.style.display = '';
      } else {
        emptyState.style.display = 'none';
      }
    }
  }

  function applySort() {
    if (!sortSelect || !reelList) return;
    var cards = getCards();
    var sort = sortSelect.value || 'date_desc';

    function compareTitle(a, b, dir) {
      var aVal = (a.getAttribute('data-title') || '').toLowerCase();
      var bVal = (b.getAttribute('data-title') || '').toLowerCase();
      if (!aVal && !bVal) return 0;
      if (!aVal) return 1;
      if (!bVal) return -1;
      if (aVal < bVal) return dir === 'asc' ? -1 : 1;
      if (aVal > bVal) return dir === 'asc' ? 1 : -1;
      return 0;
    }

    function compareDate(a, b, dir) {
      var aVal = a.getAttribute('data-date') || '';
      var bVal = b.getAttribute('data-date') || '';
      if (!aVal && !bVal) return 0;
      if (!aVal) return 1;
      if (!bVal) return -1;
      var aTs = Date.parse(aVal) || 0;
      var bTs = Date.parse(bVal) || 0;
      return dir === 'asc' ? aTs - bTs : bTs - aTs;
    }

    function compareViews(a, b) {
      var aVal = parseInt(a.getAttribute('data-views') || '0', 10);
      var bVal = parseInt(b.getAttribute('data-views') || '0', 10);
      return bVal - aVal;
    }

    cards.sort(function (a, b) {
      if (sort === 'title_asc') return compareTitle(a, b, 'asc');
      if (sort === 'title_desc') return compareTitle(a, b, 'desc');
      if (sort === 'views_desc') return compareViews(a, b);
      if (sort === 'date_asc') return compareDate(a, b, 'asc');
      return compareDate(a, b, 'desc');
    });

    cards.forEach(function (card) {
      reelList.appendChild(card);
    });
  }

  function upsertReelCard(reelId, html) {
    if (!reelList) return;
    var wrapper = document.createElement('div');
    wrapper.innerHTML = html;
    var nextCard = wrapper.firstElementChild;
    if (!nextCard) return;

    var existing = document.getElementById('reel-card-' + reelId);
    if (existing) {
      existing.replaceWith(nextCard);
    } else {
      reelList.appendChild(nextCard);
    }

    applySort();
    applyFilter();
  }

  function openStream(jobId, options) {
    options = options || {};
    activeJobScope = options.scope || 'batch';
    activeSingleReelId = activeJobScope === 'single' ? options.reelId : null;
    activeSingleTrigger = activeJobScope === 'single' ? (options.triggerEl || null) : null;

    if (activeSource) {
      activeSource.close();
      activeSource = null;
    }

    activeSource = new EventSource('/api/stream/' + jobId);
    if (activeJobScope !== 'single') {
      updateStatus('Processing started', 'Job #' + jobId, 0, 'working');
    }

    activeSource.onmessage = function (event) {
      var data;
      try {
        data = JSON.parse(event.data);
      } catch (err) {
        return;
      }

      if (data.type === 'progress' && activeJobScope !== 'single') {
        updateStatus(data.message || 'Working...', data.meta || '', data.percent || 0, 'working');
      }

      if (data.type === 'reel_update') {
        upsertReelCard(data.reel_id, data.html || '');
        if (activeJobScope === 'single' && String(data.reel_id) === String(activeSingleReelId)) {
          activeSingleReelId = null;
          activeSingleTrigger = null;
        }
      }

      if (data.type === 'complete') {
        if (activeJobScope !== 'single') {
          updateStatus(data.message || 'Complete', 'Success: ' + (data.success || 0) + ', Failed: ' + (data.failed || 0) + ', Skipped: ' + (data.skipped || 0), 100, 'done');
        } else if (activeSingleReelId) {
          setCardLoading(activeSingleReelId, false, activeSingleTrigger);
          activeSingleReelId = null;
          activeSingleTrigger = null;
        }
        activeSource.close();
        activeSource = null;
        activeJobScope = null;
      }

      if (data.type === 'error') {
        if (activeJobScope !== 'single') {
          updateStatus('Error', data.message || 'Processing failed', 100, 'error');
        } else if (activeSingleReelId) {
          setCardLoading(activeSingleReelId, false, activeSingleTrigger);
          activeSingleReelId = null;
          activeSingleTrigger = null;
        }
        activeSource.close();
        activeSource = null;
        activeJobScope = null;
      }
    };

    activeSource.onerror = function () {
      if (activeJobScope !== 'single') {
        updateStatus('Error', 'Connection lost during stream.', 100, 'error');
      } else if (activeSingleReelId) {
        setCardLoading(activeSingleReelId, false, activeSingleTrigger);
        activeSingleReelId = null;
        activeSingleTrigger = null;
      }
      if (activeSource) {
        activeSource.close();
        activeSource = null;
      }
      activeJobScope = null;
    };
  }

  function startJob(url, regenerate, options) {
    options = options || {};
    if (options.scope === 'single' && options.reelId) {
      setCardLoading(options.reelId, true, options.triggerEl || null);
    } else {
      updateStatus('Queueing job...', '', 0, 'working');
    }

    fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ regenerate: regenerate ? 1 : 0 })
    })
      .then(function (res) {
        if (!res.ok) throw new Error('Request failed');
        return res.json();
      })
      .then(function (data) {
        if (!data || !data.job_id) throw new Error('Missing job id');
        openStream(data.job_id, options);
      })
      .catch(function (err) {
        if (options.scope === 'single' && options.reelId) {
          setCardLoading(options.reelId, false, options.triggerEl || null);
        } else {
          updateStatus('Error', err.message || 'Failed to start job', 100, 'error');
        }
      });
  }

  if (searchInput) {
    searchInput.addEventListener('input', applyFilter);
  }

  if (sortSelect) {
    sortSelect.addEventListener('change', function () {
      applySort();
      applyFilter();
    });
  }

  applySort();
  applyFilter();
})();
