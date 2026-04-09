(function () {
  const observer = new MutationObserver(function (mutations, obs) {
    const footer = document.querySelector(".sidebar-sub-menu-panel__footer");
    if (footer) {
      if (!footer.querySelector(".custom-version-info")) {
        const extra = document.createElement("p");
        extra.className = "custom-version-info";
        extra.style.cssText =
          "font-size: 0.75rem; color: var(--color-grey-400); margin-top: 4px;";
        extra.textContent = "Sites Conformes - " + window.__version__;
        footer.appendChild(extra);
      }
      obs.disconnect();
    }
  });

  observer.observe(document.body, {
    childList: true,
    subtree: true,
  });
})();
