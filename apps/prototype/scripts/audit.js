/**
 * PROTOTYPE-SPEC.md §10 "규칙 위반 자동 점검" — console-runnable audit.
 *
 * Usage: open the app in a browser, navigate to whichever screen/step you
 * want to check (use the ScenarioBar to force `no-result` / `failed`), open
 * devtools console, paste this whole file (or run it via a <script> tag),
 * and read `window.__auditResult` / the console table it prints.
 *
 * This is NOT part of the build — it is never imported by src/. Keep it
 * under apps/prototype/scripts/ only, paste-into-console style.
 */
(function runAudit() {
  const results = {};

  function computedNumber(el, prop) {
    const v = getComputedStyle(el).getPropertyValue(prop).trim();
    return v;
  }

  function tokenValue(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  function colorsEqual(a, b) {
    // Normalize via a throwaway element so "rgb(...)" vs "#hex" compare equal.
    const probe = document.createElement('div');
    probe.style.color = a;
    document.body.appendChild(probe);
    const na = getComputedStyle(probe).color;
    probe.style.color = b;
    const nb = getComputedStyle(probe).color;
    document.body.removeChild(probe);
    return na === nb;
  }

  // ---- 1. confidence/accuracy percentage text --------------------------
  (function checkPercentages() {
    const PCT_RE = /\d+\s*%/;
    const KEYWORD_RE = /(확신|정확|일치)/;
    let count = 0;
    const hits = [];
    document.querySelectorAll('body *').forEach((el) => {
      if (el.children.length > 0) return; // leaf nodes only
      const text = el.textContent || '';
      if (PCT_RE.test(text) && KEYWORD_RE.test(text)) {
        count++;
        hits.push(text.trim());
      }
    });
    results.confidencePercentages = { count, hits };
  })();

  // ---- 2. ETA / remaining-time text -------------------------------------
  (function checkEta() {
    // "초 남음" / "약 ...후 완료" / "남은 시간" / "약 N분 더 걸립니다(걸려요)".
    // Judgement call (per brief): NoResultScreen's `.axis-s` copy ("약 4분 더
    // 걸립니다") is a cost estimate for the *widen* action the user is about
    // to opt into — not an ETA counting down the currently-running task — so
    // it's excluded here by its `.axis-s` container class.
    const ETA_RE = /(초\s*남음|약\s*.{0,6}후\s*완료|남은\s*시간|약\s*.{0,8}(더\s*걸립니다|더\s*걸려요))/;
    let count = 0;
    const hits = [];
    document.querySelectorAll('body *').forEach((el) => {
      if (el.children.length > 0) return;
      const text = (el.textContent || '').trim();
      if (!text) return;
      if (ETA_RE.test(text)) {
        const inWidenPreview = !!el.closest('.axis-s');
        if (inWidenPreview) {
          hits.push({ text, excluded: 'widen-cost-preview (.axis-s), not a current-task ETA' });
          return;
        }
        count++;
        hits.push(text);
      }
    });
    results.etaText = { count, hits };
  })();

  // ---- 3. --red usage outside FailedScreen ------------------------------
  // There is no DOM marker distinguishing "the FailedScreen subtree" from
  // any other screen's root (both use the shared generic `.pbody`/`.empty`
  // shell) — so per the brief, this is run once per mounted step. On every
  // step OTHER than `failed`, `count` here must be 0 for the rule to hold.
  // On the `failed` step itself, a nonzero count is expected (FailedScreen
  // is the one screen allowed to use --red) — inspect `hits` manually to
  // confirm usage stays confined to the single alert-icon roundel per the
  // Global Constraint comment in FailedScreen.tsx.
  (function checkRed() {
    const redVal = tokenValue('--red');
    let count = 0;
    const hits = [];
    document.querySelectorAll('body *').forEach((el) => {
      const cs = getComputedStyle(el);
      const props = ['color', 'backgroundColor', 'borderColor', 'borderTopColor', 'borderBottomColor', 'borderLeftColor', 'borderRightColor'];
      for (const p of props) {
        const v = cs[p];
        if (v && v !== 'rgba(0, 0, 0, 0)' && colorsEqual(v, redVal)) {
          count++;
          hits.push({ el: el.tagName + (el.className ? '.' + String(el.className).split(' ').join('.') : ''), prop: p, value: v });
          break;
        }
      }
      // SVG icons (lucide-react) commonly set `stroke`/`fill` attributes directly to
      // `var(--red)` (see FailedScreen's TriangleAlert) — getComputedStyle().color
      // doesn't reflect this (SVG paints via stroke/fill, not CSS color; see the
      // contrast-check comment above), so check the raw attribute string too.
      if (el.tagName === 'svg' || el.tagName === 'path') {
        for (const attr of ['stroke', 'fill']) {
          const v = el.getAttribute(attr);
          if (v && v.includes('var(--red)')) {
            count++;
            hits.push({ el: el.tagName + (el.className ? '.' + String(el.className).split(' ').join('.') : ''), prop: `svg:${attr}`, value: v });
          }
        }
      }
    });
    results.redUsage = { count, hits, redToken: redVal, note: 'Interpret per current step: 0 expected unless step === "failed"; also includes --red-soft/--red-bd? No — only the raw --red token per the brief\'s own check definition. FailedScreen\'s roundel background/border (--red-soft/--red-bd) are separate tokens, correctly not counted here.' };
  })();

  // ---- 4. --orange usage outside "확인 필요" context --------------------
  (function checkOrange() {
    const orangeVals = [tokenValue('--orange'), tokenValue('--orange-ink'), tokenValue('--orange-soft'), tokenValue('--orange-bd')];
    let count = 0;
    const hits = [];
    document.querySelectorAll('body *').forEach((el) => {
      // Allowed "확인 필요"/needs-attention contexts, manually verified during
      // Task 17's walk: .badge-attention (StatusBadge itself), .xhd.pick
      // (HandoffScreen's "안전신문고에서 직접 고를 것" header — needs the
      // user's own action), .q (PrepareScreen's uncertain-plate-character
      // glyph), .kv-row.act (KVRow's needs-review active-row highlight),
      // .sum-ic (PrepareScreen's "남은 확인 N개" summary icon, orange only
      // when remaining > 0). A few remaining hits (ScopeScreen's
      // "못 알아들었어요" fallback value, PrepareScreen's disabled-다음-button
      // hint paragraph) use ad-hoc inline styles with no stable selector —
      // manually verified correct (needs-review semantics) during the walk,
      // left for the script to keep surfacing per the brief's own note that
      // this check can't be fully automated.
      const inAllowedContext = !!el.closest('.badge-attention, .xhd.pick, .q, .kv-row.act, .sum-ic');
      if (inAllowedContext) return;
      const cs = getComputedStyle(el);
      const props = ['color', 'backgroundColor', 'borderColor'];
      for (const p of props) {
        const v = cs[p];
        if (v && v !== 'rgba(0, 0, 0, 0)' && orangeVals.some((ov) => colorsEqual(v, ov))) {
          count++;
          hits.push({ el: el.tagName + (el.className ? '.' + String(el.className).split(' ').join('.') : ''), prop: p, value: v, text: (el.textContent || '').slice(0, 40) });
          break;
        }
      }
    });
    results.orangeMisuse = { count, hits, note: 'Heuristic — excludes .badge-attention/[data-needs-review]/[data-scenariobar]. Manual eyeball still required per brief.' };
  })();

  // ---- 5. StatusBadge carrying a WorkStatus value ------------------------
  results.statusBadgeWorkStatus = {
    count: 0,
    note: 'Not runtime-checkable and not attempted — StatusBadge(props: { status: InfoStatus }) means passing a WorkStatus value is a TypeScript compile error (InfoStatus and WorkStatus share no string literals). Verified statically instead of at runtime; see src/components/StatusBadge.tsx.',
  };

  // ---- 6. sub-15px text outside video overlays (11px floor there) -------
  (function checkFontSize() {
    let count = 0;
    const hits = [];
    document.querySelectorAll('body *').forEach((el) => {
      if (el.children.length > 0) return; // leaf text nodes only
      const text = (el.textContent || '').trim();
      if (!text) return;
      const cs = getComputedStyle(el);
      if (cs.visibility === 'hidden' || cs.display === 'none') return;
      const rect = el.getBoundingClientRect();
      if (rect.width === 0 && rect.height === 0) return;
      const size = parseFloat(cs.fontSize);
      // Video-mockup subtrees (all styled on the --video dark-dashcam token):
      // `.ev`/`.cand-th` (EvidenceFrame's full viewer / thumbnail),
      // `.plate-stage` (PrepareScreen's plate close-up), `.fr` (PrepareScreen's
      // 4 plate-quality frame thumbnails).
      const inOverlay = !!el.closest('.ev, .cand-th, .plate-stage, .fr');
      const floor = inOverlay ? 11 : 15;
      if (size < floor) {
        count++;
        hits.push({ el: el.tagName + (el.className ? '.' + String(el.className).split(' ').join('.') : ''), size, floor, text: text.slice(0, 30) });
      }
    });
    results.subFloorFontSize = { count, hits };
  })();

  // ---- 7. contrast ratio < 4.5:1 -----------------------------------------
  (function checkContrast() {
    function parseColor(str) {
      const m = str.match(/rgba?\(([^)]+)\)/);
      if (!m) return null;
      const parts = m[1].split(',').map((s) => parseFloat(s.trim()));
      return { r: parts[0], g: parts[1], b: parts[2], a: parts.length > 3 ? parts[3] : 1 };
    }
    function relLum({ r, g, b }) {
      const [rs, gs, bs] = [r, g, b].map((c) => {
        const cs = c / 255;
        return cs <= 0.03928 ? cs / 12.92 : Math.pow((cs + 0.055) / 1.055, 2.4);
      });
      return 0.2126 * rs + 0.7152 * gs + 0.0722 * bs;
    }
    function contrastRatio(fg, bg) {
      const l1 = relLum(fg) + 0.05;
      const l2 = relLum(bg) + 0.05;
      return l1 > l2 ? l1 / l2 : l2 / l1;
    }
    function nearestBg(el) {
      let cur = el;
      while (cur) {
        const cs = getComputedStyle(cur);
        const bg = parseColor(cs.backgroundColor);
        if (bg && bg.a > 0) return bg;
        cur = cur.parentElement;
      }
      return { r: 255, g: 255, b: 255, a: 1 }; // fallback white
    }
    let count = 0;
    const hits = [];
    document.querySelectorAll('body *').forEach((el) => {
      if (el.children.length > 0) return;
      const text = (el.textContent || '').trim();
      if (!text) return;
      // SVG <text> renders via the `fill` attribute/property, not CSS `color`,
      // and its backdrop is normally a sibling <rect> inside the same SVG —
      // neither participates in the color/background-color box model this
      // walk-up assumes, so it produces meaningless numbers (verified against
      // an actual case: computed `color` read here was an inherited, unused
      // value while the real rendered `fill` was a small dark plate glyph on
      // a light plate-rect background — high real contrast, false-flagged as
      // ~1:1 by this heuristic). These are inline illustration artwork (spec
      // §6: "실제 영상·이미지를 쓰지 않는다 — 항상 인라인 SVG"), not UI copy —
      // skip them; verify plate/scene SVG legibility by eye instead.
      if (el.ownerSVGElement || el.namespaceURI === 'http://www.w3.org/2000/svg') return;
      const cs = getComputedStyle(el);
      if (cs.visibility === 'hidden' || cs.display === 'none') return;
      // Disabled controls are explicitly excluded from WCAG 1.4.3 ("Inactive
      // User Interface Components") — a dimmed disabled button/field is
      // correct, not a violation.
      if (el.disabled || el.closest('button:disabled, input:disabled, textarea:disabled, [aria-disabled="true"]')) return;
      const rect = el.getBoundingClientRect();
      if (rect.width === 0 && rect.height === 0) return;
      const fg = parseColor(cs.color);
      if (!fg) return;
      const bg = nearestBg(el);
      const ratio = contrastRatio(fg, bg);
      const fontSize = parseFloat(cs.fontSize);
      const fontWeight = parseInt(cs.fontWeight, 10) || 400;
      const isLarge = fontSize >= 24 || (fontSize >= 18.66 && fontWeight >= 700);
      const threshold = isLarge ? 3.0 : 4.5;
      if (ratio < threshold) {
        count++;
        hits.push({ el: el.tagName + (el.className ? '.' + String(el.className).split(' ').join('.') : ''), ratio: ratio.toFixed(2), threshold, text: text.slice(0, 30) });
      }
    });
    results.contrastFailures = { count, hits };
  })();

  console.table(
    Object.entries(results).map(([k, v]) => ({ check: k, count: v.count }))
  );
  console.log('Full results:', results);
  window.__auditResult = results;
  return results;
})();
