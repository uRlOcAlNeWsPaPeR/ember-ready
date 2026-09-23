// Shared bottom navigation bar — Map, Earthquakes, then Plan. Injected into
// a `<div id="bottom-nav-root">` placeholder on every screen so the markup
// and icons are only maintained once.
(function () {
  const ITEMS = [
    {
      href: "index.html",
      match: ["", "index.html"],
      label: "Map",
      icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 6v16l7-4 8 4 7-4V2l-7 4-8-4-7 4z"/><path d="M8 2v16M16 6v16"/></svg>`,
    },
    {
      href: "earthquakes.html",
      match: ["earthquakes.html"],
      label: "Earthquakes",
      icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12h3l2-7 3 14 2-9 2 5 2-3h6" /></svg>`,
    },
    {
      href: "plan.html",
      match: ["plan.html"],
      label: "Plan",
      icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>`,
    },
  ];

  function currentPage() {
    const path = window.location.pathname;
    return path.substring(path.lastIndexOf("/") + 1);
  }

  function mount() {
    const root = document.getElementById("bottom-nav-root");
    if (!root) return;
    const page = currentPage();
    const nav = document.createElement("nav");
    nav.className = "bottom-nav";
    nav.setAttribute("aria-label", "Primary");
    for (const item of ITEMS) {
      const a = document.createElement("a");
      a.href = item.href;
      if (item.match.includes(page)) {
        a.classList.add("active");
        a.setAttribute("aria-current", "page");
      }
      a.innerHTML = `${item.icon}<span>${item.label}</span>`;
      nav.appendChild(a);
    }
    root.replaceWith(nav);
  }

  document.addEventListener("DOMContentLoaded", mount);
})();
