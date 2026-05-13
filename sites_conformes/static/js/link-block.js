class LinkBlock {
  constructor(block, meta) {
    this.block = block;
    this.container = this.block.container[0];
    this.meta = meta;
  }

  initialize() {
    this.select = this.container.querySelector("select");
    if (!this.select) {
      console.warn("Link block: select element not found.");
      return;
    }

    /* Hide all fields by default */
    const pageChooser = this.container.querySelector(
      '[data-contentpath="page"]'
    );
    if (pageChooser) pageChooser.style.display = "none";

    const urlInput = this.container.querySelector(
      '[data-contentpath="external_url"]'
    );
    if (urlInput) urlInput.style.display = "none";

    const documentChooser = this.container.querySelector(
      '[data-contentpath="document"]'
    );
    if (documentChooser) documentChooser.style.display = "none";

    const anchorInput = this.container.querySelector(
      '[data-contentpath="anchor"]'
    );
    if (anchorInput) anchorInput.style.display = "none";

    const queryInput = this.container.querySelector(
      '[data-contentpath="query_string"]'
    );
    if (pageChooser) queryInput.style.display = "none";

    let fieldsWithAnchors = ["page", "anchor"];

    const updateDisplay = (value) => {
      if (pageChooser) {
        pageChooser.style.display = value === "page" ? "block" : "none";
        queryInput.style.display = value === "page" ? "block" : "none";
      }
      if (urlInput)
        urlInput.style.display = value === "external_url" ? "block" : "none";
      if (documentChooser)
        documentChooser.style.display = value === "document" ? "block" : "none";
      if (anchorInput) {
        if (fieldsWithAnchors.includes(value)) {
          anchorInput.style.display = "block";
        } else {
          anchorInput.style.display = "none";
        }
      }

    };
    updateDisplay(this.select.value);

    this.select.addEventListener("change", function () {
      const selectedValue = this.value;
      updateDisplay(selectedValue);
    });
  }
}

class LinkBlockDefinition extends window.wagtailStreamField.blocks
  .StructBlockDefinition {
  render(placeholder, prefix, initialState, initialError) {
    if (this.meta.url_link_text_required) {
      const linkText = this.childBlockDefs.find(
        (obj) => obj.name === "link_text"
      );
      if (linkText) linkText.meta.required = true;
    }

    const block = super.render(placeholder, prefix, initialState, initialError);
    new LinkBlock(block, this.meta).initialize();
    return block;
  }
}

window.telepath.register("blocks.links.LinkBlock", LinkBlockDefinition);
