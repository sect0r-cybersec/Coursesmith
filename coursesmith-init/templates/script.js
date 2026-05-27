/* =============================================================================
   Study Guide Script - Progress tracking, quiz logic, code copy buttons
   All state lives in localStorage. No backend.
   ============================================================================= */

(function () {
  'use strict';

  // -----------------------------------------------------------------
  // Storage keys are scoped per book slug to avoid cross-contamination.
  // The book slug is read from a meta tag on the page.
  // -----------------------------------------------------------------
  const bookSlug = document.querySelector('meta[name="book-slug"]')?.content || 'default';
  const STORAGE_KEY = `study-guide:${bookSlug}:progress`;
  const THEME_STORAGE_KEY = 'coursesmith-theme';

  // -----------------------------------------------------------------
  // Theme toggle (light / dark)
  // Anti-flash <head> snippet sets data-theme before paint; this
  // module wires the toggle button and persists user overrides.
  // -----------------------------------------------------------------
  const SUN_ICON = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/></svg>';
  const MOON_ICON = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';

  function currentTheme() {
    const saved = localStorage.getItem(THEME_STORAGE_KEY);
    if (saved === 'light' || saved === 'dark') return saved;
    return matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
  }

  // When opened via file:// some browsers isolate localStorage per path,
  // so the saved theme on the roadmap can't be read from a chapter page.
  // The ?theme= URL param is the cross-page carrier; on load we hydrate
  // localStorage from it, and on every link click we append it.
  function hydrateThemeFromUrl() {
    try {
      const params = new URLSearchParams(window.location.search);
      const t = params.get('theme');
      if (t === 'light' || t === 'dark') {
        localStorage.setItem(THEME_STORAGE_KEY, t);
        document.documentElement.setAttribute('data-theme', t);
      }
    } catch (e) { /* no-op */ }
  }

  function initThemePropagation() {
    document.addEventListener('click', (ev) => {
      const a = ev.target.closest('a[href]');
      if (!a) return;
      const href = a.getAttribute('href');
      // Skip external, anchor-only, or download links
      if (!href || href.startsWith('#') || href.startsWith('mailto:') ||
          /^[a-z]+:\/\//i.test(href) || a.hasAttribute('download')) return;
      try {
        const url = new URL(a.href, window.location.href);
        if (url.origin !== window.location.origin) return;
        url.searchParams.set('theme', currentTheme());
        a.href = url.toString();
      } catch (e) { /* no-op */ }
    }, true);
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    try {
      localStorage.setItem(THEME_STORAGE_KEY, theme);
    } catch (e) {
      console.warn('Failed to save theme preference:', e);
    }
    document.querySelectorAll('.theme-toggle').forEach(refreshToggle);
  }

  function refreshToggle(btn) {
    const t = currentTheme();
    // Show the target icon: sun = "switch to light", moon = "switch to dark"
    btn.innerHTML = t === 'light' ? MOON_ICON : SUN_ICON;
    btn.setAttribute(
      'aria-label',
      t === 'light' ? 'Switch to dark theme' : 'Switch to light theme'
    );
  }

  function initThemeToggle() {
    document.querySelectorAll('.theme-toggle').forEach(btn => {
      refreshToggle(btn);
      btn.addEventListener('click', () => {
        applyTheme(currentTheme() === 'light' ? 'dark' : 'light');
      });
    });
  }

  function loadProgress() {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY)) || {};
    } catch {
      return {};
    }
  }

  function saveProgress(progress) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(progress));
    } catch (e) {
      console.warn('Failed to save progress:', e);
    }
  }

  function getChapterProgress(chapterSlug) {
    const all = loadProgress();
    return all[chapterSlug] || { subsections: {}, completed: false };
  }

  function setSubsectionComplete(chapterSlug, subsectionId, complete) {
    const all = loadProgress();
    if (!all[chapterSlug]) all[chapterSlug] = { subsections: {}, completed: false };
    all[chapterSlug].subsections[subsectionId] = complete;
    // Mark whole chapter complete if all subsections are done
    const subsections = document.querySelectorAll('.subsection[data-subsection-id]');
    if (subsections.length > 0) {
      const allDone = Array.from(subsections).every(el => {
        const id = el.dataset.subsectionId;
        return all[chapterSlug].subsections[id];
      });
      all[chapterSlug].completed = allDone;
    }
    saveProgress(all);
  }

  // -----------------------------------------------------------------
  // Quiz logic
  // -----------------------------------------------------------------
  function initQuizzes() {
    document.querySelectorAll('.quiz-question').forEach(q => {
      const type = q.dataset.type || 'mcq';

      if (type === 'mcq') {
        const options = q.querySelectorAll('.quiz-option');
        options.forEach(opt => {
          opt.addEventListener('click', () => {
            options.forEach(o => o.classList.remove('selected'));
            opt.classList.add('selected');
            const input = opt.querySelector('input[type="radio"]');
            if (input) input.checked = true;
          });
        });
      }

      const checkBtn = q.querySelector('.quiz-check-btn');
      if (checkBtn) {
        checkBtn.addEventListener('click', () => checkAnswer(q));
      }

      const showBtn = q.querySelector('.quiz-show-btn');
      if (showBtn) {
        showBtn.addEventListener('click', () => {
          const exp = q.querySelector('.quiz-explanation');
          if (exp) exp.classList.add('shown');
        });
      }
    });
  }

  function checkAnswer(questionEl) {
    const type = questionEl.dataset.type || 'mcq';
    const explanation = questionEl.querySelector('.quiz-explanation');

    if (type === 'mcq') {
      const correct = questionEl.dataset.correct;
      const options = questionEl.querySelectorAll('.quiz-option');
      options.forEach(opt => {
        opt.classList.remove('correct', 'incorrect');
        const value = opt.dataset.value;
        if (value === correct) {
          opt.classList.add('correct');
        } else if (opt.classList.contains('selected')) {
          opt.classList.add('incorrect');
        }
      });
    } else if (type === 'short') {
      // Short answer: just reveal the model answer. No automatic grading.
      // The user self-marks.
    }

    if (explanation) explanation.classList.add('shown');
  }

  // -----------------------------------------------------------------
  // Subsection complete buttons
  // -----------------------------------------------------------------
  function initSubsectionComplete() {
    const chapterSlug = document.querySelector('meta[name="chapter-slug"]')?.content;
    if (!chapterSlug) return;

    document.querySelectorAll('.subsection[data-subsection-id]').forEach(section => {
      const subsectionId = section.dataset.subsectionId;
      const btn = section.querySelector('.complete-btn');
      const progress = getChapterProgress(chapterSlug);
      const isComplete = progress.subsections[subsectionId] === true;

      if (isComplete) {
        section.classList.add('complete');
        if (btn) {
          btn.classList.add('completed');
          btn.textContent = '✓ Subsection complete';
        }
      }

      if (btn) {
        btn.addEventListener('click', () => {
          const nowComplete = !section.classList.contains('complete');
          section.classList.toggle('complete', nowComplete);
          btn.classList.toggle('completed', nowComplete);
          btn.textContent = nowComplete ? '✓ Subsection complete' : 'Mark subsection complete';
          setSubsectionComplete(chapterSlug, subsectionId, nowComplete);
        });
      }
    });
  }

  // -----------------------------------------------------------------
  // Code copy buttons
  // -----------------------------------------------------------------
  function initCopyButtons() {
    document.querySelectorAll('pre').forEach(pre => {
      if (pre.querySelector('.copy-btn')) return;
      const btn = document.createElement('button');
      btn.className = 'copy-btn';
      btn.textContent = 'Copy';
      btn.type = 'button';
      btn.addEventListener('click', async () => {
        const code = pre.querySelector('code')?.innerText || pre.innerText;
        try {
          await navigator.clipboard.writeText(code);
          btn.textContent = 'Copied';
          btn.classList.add('copied');
          setTimeout(() => {
            btn.textContent = 'Copy';
            btn.classList.remove('copied');
          }, 1500);
        } catch {
          btn.textContent = 'Failed';
          setTimeout(() => { btn.textContent = 'Copy'; }, 1500);
        }
      });
      pre.appendChild(btn);
    });
  }

  // -----------------------------------------------------------------
  // Roadmap status (rendered on the index page)
  // -----------------------------------------------------------------
  function updateRoadmapStatus() {
    const cards = document.querySelectorAll('.roadmap-card[data-chapter-slug]');
    if (cards.length === 0) return;

    const all = loadProgress();
    let completedCount = 0;
    let totalCount = cards.length;

    cards.forEach(card => {
      const slug = card.dataset.chapterSlug;
      const status = card.dataset.status;
      const chapterProgress = all[slug];
      const userCompleted = chapterProgress?.completed === true;

      if (userCompleted && status === 'ready') {
        completedCount++;
        const badge = card.querySelector('.status-badge');
        if (badge && !badge.classList.contains('user-completed')) {
          badge.classList.add('user-completed');
          badge.textContent = '✓ Completed';
        }
      }
    });

    // Update progress bar
    const progressEl = document.querySelector('.roadmap-progress');
    if (progressEl) {
      const fill = progressEl.querySelector('.fill');
      const text = progressEl.querySelector('.progress-text');
      const pct = totalCount > 0 ? (completedCount / totalCount) * 100 : 0;
      if (fill) fill.style.width = `${pct}%`;
      if (text) text.textContent = `${completedCount} of ${totalCount} chapters`;
    }
  }

  // -----------------------------------------------------------------
  // Sidebar status icons (chapter page sidebar showing all chapters)
  // -----------------------------------------------------------------
  function updateSidebarStatus() {
    const all = loadProgress();
    document.querySelectorAll('.sidebar-link[data-chapter-slug]').forEach(link => {
      const slug = link.dataset.chapterSlug;
      const icon = link.querySelector('.status-icon');
      if (!icon) return;
      const completed = all[slug]?.completed === true;
      icon.classList.toggle('complete', completed);
      icon.classList.toggle('incomplete', !completed);
      icon.textContent = completed ? '●' : '○';
    });
  }

  // -----------------------------------------------------------------
  // Reset progress (utility)
  // -----------------------------------------------------------------
  window.resetStudyProgress = function () {
    if (confirm('Reset all progress for this book?')) {
      localStorage.removeItem(STORAGE_KEY);
      location.reload();
    }
  };

  // -----------------------------------------------------------------
  // Init
  // -----------------------------------------------------------------
  hydrateThemeFromUrl();
  document.addEventListener('DOMContentLoaded', () => {
    initThemeToggle();
    initThemePropagation();
    initQuizzes();
    initSubsectionComplete();
    initCopyButtons();
    updateRoadmapStatus();
    updateSidebarStatus();

    // Trigger Prism highlighting if it loaded
    if (window.Prism) {
      window.Prism.highlightAll();
    }
  });
})();
