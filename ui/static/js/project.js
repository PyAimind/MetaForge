import { getProject, listModules } from "./api.js";
import { showCode, clearCode } from "./code_viewer.js";
import { showGalaxy } from "./galaxy.js";

function _renderModules(projectId, modules) {
  const list = document.getElementById("modules-list");
  if (!list) return;
  list.innerHTML = "";

  if (!modules || modules.length === 0) {
    const empty = document.createElement("div");
    empty.className = "module-item empty";
    empty.textContent = "No modules yet";
    list.appendChild(empty);
    return;
  }

  for (const mod of modules) {
    const item = document.createElement("div");
    item.className = "module-item";
    item.textContent = mod.name;
    item.dataset.name = mod.name;
    item.addEventListener("click", () => {
      _selectModule(item);
      showCode(projectId, mod.name);
    });
    list.appendChild(item);
  }
}

function _selectModule(selectedItem) {
  const list = document.getElementById("modules-list");
  if (!list) return;
  for (const item of list.querySelectorAll(".module-item")) {
    item.classList.remove("selected");
  }
  selectedItem.classList.add("selected");
}

function _setProjectHeader(meta) {
  const title = document.getElementById("project-title");
  const status = document.getElementById("project-status");
  if (title) title.textContent = meta.name || "Untitled";
  if (status) status.textContent = meta.status || "";
}

function showProjectView() {
  const home = document.getElementById("view-home");
  const project = document.getElementById("view-project");
  if (home) home.style.display = "none";
  if (project) project.style.display = "flex";
}

export function showHomeView() {
  const home = document.getElementById("view-home");
  const project = document.getElementById("view-project");
  if (home) home.style.display = "flex";
  if (project) project.style.display = "none";
  clearCode();
  showGalaxy();
}

export async function openProject(projectId) {
  try {
    const meta = await getProject(projectId);
    _setProjectHeader(meta);
    clearCode();
    showProjectView();

    const modules = await listModules(projectId);
    _renderModules(projectId, modules);
  } catch (err) {
    alert(`Failed to open project: ${err.message}`);
  }
}

export function initProject() {
  const back = document.getElementById("project-back");
  if (back) back.addEventListener("click", showHomeView);

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    const projectView = document.getElementById("view-project");
    if (projectView && projectView.style.display !== "none") {
      showHomeView();
    }
  });
}