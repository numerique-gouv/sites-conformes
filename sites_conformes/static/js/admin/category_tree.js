// Drag-and-drop nesting for the category tree listing: drop a category on another one to make it a
// child, or on the root zone to make it a root. The server does the move; the page reloads to show it.
(() => {
  const tree = document.querySelector("[data-category-tree]");
  if (!tree) return;

  let dragged = null;

  const targetOf = (event) => event.target.closest("[data-node], [data-root-zone]");
  const canDrop = (target) => dragged && target && target !== dragged && !dragged.contains(target);
  const clearHighlight = () => tree.querySelectorAll(".is-drop-target").forEach((el) => el.classList.remove("is-drop-target"));

  tree.addEventListener("dragstart", (event) => {
    const row = event.target.closest(".sf-category-tree__row");
    if (!row) return;
    dragged = row.closest("[data-node]");
    dragged.classList.add("is-dragging");
    event.dataTransfer.effectAllowed = "move";
  });

  tree.addEventListener("dragend", () => {
    clearHighlight();
    dragged?.classList.remove("is-dragging");
    dragged = null;
  });

  tree.addEventListener("dragover", (event) => {
    const target = targetOf(event);
    if (!canDrop(target)) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
    clearHighlight();
    target.classList.add("is-drop-target");
  });

  tree.addEventListener("drop", async (event) => {
    const target = targetOf(event);
    if (!canDrop(target)) return;
    event.preventDefault();
    const body = new FormData();
    body.append("node", dragged.dataset.node);
    if (target.dataset.node) body.append("target", target.dataset.node);
    await fetch(tree.dataset.moveUrl, { method: "POST", body, headers: { "X-CSRFToken": tree.dataset.csrf } });
    window.location.reload(); // success or error, the server left a message to display
  });
})();
