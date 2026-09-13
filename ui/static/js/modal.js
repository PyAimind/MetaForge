let _resolve = null;

function _elements() {
  return {
    modal: document.getElementById("modal"),
    title: document.getElementById("modal-title"),
    message: document.getElementById("modal-message"),
    input: document.getElementById("modal-input"),
    cancel: document.getElementById("modal-cancel"),
    confirm: document.getElementById("modal-confirm"),
    backdrop: document.querySelector(".modal-backdrop"),
  };
}

function _close(value) {
  const el = _elements();
  if (el.modal) el.modal.style.display = "none";
  const r = _resolve;
  _resolve = null;
  if (r) r(value);
}

function _open({ title, message, defaultValue = null, confirmLabel = "Confirm", danger = false }) {
  return new Promise((resolve) => {
    _resolve = resolve;
    const el = _elements();
    if (!el.modal) { resolve(null); return; }

    if (el.title) el.title.textContent = title || "";
    if (el.message) el.message.textContent = message || "";
    if (el.confirm) {
      el.confirm.textContent = confirmLabel;
      el.confirm.classList.toggle("danger", danger);
    }

    const hasInput = defaultValue !== null;
    if (el.input) {
      el.input.style.display = hasInput ? "block" : "none";
      el.input.value = hasInput ? defaultValue : "";
    }

    el.modal.style.display = "flex";
    if (hasInput && el.input) {
      setTimeout(() => el.input.focus(), 50);
    }
  });
}

function _init() {
  const el = _elements();
  if (!el.modal || el.modal.dataset.wired === "yes") return;
  el.modal.dataset.wired = "yes";

  el.cancel.addEventListener("click", () => _close(null));
  el.backdrop.addEventListener("click", () => _close(null));
  el.confirm.addEventListener("click", () => {
    const hasInput = el.input && el.input.style.display !== "none";
    _close(hasInput ? el.input.value : true);
  });

  document.addEventListener("keydown", (e) => {
    if (el.modal.style.display === "none") return;
    if (e.key === "Escape") _close(null);
    if (e.key === "Enter" && el.input && el.input.style.display !== "none") {
      _close(el.input.value);
    }
  });
}

export function promptDialog(title, defaultValue = "") {
  _init();
  return _open({
    title,
    message: "",
    defaultValue,
    confirmLabel: "Save",
  });
}

export function confirmDialog(title, message, danger = false) {
  _init();
  return _open({
    title,
    message,
    defaultValue: null,
    confirmLabel: danger ? "Delete" : "Confirm",
    danger,
  });
}