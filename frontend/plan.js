// Powers Your Plan (plan.html): guided plans for two hazards — Wildfire and
// Earthquake — each with Before/During/After steps, summarized as compact
// rows and opened as popups for the full checklist, so the page itself
// stays scannable instead of dumping every item on screen at once.
const API_BASE = window.EMBERREADY_API_BASE || "";

const CHAPTER_TITLES = {
  before: "Before a Wildfire",
  during: "During a Wildfire",
  after: "After a Wildfire",
  earthquakeBefore: "Before an Earthquake",
  earthquakeDuring: "During an Earthquake",
  earthquakeAfter: "After an Earthquake",
};

// Each hazard's three chapters, in order, plus how to compute progress for
// each. Wildfire's "before" is the one dynamic, backend-personalized
// checklist; everything else is a static, locally-tracked review list.
const WILDFIRE_CHAPTERS = [
  { id: "before", startedLabel: "Not started", getProgress: () => EmberReadyState.beforeProgress(EmberReadyState.load().lastChecklist) },
  { id: "during", startedLabel: "Not reviewed", getProgress: () => EmberReadyState.reviewedProgress("during") },
  { id: "after", startedLabel: "Not reviewed", getProgress: () => EmberReadyState.reviewedProgress("after") },
];

const EARTHQUAKE_CHAPTERS = [
  { id: "earthquakeBefore", startedLabel: "Not reviewed", getProgress: () => EmberReadyState.reviewedProgress("earthquakeBefore") },
  { id: "earthquakeDuring", startedLabel: "Not reviewed", getProgress: () => EmberReadyState.reviewedProgress("earthquakeDuring") },
  { id: "earthquakeAfter", startedLabel: "Not reviewed", getProgress: () => EmberReadyState.reviewedProgress("earthquakeAfter") },
];

function chapterEl(id) {
  return document.querySelector(`.journey-chapter[data-chapter="${id}"]`);
}

function bodyHome(id) {
  return document.querySelector(`[data-body-home="${id}"]`);
}

function setChapterVisualState(id, complete) {
  const el = chapterEl(id);
  el.classList.toggle("complete", complete);
  const statusEl = el.querySelector("[data-status]");
  if (statusEl) statusEl.textContent = complete ? "Complete" : "Not started";
}

function setProgressRow(id, done, total, startedLabel) {
  const badge = document.querySelector(`[data-progress-badge="${id}"]`);
  const text = document.querySelector(`[data-progress-text="${id}"]`);
  const complete = total > 0 && done === total;
  badge.textContent = total === 0 ? "--" : `${done}/${total}`;
  badge.className = `tap-row-badge${complete ? " badge-done" : done > 0 ? " badge-attn" : ""}`;
  text.textContent = total === 0 ? "Set up your checklist" : complete ? "Complete" : done > 0 ? `${done} of ${total} done` : startedLabel;
}

function refreshChapterGroup(chapters, pathFillId, isVisible) {
  let lastCompleteIdx = -1;
  chapters.forEach((chapter, idx) => {
    const progress = chapter.getProgress();
    setProgressRow(chapter.id, progress.done, progress.total, chapter.startedLabel);
    const complete = progress.total > 0 && progress.done === progress.total;
    setChapterVisualState(chapter.id, complete);
    if (complete) lastCompleteIdx = idx;
  });

  // The path-fill height needs real layout (offsetTop is 0 on a hidden,
  // display:none section) — skip it while hidden rather than zeroing out
  // a correct fill. setHazardTab() re-runs this the moment a section
  // becomes visible again, so it's never stale for long.
  if (!isVisible) return;

  const pathFill = document.getElementById(pathFillId);
  if (lastCompleteIdx >= 0) {
    const target = chapterEl(chapters[lastCompleteIdx].id);
    const node = target.querySelector(".chapter-node");
    const height = target.offsetTop + node.offsetTop + node.offsetHeight / 2 - 10;
    pathFill.style.height = `${Math.max(0, height)}px`;
  } else {
    pathFill.style.height = "0px";
  }
}

function refreshAllChapterStates() {
  const wildfireVisible = !document.getElementById("wildfire-plan-section").classList.contains("hidden");
  const earthquakeVisible = !document.getElementById("earthquake-plan-section").classList.contains("hidden");
  refreshChapterGroup(WILDFIRE_CHAPTERS, "journey-path-fill", wildfireVisible);
  refreshChapterGroup(EARTHQUAKE_CHAPTERS, "eq-journey-path-fill", earthquakeVisible);
}

document.querySelectorAll("[data-open-chapter]").forEach((btn) => {
  btn.addEventListener("click", () => {
    const id = btn.dataset.openChapter;
    EmberReadyModal.open(CHAPTER_TITLES[id], bodyHome(id));
  });
});

// --- Hazard tab switcher --------------------------------------------------

function setHazardTab(hazard) {
  document.querySelectorAll("[data-hazard]").forEach((btn) => btn.classList.toggle("active", btn.dataset.hazard === hazard));
  document.getElementById("wildfire-plan-section").classList.toggle("hidden", hazard !== "wildfire");
  document.getElementById("earthquake-plan-section").classList.toggle("hidden", hazard !== "earthquake");
  document.getElementById("plan-subtitle").textContent =
    hazard === "wildfire"
      ? "Clear guidance for before, during, and after a wildfire."
      : "Clear guidance for before, during, and after an earthquake.";
  EmberReadyState.setLastPlanHazard(hazard);
  // Path-fill height depends on layout, which only exists once a section
  // is actually visible (display:none elements report 0 offsets).
  refreshAllChapterStates();
}

document.querySelectorAll("[data-hazard]").forEach((btn) => {
  btn.addEventListener("click", () => setHazardTab(btn.dataset.hazard));
});

// --- Before a Wildfire: household form drives all three real checklists --

function updateAccordionCount(elementId, done, total) {
  const span = document.querySelector(`[data-count="${elementId}"]`);
  if (span) span.textContent = `(${done}/${total})`;
}

function renderChecklistList(elementId, category, items) {
  const ul = document.getElementById(elementId);
  ul.innerHTML = "";
  items.forEach((item, idx) => {
    const li = document.createElement("li");
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.id = `${elementId}-${idx}`;
    checkbox.checked = EmberReadyState.isDone(category, item.text);

    const label = document.createElement("label");
    label.setAttribute("for", checkbox.id);
    label.textContent = item.text;
    const reasons = (item.reasons || []).filter((r) => r !== "everyone");
    if (reasons.length > 0) {
      const tag = document.createElement("span");
      tag.className = "reason-tag";
      tag.textContent = `Included because: ${reasons.join(", ")}`;
      label.appendChild(tag);
    }

    checkbox.addEventListener("change", () => {
      const wasComplete = (() => {
        const p = EmberReadyState.beforeProgress(EmberReadyState.load().lastChecklist);
        return p.total > 0 && p.done === p.total;
      })();
      EmberReadyState.setDone(category, item.text, checkbox.checked);
      if (checkbox.checked && !wasComplete) {
        EmberReadyEffects.flySpark(checkbox, chapterEl("before").querySelector(".chapter-node"), () => {});
      }
      const p = EmberReadyState.categoryProgress(category, items);
      updateAccordionCount(elementId, p.done, p.total);
      refreshAllChapterStates();
    });

    li.append(checkbox, label);
    ul.appendChild(li);
  });
  const p = EmberReadyState.categoryProgress(category, items);
  updateAccordionCount(elementId, p.done, p.total);
  const accordion = document.getElementById(`${elementId}-accordion`);
  if (accordion) accordion.classList.remove("hidden");
}

function renderAllChecklists(checklist) {
  document.getElementById("before-note").textContent = checklist.note || "";
  renderChecklistList("evacuation-route-list", "evacuation_route", checklist.evacuation_route || []);
  renderChecklistList("go-bag-list", "go_bag", checklist.go_bag || []);
  renderChecklistList("defensible-space-list", "defensible_space", checklist.defensible_space || []);
  document.getElementById("household-form").classList.add("hidden");
}

document.getElementById("household-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(event.target);
  const payload = {
    ownership: formData.get("ownership"),
    has_pets: formData.get("has_pets") === "on",
    mobility_needs: formData.get("mobility_needs") === "on",
    construction_type: formData.get("construction_type"),
  };

  try {
    const resp = await fetch(`${API_BASE}/api/checklist`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await resp.json();
    if (!resp.ok) {
      alert("Could not build your checklist. Please try again.");
      return;
    }
    EmberReadyState.update({ lastChecklist: data, householdProfile: payload });
    renderAllChecklists(data);
    refreshAllChapterStates();
  } catch (err) {
    alert("Network error while building your checklist. Please try again.");
  }
});

// --- Static guidance stages (wildfire During/After, all of Earthquake) ---

function renderStaticList(elementId, stage, items) {
  const ul = document.getElementById(elementId);
  ul.innerHTML = "";
  items.forEach((text, idx) => {
    const li = document.createElement("li");
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.id = `${elementId}-${idx}`;
    checkbox.checked = EmberReadyState.isReviewed(stage, text);
    const label = document.createElement("label");
    label.setAttribute("for", checkbox.id);
    label.textContent = text;
    checkbox.addEventListener("change", () => {
      const wasComplete = EmberReadyState.reviewedProgress(stage);
      const wasAllDone = wasComplete.done === wasComplete.total;
      EmberReadyState.setReviewed(stage, text, checkbox.checked);
      if (checkbox.checked && !wasAllDone) {
        EmberReadyEffects.flySpark(checkbox, chapterEl(stage).querySelector(".chapter-node"), () => {});
      }
      refreshAllChapterStates();
    });
    li.append(checkbox, label);
    ul.appendChild(li);
  });
}

// --- Restore on load ------------------------------------------------

(function restore() {
  const state = EmberReadyState.load();
  if (state.lastChecklist) {
    renderAllChecklists(state.lastChecklist);
  }
  renderStaticList("during-list", "during", EmberReadyState.DURING_ITEMS);
  renderStaticList("after-list", "after", EmberReadyState.AFTER_ITEMS);
  renderStaticList("earthquake-before-list", "earthquakeBefore", EmberReadyState.EARTHQUAKE_BEFORE_ITEMS);
  renderStaticList("earthquake-during-list", "earthquakeDuring", EmberReadyState.EARTHQUAKE_DURING_ITEMS);
  renderStaticList("earthquake-after-list", "earthquakeAfter", EmberReadyState.EARTHQUAKE_AFTER_ITEMS);

  const hash = window.location.hash.replace("#", "");
  const initialHazard = hash.startsWith("earthquake") ? "earthquake" : state.lastPlanHazard || "wildfire";
  setHazardTab(initialHazard);

  if (hash && bodyHome(hash)) {
    EmberReadyModal.open(CHAPTER_TITLES[hash], bodyHome(hash));
    setTimeout(() => chapterEl(hash).scrollIntoView({ behavior: EmberReadyEffects.reduceMotionPreferred() ? "auto" : "smooth", block: "start" }), 100);
  }
})();
