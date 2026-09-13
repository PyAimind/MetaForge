import { createProject, listProjects, renameProject, deleteProject } from "./api.js";
import { initGalaxy, hideGalaxy, showGalaxy } from "./galaxy.js";
import { initHome } from "./home.js";
import { initProject, openProject, showHomeView } from "./project.js";
import { promptDialog, confirmDialog } from "./modal.js";
import {
  initThinking,
  connectToRun,
  disconnect as disconnectThinking,
  restoreIfActive,
} from "./thinking.js";

let _pollTimer = null;
let _currentProjectId = null;

function _defaultName(idea) {
  const trimmed = idea.trim();
  if (trimmed.length <= 40) return trimmed;
  return trimmed.slice(0, 40);
}

function _closeDrawer() {
  const drawer = document.getElementById("drawer");
  const overlay = document.getElementById("overlay");
  if (drawer) drawer.classList.remove("open");
  if (overlay) overlay.classList.remove("open");
}

function _makeStatusBadge(status) {
  const badge = document.createElement("span");
  badge.className = "project-status-badge " + (status || "pending");
  badge.textContent = status || "pending";
  return badge;
}

async function _onRename(projectId, currentName) {
  const newName = await promptDialog("Rename project", currentName || "");
  if (!newName || !newName.trim()) return;
  if (newName.trim() === currentName) return;
  try {
    await renameProject(projectId, newName.trim());
    loadProjects();
  } catch (err) {
    alert(`Failed to rename: ${err.message}`);
  }
}

async function _onDelete(projectId, currentName) {
  const ok = await confirmDialog(
    "Delete project",
    `"${currentName}" will be permanently removed. This cannot be undone.`,
    true
  );
  if (!ok) return;
  try {
    await deleteProject(projectId);
    if (_currentProjectId === projectId) {
      _currentProjectId = null;
      showHomeView();
    }
    loadProjects();
  } catch (err) {
    alert(`Failed to delete: ${err.message}`);
  }
}

function _makeProjectItem(project) {
  const item = document.createElement("div");
  item.className = "project-item";
  item.dataset.id = project.id;

  const main = document.createElement("div");
  main.className = "project-item-main";

  const name = document.createElement("span");
  name.className = "project-name";
  name.textContent = project.name || project.id;
  main.appendChild(name);
  main.appendChild(_makeStatusBadge(project.status));

  const actions = document.createElement("div");
  actions.className = "project-item-actions";

  const renameBtn = document.createElement("button");
  renameBtn.className = "project-action rename";
  renameBtn.title = "Rename";
  renameBtn.textContent = "✎";
  renameBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    _onRename(project.id, project.name);
  });

  const deleteBtn = document.createElement("button");
  deleteBtn.className = "project-action delete";
  deleteBtn.title = "Delete";
  deleteBtn.textContent = "×";
  deleteBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    _onDelete(project.id, project.name || project.id);
  });

  actions.appendChild(renameBtn);
  actions.appendChild(deleteBtn);

  item.appendChild(main);
  item.appendChild(actions);

  item.addEventListener("click", () => {
    _currentProjectId = project.id;
    _closeDrawer();
    hideGalaxy();
    openProject(project.id);
  });

  return item;
}

function _renderProjects(projects) {
  const list = document.getElementById("projects-list");
  if (!list) return;
  list.innerHTML = "";
  for (const project of projects) {
    list.appendChild(_makeProjectItem(project));
  }
}

async function loadProjects() {
  try {
    const projects = await listProjects();
    _renderProjects(projects);
    const anyRunning = projects.some((p) => p.status === "running");
    if (anyRunning && !_pollTimer) {
      _pollTimer = setInterval(loadProjects, 3000);
    } else if (!anyRunning && _pollTimer) {
      clearInterval(_pollTimer);
      _pollTimer = null;
    }
  } catch (error) {
    console.error("Failed to load projects:", error);
  }
}

async function handleIdea(idea) {
  const name = _defaultName(idea);
  try {
    const result = await createProject(name, idea);
    hideGalaxy();
    connectToRun(result.id);
    loadProjects();
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

  if (toggle) {
    toggle.addEventListener("click", () => {
      drawer.classList.toggle("open");
      if (overlay) overlay.classList.toggle("open");
      if (drawer.classList.contains("open")) loadProjects();
    });
  }
  if (closeBtn) closeBtn.addEventListener("click", _closeDrawer);
  if (overlay) overlay.addEventListener("click", _closeDrawer);
  if (newBtn) {
    newBtn.addEventListener("click", () => {
      _closeDrawer();
      _currentProjectId = null;
      disconnectThinking();
      showHomeView();
      showGalaxy();
      if (ideaInput) ideaInput.focus();
    });
  }
}



async function main() {
  initGalaxy();
  initProject();
  initThinking();
  initDrawer();
  initHome({ onIdeaSubmitted: handleIdea });
  loadProjects();



  const restored = await restoreIfActive();
  if (restored) {
    hideGalaxy();
  }
}

main();