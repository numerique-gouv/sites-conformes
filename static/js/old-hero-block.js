class OldHeroBlockDefinition extends window.wagtailStreamField.blocks
  .StructBlockDefinition {
  render(placeholder, prefix, initialState, initialError) {
    const block = super.render(placeholder, prefix, initialState, initialError);
    console.log(block);

    block.container[0]
      .querySelectorAll("input, textarea, select, button, label")
      .forEach((el) => {
        el.setAttribute("readonly", "true");
        el.style.pointerEvents = "none";
        el.style.opacity = "0.6";
      });

    const draftEditors = block.container[0].querySelectorAll(
      '.public-DraftEditor-content[contenteditable="true"]'
    );

    draftEditors.forEach((el) => {
      el.style.backgroundColor = "#f5f5f5";
      el.style.pointerEvents = "none";
    });

    return block;
  }
}
window.telepath.register("blocks.OldHero", OldHeroBlockDefinition);
