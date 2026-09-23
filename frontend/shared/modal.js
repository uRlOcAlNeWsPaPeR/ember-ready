// A single reusable popup used across screens: tap a summary row, see the
// full detail in a bottom-sheet-style modal. Content can be a plain HTML
// string, or an existing DOM node — passing a node MOVES it into the modal
// (so existing render logic/state on that node keeps working) and restores
// it to its original spot when the modal closes.
const EmberReadyModal = (() => {
  let overlayEl = null;
  let movedNode = null;
  let originalParent = null;
  let originalNext = null;

  function ensureOverlay() {
    if (overlayEl) return overlayEl;
    overlayEl = document.createElement("div");
    overlayEl.className = "modal-overlay hidden";
    overlayEl.innerHTML = `
      <div class="modal-panel" role="dialog" aria-modal="true">
        <div class="modal-header">
          <h3 class="modal-title"></h3>
          <button type="button" class="modal-close" aria-label="Close">&times;</button>
        </div>
        <div class="modal-body"></div>
      </div>
    `;
    document.body.appendChild(overlayEl);
    overlayEl.querySelector(".modal-close").addEventListener("click", close);
    overlayEl.addEventListener("click", (event) => {
      if (event.target === overlayEl) close();
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && !overlayEl.classList.contains("hidden")) close();
    });
    return overlayEl;
  }

  function restoreMovedNode() {
    if (movedNode && originalParent) {
      originalParent.insertBefore(movedNode, originalNext);
    }
    movedNode = null;
    originalParent = null;
    originalNext = null;
  }

  function open(title, content) {
    const overlay = ensureOverlay();
    overlay.querySelector(".modal-title").textContent = title;
    const body = overlay.querySelector(".modal-body");
    restoreMovedNode();
    body.innerHTML = "";
    if (typeof content === "string") {
      body.innerHTML = content;
    } else if (content instanceof Node) {
      originalParent = content.parentElement;
      originalNext = content.nextSibling;
      movedNode = content;
      body.appendChild(content);
    }
    overlay.classList.remove("hidden");
    document.body.classList.add("modal-open");
    body.scrollTop = 0;
  }

  function close() {
    if (!overlayEl || overlayEl.classList.contains("hidden")) return;
    overlayEl.classList.add("hidden");
    document.body.classList.remove("modal-open");
    restoreMovedNode();
  }

  return { open, close };
})();

window.EmberReadyModal = EmberReadyModal;
