// Attaches a typeahead dropdown to a text input, backed by
// GET /api/geocode/suggest (city/town/ZIP suggestions — see backend for
// why this isn't powered by the Census geocoder, which has no partial-
// query endpoint). Selecting a suggestion fills the input and submits the
// input's <form>, reusing whatever search/score logic that form already
// has wired up.
function attachAddressAutocomplete(inputEl) {
  const API_BASE = window.EMBERREADY_API_BASE || "";
  const DEBOUNCE_MS = 250;
  const MIN_CHARS = 2;

  const dropdown = document.createElement("ul");
  dropdown.className = "autocomplete-dropdown hidden";
  inputEl.insertAdjacentElement("afterend", dropdown);

  // The dropdown is a sibling of the input (not a child), so it shares the
  // input's offsetParent — position it explicitly under the input rather
  // than relying on CSS `top: 100%` (which would resolve against the
  // shared parent's full height, not the input's own position within it).
  const wrapper = inputEl.parentElement;
  if (getComputedStyle(wrapper).position === "static") {
    wrapper.style.position = "relative";
  }

  function positionDropdown() {
    dropdown.style.top = `${inputEl.offsetTop + inputEl.offsetHeight + 4}px`;
    dropdown.style.left = `${inputEl.offsetLeft}px`;
    dropdown.style.width = `${inputEl.offsetWidth}px`;
  }

  let debounceTimer = null;
  let currentSuggestions = [];
  let activeIndex = -1;
  let latestRequestId = 0;

  function hideDropdown() {
    dropdown.classList.add("hidden");
    dropdown.innerHTML = "";
    currentSuggestions = [];
    activeIndex = -1;
  }

  function selectSuggestion(suggestion) {
    inputEl.value = suggestion.label;
    inputEl.dataset.selectedLat = suggestion.latitude;
    inputEl.dataset.selectedLon = suggestion.longitude;
    hideDropdown();
    const form = inputEl.closest("form");
    if (form) {
      form.requestSubmit();
    }
  }

  function renderSuggestions(suggestions) {
    currentSuggestions = suggestions;
    activeIndex = -1;
    dropdown.innerHTML = "";

    if (suggestions.length === 0) {
      hideDropdown();
      return;
    }

    suggestions.forEach((suggestion, index) => {
      const li = document.createElement("li");
      li.textContent = suggestion.label;
      li.addEventListener("mousedown", (event) => {
        // mousedown (not click) fires before the input's blur event, so
        // the dropdown doesn't disappear before the selection registers.
        event.preventDefault();
        selectSuggestion(suggestion);
      });
      li.addEventListener("mouseenter", () => setActiveIndex(index));
      dropdown.appendChild(li);
    });

    positionDropdown();
    dropdown.classList.remove("hidden");
  }

  function setActiveIndex(index) {
    const items = dropdown.querySelectorAll("li");
    items.forEach((item) => item.classList.remove("active"));
    if (index >= 0 && index < items.length) {
      items[index].classList.add("active");
      items[index].scrollIntoView({ block: "nearest" });
    }
    activeIndex = index;
  }

  async function fetchSuggestions(query) {
    const requestId = ++latestRequestId;
    try {
      const resp = await fetch(`${API_BASE}/api/geocode/suggest?q=${encodeURIComponent(query)}`);
      if (!resp.ok) return;
      const data = await resp.json();
      if (requestId !== latestRequestId) return; // a newer keystroke already superseded this request
      renderSuggestions(data.suggestions || []);
    } catch (err) {
      // Suggestions are a nice-to-have; fail silently and let the user keep typing.
    }
  }

  inputEl.addEventListener("input", () => {
    delete inputEl.dataset.selectedLat;
    delete inputEl.dataset.selectedLon;

    const query = inputEl.value.trim();
    clearTimeout(debounceTimer);
    if (query.length < MIN_CHARS) {
      hideDropdown();
      return;
    }
    debounceTimer = setTimeout(() => fetchSuggestions(query), DEBOUNCE_MS);
  });

  inputEl.addEventListener("keydown", (event) => {
    if (dropdown.classList.contains("hidden")) return;

    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex(Math.min(activeIndex + 1, currentSuggestions.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex(Math.max(activeIndex - 1, 0));
    } else if (event.key === "Enter" && activeIndex >= 0) {
      event.preventDefault();
      selectSuggestion(currentSuggestions[activeIndex]);
    } else if (event.key === "Escape") {
      hideDropdown();
    }
  });

  inputEl.addEventListener("blur", () => {
    // Delay so a mousedown-selection (see above) can still fire first.
    setTimeout(hideDropdown, 150);
  });

  document.addEventListener("click", (event) => {
    if (event.target !== inputEl && !dropdown.contains(event.target)) {
      hideDropdown();
    }
  });
}
