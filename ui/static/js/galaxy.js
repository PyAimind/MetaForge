// Atmospheric fog background for the home screen.

const GALAXY_ID = "galaxy";
let _galaxyEl = null;

export function initGalaxy() {
  _galaxyEl = document.getElementById(GALAXY_ID);
  if (!_galaxyEl) return;
  _galaxyEl.style.opacity = "1";
  _galaxyEl.classList.add("fog-active");
}

export function hideGalaxy() {
  if (!_galaxyEl) return;
  _galaxyEl.style.opacity = "0";
}

export function showGalaxy() {
  if (!_galaxyEl) return;
  _galaxyEl.style.opacity = "1";
}