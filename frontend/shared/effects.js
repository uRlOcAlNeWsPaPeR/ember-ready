// Shared visual effects for the calm "Safety Journey" redesign: the Reduce
// Motion and High Contrast accessibility settings (persisted, and Reduce
// Motion also respects prefers-reduced-motion by default), and a reusable
// "spark flies from A to B" animation used when a Safety Journey step is
// completed — an ember spark that turns blue on arrival at the protection ring.
// There is no ambient decoration here on purpose: the new design is calm,
// not busy, so nothing floats or drifts unless it is communicating progress.
const EmberReadyEffects = (() => {
  function reduceMotionPreferred() {
    const state = EmberReadyState.load();
    if (state.reduceMotion) return true;
    return window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

  function applyAccessibilityClasses() {
    const state = EmberReadyState.load();
    document.body.classList.toggle("reduce-motion", reduceMotionPreferred());
    document.body.classList.toggle("high-contrast", !!state.highContrast);
  }

  // A single small gear button opens a popup with both accessibility
  // toggles — there's no dedicated settings screen, so this is their only
  // home, kept intentionally tiny rather than growing into a full page.
  function mountSettingsFab() {
    if (document.querySelector(".settings-fab")) return;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "settings-fab";
    btn.setAttribute("aria-label", "Accessibility settings");
    btn.innerHTML = `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>`;
    btn.addEventListener("click", openSettingsPopup);
    document.body.appendChild(btn);
  }

  function toggleRowHtml(id, label, sub, checked) {
    return `
      <div class="toggle-row">
        <div>
          <div class="toggle-label">${label}</div>
          <div class="toggle-sub">${sub}</div>
        </div>
        <label class="switch">
          <input type="checkbox" id="${id}" ${checked ? "checked" : ""} />
          <span class="track"><span class="knob"></span></span>
        </label>
      </div>
    `;
  }

  function openSettingsPopup() {
    if (!window.EmberReadyModal) return;
    const state = EmberReadyState.load();
    const body = document.createElement("div");
    body.innerHTML =
      toggleRowHtml("reduce-motion-toggle", "Reduce Motion", "Turns off animations throughout the app.", state.reduceMotion) +
      toggleRowHtml("high-contrast-toggle", "High Contrast", "Increases contrast and adds borders for readability.", state.highContrast);
    EmberReadyModal.open("Accessibility", body);
    body.querySelector("#reduce-motion-toggle").addEventListener("change", (e) => {
      EmberReadyState.update({ reduceMotion: e.target.checked });
      applyAccessibilityClasses();
    });
    body.querySelector("#high-contrast-toggle").addEventListener("change", (e) => {
      EmberReadyState.update({ highContrast: e.target.checked });
      applyAccessibilityClasses();
    });
  }

  // Flies a small ember spark from `fromEl`'s center to `toEl`'s center,
  // turning into a cool-blue spark on arrival. Calls onArrive when the
  // animation completes. Skips straight to onArrive under Reduce Motion.
  function flySpark(fromEl, toEl, onArrive) {
    if (!fromEl || !toEl || reduceMotionPreferred()) {
      if (onArrive) onArrive();
      return;
    }
    const fromRect = fromEl.getBoundingClientRect();
    const toRect = toEl.getBoundingClientRect();

    const spark = document.createElement("div");
    spark.className = "ember-spark";
    spark.style.left = `${fromRect.left + fromRect.width / 2 - 6}px`;
    spark.style.top = `${fromRect.top + fromRect.height / 2 - 6}px`;
    document.body.appendChild(spark);

    requestAnimationFrame(() => {
      spark.style.left = `${toRect.left + toRect.width / 2 - 6}px`;
      spark.style.top = `${toRect.top + toRect.height / 2 - 6}px`;
      spark.style.transform = "scale(1.5)";
    });

    setTimeout(() => {
      spark.classList.add("arrived");
      if (onArrive) onArrive();
      setTimeout(() => {
        spark.style.opacity = "0";
        setTimeout(() => spark.remove(), 300);
      }, 150);
    }, 650);
  }

  function init() {
    applyAccessibilityClasses();
    mountSettingsFab();
  }

  return { init, reduceMotionPreferred, applyAccessibilityClasses, flySpark };
})();

window.EmberReadyEffects = EmberReadyEffects;
document.addEventListener("DOMContentLoaded", () => EmberReadyEffects.init());
