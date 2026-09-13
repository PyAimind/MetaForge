import { getModule } from "./api.js";

function _setFilename(name) {
  const el = document.getElementById("code-filename");
  if (el) el.textContent = name || "Select a module";
}

function _setContent(code) {
  const el = document.getElementById("code-content");
  if (!el) return;
  if (window.hljs) {
    const result = window.hljs.highlight(code, { language: "python" });
    el.innerHTML = result.value;
    el.className = "code-content hljs language-python";
  } else {
    el.textContent = code;
    el.className = "code-content";
  }
}

function _setError(message) {
  _setFilename("Error");
  const el = document.getElementById("code-content");
  if (!el) return;
  el.textContent = `// ${message}`;
  el.className = "code-content";
}

async function _copyToClipboard(text, button) {
  const original = button.textContent;
  try {
    await navigator.clipboard.writeText(text);
    button.textContent = "Copied!";
  } catch (err) {
    const ta = document.createElement("textarea");
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand("copy"); } catch (e) { /* ignore */ }
    document.body.removeChild(ta);
    button.textContent = "Copied!";
  }
  setTimeout(() => { button.textContent = original; }, 1500);
}

function _wireCopyButton(code) {
  const btn = document.getElementById("code-copy");
  if (!btn) return;
  btn.hidden = false;
  btn.onclick = () => _copyToClipboard(code, btn);
}

export async function showCode(projectId, filename) {
  try {
    const data = await getModule(projectId, filename);
    _setFilename(data.name);
    _setContent(data.content);
    _wireCopyButton(data.content);
  } catch (err) {
    _setError(err.message);
    const btn = document.getElementById("code-copy");
    if (btn) btn.hidden = true;
  }
}

export function clearCode() {
  _setFilename("Select a module");
  _setContent("");
  const btn = document.getElementById("code-copy");
  if (btn) btn.hidden = true;
}