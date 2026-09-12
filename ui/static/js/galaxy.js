function _galaxy() {
  return document.getElementById("galaxy");
}

// Placeholder: will also initialize the Three.js scene in Task 2.1.
export function initGalaxy() {
  const el = _galaxy();
  if (!el) return;
  el.style.opacity = "1";
}

export function hideGalaxy() {
  const el = _galaxy();
  if (!el) return;
  el.style.opacity = "0";
}

export function showGalaxy() {
  const el = _galaxy();
  if (!el) return;
  el.style.opacity = "1";
}