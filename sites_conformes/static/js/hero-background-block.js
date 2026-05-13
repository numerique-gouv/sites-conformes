class HeroBackgroundBlock {
  constructor(block) {
    this.block = block;
  }

  initialize() {
    const container = this.block.container?.[0];
    if (!container) return;

    const selector = container.querySelector(
      `[name$="background_color_or_image"]`
    );
    if (!selector) return;

    const imageField = container.querySelector(`[data-contentpath="image"]`);
    const colorField = container.querySelector(
      `[data-contentpath="background_color"]`
    );

    const updateDisplay = (value) => {
      if (imageField)
        imageField.style.display = value === "image" ? "" : "none";
      if (colorField)
        colorField.style.display = value === "color" ? "" : "none";
    };

    updateDisplay(selector.value);
    selector.addEventListener("change", (e) => updateDisplay(e.target.value));
  }
}

class HeroBackgroundBlockDefinition extends window.wagtailStreamField.blocks
  .StructBlockDefinition {
  render(placeholder, initialState, initialError) {
    const block = super.render(placeholder, initialState, initialError);
    new HeroBackgroundBlock(block).initialize();
    return block;
  }
}

window.telepath.register(
  "blocks.HeroBackgroundImageBlock",
  HeroBackgroundBlockDefinition
);
