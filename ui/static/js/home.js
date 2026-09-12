export function initHome({ onIdeaSubmitted }) {
  const form = document.getElementById("idea-form");
  const input = document.getElementById("idea-input");
  if (!form || !input) return;

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const idea = input.value.trim();
    if (!idea) return;
    input.value = "";
    onIdeaSubmitted(idea);
  });
}