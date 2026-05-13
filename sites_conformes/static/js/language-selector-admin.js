document.addEventListener("DOMContentLoaded", function () {
  const modeSelect = document.querySelector("#id_language_selector_mode");
  if (!modeSelect) return;

  const totalFormsInput = document.querySelector(
    "#id_language_selector_items-TOTAL_FORMS",
  );
  const itemsBlock = totalFormsInput
    ? totalFormsInput.closest(".w-panel__wrapper")
    : null;

  function toggleItemsBlock() {
    if (!itemsBlock) return;
    itemsBlock.style.display = modeSelect.value === "manual" ? "" : "none";
  }

  toggleItemsBlock();
  modeSelect.addEventListener("change", toggleItemsBlock);

  function toggleLinkFields(itemElement) {
    const linkTypeSelect = itemElement.querySelector(
      '[data-contentpath="link_type"] select',
    );
    if (!linkTypeSelect) return;

    const pageWrapper = itemElement
      .querySelector('[data-contentpath="page"]')
      ?.closest(".w-panel__wrapper");
    const urlWrapper = itemElement
      .querySelector('[data-contentpath="external_url"]')
      ?.closest(".w-panel__wrapper");

    function toggle() {
      const value = linkTypeSelect.value;
      if (pageWrapper)
        pageWrapper.style.display = value === "page" ? "" : "none";
      if (urlWrapper)
        urlWrapper.style.display = value === "external_url" ? "" : "none";
    }

    toggle();
    linkTypeSelect.addEventListener("change", toggle);
  }

  document
    .querySelectorAll("[data-inline-panel-child]")
    .forEach(function (item) {
      toggleLinkFields(item);
    });

  document.addEventListener("w-formset:added", function (event) {
    toggleLinkFields(event.target);
  });
});
