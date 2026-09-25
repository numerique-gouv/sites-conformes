// Stimulus controller for the category tree listing: drop a category on another one to make it a
// child, or on the root zone to make it a root. The server does the move; the page reloads to show it.
class CategoryTreeController extends window.StimulusModule.Controller {
  static values = { moveUrl: String };

  connect() {
    this.dragged = null;
  }

  start(event) {
    const row = event.target.closest(".sf-category-tree__row");
    if (!row) return;
    this.dragged = row.closest("[data-node]");
    this.dragged.classList.add("is-dragging");
    event.dataTransfer.effectAllowed = "move";
  }

  end() {
    this.clearHighlight();
    this.dragged?.classList.remove("is-dragging");
    this.dragged = null;
  }

  over(event) {
    const target = this.dropTarget(event);
    if (!target) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
    this.clearHighlight();
    target.classList.add("is-drop-target");
  }

  async drop(event) {
    const target = this.dropTarget(event);
    if (!target) return;
    event.preventDefault();
    const body = new FormData();
    body.append("node", this.dragged.dataset.node);
    if (target.dataset.node) body.append("target", target.dataset.node);
    await fetch(this.moveUrlValue, {
      method: "POST",
      body,
      headers: { "X-CSRFToken": window.wagtailConfig.CSRF_TOKEN },
    });
    window.location.reload(); // success or error, the server left a message to display
  }

  // The node or root zone under the pointer, unless it is the dragged node or one of its descendants.
  dropTarget(event) {
    const target = event.target.closest("[data-node], [data-root-zone]");
    if (!this.dragged || !target || target === this.dragged || this.dragged.contains(target)) return null;
    return target;
  }

  clearHighlight() {
    this.element.querySelectorAll(".is-drop-target").forEach((el) => el.classList.remove("is-drop-target"));
  }
}

window.wagtail.app.register("sf-category-tree", CategoryTreeController);
