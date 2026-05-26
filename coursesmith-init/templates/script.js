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
  document.addEventListener('DOMContentLoaded', () => {
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
