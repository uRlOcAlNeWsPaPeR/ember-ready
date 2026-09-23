// Powers Your Plan (plan.html): three guided plans — Before, During, and
// After a wildfire — each summarized as a compact row on the page and
// opened as a popup for the full checklist, so the page itself stays
// scannable instead of dumping every item on screen at once.
const API_BASE = window.EMBERREADY_API_BASE || "";

const CHAPTER_TITLES = {
  before: "Before a Wildfire",
  during: "During a Wildfire",
  after: "After a Wildfire",
};

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

function refreshAllChapterStates() {
  const checklist = EmberReadyState.load().lastChecklist;
  const before = EmberReadyState.beforeProgress(checklist);
  const during = EmberReadyState.reviewedProgress("during");
  const after = EmberReadyState.reviewedProgress("after");

  const completeFlags = {
    before: before.total > 0 && before.done === before.total,
    during: during.done === during.total,
    after: after.done === after.total,
  };

  setProgressRow("before", before.done, before.total, "Not started");
  setProgressRow("during", during.done, during.total, "Not reviewed");
  setProgressRow("after", after.done, after.total, "Not reviewed");

  let lastCompleteIdx = -1;
  ["before", "during", "after"].forEach((id, idx) => {
    setChapterVisualState(id, completeFlags[id]);
    if (completeFlags[id]) lastCompleteIdx = idx;
  });

  const chapters = document.querySelectorAll(".journey-chapter");
  const pathFill = document.getElementById("journey-path-fill");
  if (lastCompleteIdx >= 0 && chapters[lastCompleteIdx]) {
    const target = chapters[lastCompleteIdx];
    const node = target.querySelector(".chapter-node");
    const height = target.offsetTop + node.offsetTop + node.offsetHeight / 2 - 10;
    pathFill.style.height = `${Math.max(0, height)}px`;
  } else {
    pathFill.style.height = "0px";
  }
}

document.querySelectorAll("[data-open-chapter]").forEach((btn) => {
  btn.addEventListener("click", () => {
    const id = btn.dataset.openChapter;
    EmberReadyModal.open(CHAPTER_TITLES[id], bodyHome(id));
  });
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

// --- During / After: static guidance, checked off locally ---------------

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
  refreshAllChapterStates();

  const hash = window.location.hash.replace("#", "");
  if (hash && bodyHome(hash)) {
    EmberReadyModal.open(CHAPTER_TITLES[hash], bodyHome(hash));
    setTimeout(() => chapterEl(hash).scrollIntoView({ behavior: EmberReadyEffects.reduceMotionPreferred() ? "auto" : "smooth", block: "start" }), 100);
  }
})();
