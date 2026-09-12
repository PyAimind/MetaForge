import { createProject, listProjects } from "./api.js";
import { initGalaxy, hideGalaxy } from "./galaxy.js";
import { initHome } from "./home.js";
import { initProject } from "./project.js";

function _defaultName(idea) {
  const trimmed = idea.trim();
  if (trimmed.length <= 40) return trimmed;
  return trimmed.slice(0, 40);
}

function _renderProjects(projects) {
  const list = document.getElementById("projects-list");
  if (!list) return;
  list.innerHTML = "";
  for (const project of projects) {
    const item = document.createElement("div");
    item.className = "project-item";
    item.dataset.id = project.id;
    item.textContent = project.name || project.id;
    list.appendChild(item);
  }
}

async function loadProjects() {
  try {
    const projects = await listProjects();
    _renderProjects(projects);
  } catch (error) {
    console.error("Failed to load projects:", error);
  }
}

async function handleIdea(idea) {
  const name = _defaultName(idea);
  try {
    await createProject(name, idea);
    hideGalaxy();
  } catch (error) {
    alert(`Failed to start project: ${error.message}`);
  }
}

function initDrawer() {
  const toggle = document.getElementById("menu-toggle");
  const drawer = document.getElementById("drawer");
  const overlay = document.getElementById("overlay");
  const closeBtn = document.getElementById("drawer-close");
  const newBtn = document.getElementById("new-project");
  const ideaInput = document.getElementById("idea-input");
  if (!drawer) return;

  const close = () => {
    drawer.classList.remove("open");
    if (overlay) overlay.classList.remove("open");
  };

  if (toggle) {
    toggle.addEventListener("click", () => {
      drawer.classList.toggle("open");
      if (overlay) overlay.classList.toggle("open");
    });
  }
  if (closeBtn) closeBtn.addEventListener("click", close);
  if (overlay) overlay.addEventListener("click", close);
  if (newBtn) {
    newBtn.addEventListener("click", () => {
      close();
      if (ideaInput) ideaInput.focus();
    });
  }
}

function main() {
  initGalaxy();
  initProject();
  initDrawer();
  initHome({ onIdeaSubmitted: handleIdea });
  loadProjects();
}

main();