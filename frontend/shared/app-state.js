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

  // All of these are general official guidance, not personalized —
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

  const EARTHQUAKE_BEFORE_ITEMS = [
    "Secure heavy furniture, mirrors, water heaters, and shelving to walls so they can't tip over.",
    "Know how to shut off your home's gas, water, and electricity in an emergency.",
    "Pack a go-bag and emergency kit: water, food, medications, flashlight, and a battery-powered radio.",
    "Identify safe spots in each room — under sturdy furniture and away from windows or tall shelving.",
    "Practice \"Drop, Cover, and Hold On\" with everyone in your household.",
    "Agree on an out-of-area contact and a meeting point in case your household is separated.",
  ];

  const EARTHQUAKE_DURING_ITEMS = [
    "Drop, Cover, and Hold On: drop to the ground, cover under sturdy furniture, and hold on until shaking stops.",
    "If indoors, stay indoors — most injuries happen when people try to move during shaking.",
    "If outdoors, move to an open area away from buildings, trees, and power lines.",
    "If in bed, stay there and cover your head and neck with a pillow.",
    "If driving, pull over away from bridges and overpasses, and stay in the vehicle until shaking stops.",
  ];

  const EARTHQUAKE_AFTER_ITEMS = [
    "Expect aftershocks — be ready to Drop, Cover, and Hold On again.",
    "Check yourself and others for injuries before checking on your home.",
    "Before re-entering, check for gas leaks, structural damage, and downed power lines.",
    "Listen to official sources (see the Map tab) for information and instructions, not rumors.",
    "Document any damage with photos before you begin cleanup, for insurance purposes.",
  ];

  // Maps a stage name to its static item list and the state key its
  // local "reviewed" flags live under. Wildfire keeps its original
  // "during"/"after" names (no dynamic "before" here — that's the real,
  // personalized backend checklist instead); earthquake has all three,
  // since there's no equivalent backend personalization for it.
  const REVIEW_STAGES = {
    during: { items: DURING_ITEMS, stateKey: "duringReviewed" },
    after: { items: AFTER_ITEMS, stateKey: "afterReviewed" },
    earthquakeBefore: { items: EARTHQUAKE_BEFORE_ITEMS, stateKey: "earthquakeBeforeReviewed" },
    earthquakeDuring: { items: EARTHQUAKE_DURING_ITEMS, stateKey: "earthquakeDuringReviewed" },
    earthquakeAfter: { items: EARTHQUAKE_AFTER_ITEMS, stateKey: "earthquakeAfterReviewed" },
  };

  function defaults() {
    return {
      lastScore: null, // full /api/score response
      lastChecklist: null, // full /api/checklist response
      householdProfile: null,
      completed: {}, // "<category>::<item text>" -> true (Before-wildfire checklist)
      duringReviewed: {}, // "<item text>" -> true
      afterReviewed: {}, // "<item text>" -> true
      earthquakeBeforeReviewed: {},
      earthquakeDuringReviewed: {},
      earthquakeAfterReviewed: {},
      lastPlanHazard: "wildfire", // remembers which Plan sub-tab was open
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
    const key = REVIEW_STAGES[stage].stateKey;
    return !!load()[key][text];
  }

  function setReviewed(stage, text, done) {
    const key = REVIEW_STAGES[stage].stateKey;
    return update((state) => {
      const next = { ...state[key] };
      if (done) next[text] = true;
      else delete next[text];
      return { ...state, [key]: next };
    });
  }

  function reviewedProgress(stage) {
    const { items, stateKey } = REVIEW_STAGES[stage];
    const state = load();
    const done = items.filter((t) => state[stateKey][t]).length;
    return { done, total: items.length };
  }

  function markScoreViewed() {
    return update({ scoreViewed: true });
  }

  function setLastPlanHazard(hazard) {
    return update({ lastPlanHazard: hazard });
  }

  return {
    DURING_ITEMS,
    AFTER_ITEMS,
    EARTHQUAKE_BEFORE_ITEMS,
    EARTHQUAKE_DURING_ITEMS,
    EARTHQUAKE_AFTER_ITEMS,
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
    setLastPlanHazard,
  };
})();

window.EmberReadyState = EmberReadyState;
