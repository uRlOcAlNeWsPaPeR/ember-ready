// Shared client-side state for EmberReady. No auth/accounts exist (by
// design — see README), so all progress is per-device, stored in
// localStorage: the last score/checklist looked up, which checklist items
// are marked done, household details, and accessibility preferences.
//
// EmberReady is a wildfire awareness and preparedness tool, not an
// emergency-communication app — this state deliberately holds no emergency
// contacts, "I'm safe" status, or anything else that implies EmberReady can
// reach or track people during an emergency.
const EmberReadyState = (() => {
  const KEY = "emberready_state_v3";
  const OLD_KEYS = ["emberready_state_v2", "emberready_state_v1"];

  // "During" and "After" are general official guidance, not personalized —
  // checking one off just means "I've read this," tracked locally so the
  // Plan screen can show real progress without fabricating a task system.
  const DURING_ITEMS = [
    "Follow official evacuation instructions immediately if they're issued for your area.",
    "Leave early if you're told to evacuate — don't wait to see how the fire develops.",
    "Avoid smoke exposure: stay indoors with windows/doors closed, or wear an N95+ mask if you must go outside.",
    "Keep track of local updates through official sources (see the Map tab), not rumors or social media.",
  ];

  const AFTER_ITEMS = [
    "Return home only when local officials say it's safe to do so.",
    "Check current air quality before spending extended time outside (see the Map tab).",
    "Document any damage with photos before you begin cleanup, for insurance purposes.",
    "Clean up safely: wear gloves and an N95+ mask, and watch for hot spots, ash, and weakened structures.",
  ];

  function defaults() {
    return {
      lastScore: null, // full /api/score response
      lastChecklist: null, // full /api/checklist response
      householdProfile: null,
      completed: {}, // "<category>::<item text>" -> true (Before-wildfire checklist)
      duringReviewed: {}, // "<item text>" -> true
      afterReviewed: {}, // "<item text>" -> true
      scoreViewed: false,
      reduceMotion: false,
      highContrast: false,
    };
  }

  function migrate(raw) {
    // Best-effort carry-over from earlier versions so returning users don't
    // lose checklist progress. Deliberately does NOT carry over emergency
    // contacts or contact-related fields — those concepts no longer exist.
    for (const oldKey of OLD_KEYS) {
      try {
        const oldRaw = localStorage.getItem(oldKey);
        if (!oldRaw) continue;
        const old = JSON.parse(oldRaw);
        return {
          ...defaults(),
          lastScore: old.lastScore || null,
          lastChecklist: old.lastChecklist || null,
          householdProfile: old.householdProfile || null,
          completed: old.completed || {},
          scoreViewed: !!old.scoreViewed,
          reduceMotion: !!old.reduceMotion,
          highContrast: !!old.highContrast,
        };
      } catch (err) {
        continue;
      }
    }
    return null;
  }

  function load() {
    try {
      const raw = localStorage.getItem(KEY);
      if (raw) return { ...defaults(), ...JSON.parse(raw) };
      const migrated = migrate();
      if (migrated) {
        save(migrated);
        return migrated;
      }
      return defaults();
    } catch (err) {
      return defaults();
    }
  }

  function save(state) {
    try {
      localStorage.setItem(KEY, JSON.stringify(state));
    } catch (err) {
      // Private browsing / storage disabled — degrade silently, nothing to persist.
    }
  }

  function update(patch) {
    const state = load();
    const next = typeof patch === "function" ? patch(state) : { ...state, ...patch };
    save(next);
    return next;
  }

  function itemKey(category, text) {
    return `${category}::${text}`;
  }

  function isDone(category, text) {
    return !!load().completed[itemKey(category, text)];
  }

  function setDone(category, text, done) {
    return update((state) => {
      const completed = { ...state.completed };
      if (done) completed[itemKey(category, text)] = true;
      else delete completed[itemKey(category, text)];
      return { ...state, completed };
    });
  }

  function categoryProgress(category, items) {
    const state = load();
    const total = items.length;
    const done = items.filter((item) => state.completed[itemKey(category, item.text)]).length;
    return { done, total, pct: total === 0 ? 0 : Math.round((done / total) * 100) };
  }

  // Combined progress across all three Before-wildfire checklist categories.
  function beforeProgress(checklist) {
    if (!checklist) return { done: 0, total: 0, pct: 0 };
    const categories = [
      ["defensible_space", checklist.defensible_space || []],
      ["go_bag", checklist.go_bag || []],
      ["evacuation_route", checklist.evacuation_route || []],
    ];
    let done = 0;
    let total = 0;
    for (const [cat, items] of categories) {
      const p = categoryProgress(cat, items);
      done += p.done;
      total += p.total;
    }
    return { done, total, pct: total === 0 ? 0 : Math.round((done / total) * 100) };
  }

  function isReviewed(stage, text) {
    const key = stage === "during" ? "duringReviewed" : "afterReviewed";
    return !!load()[key][text];
  }

  function setReviewed(stage, text, done) {
    const key = stage === "during" ? "duringReviewed" : "afterReviewed";
    return update((state) => {
      const next = { ...state[key] };
      if (done) next[text] = true;
      else delete next[text];
      return { ...state, [key]: next };
    });
  }

  function reviewedProgress(stage) {
    const items = stage === "during" ? DURING_ITEMS : AFTER_ITEMS;
    const state = load();
    const key = stage === "during" ? "duringReviewed" : "afterReviewed";
    const done = items.filter((t) => state[key][t]).length;
    return { done, total: items.length };
  }

  function markScoreViewed() {
    return update({ scoreViewed: true });
  }

  return {
    DURING_ITEMS,
    AFTER_ITEMS,
    load,
    save,
    update,
    isDone,
    setDone,
    categoryProgress,
    beforeProgress,
    isReviewed,
    setReviewed,
    reviewedProgress,
    markScoreViewed,
  };
})();

window.EmberReadyState = EmberReadyState;
