window.addEventListener('DOMContentLoaded', () => {
  const previewPanel = document.querySelector('[data-side-panel="preview"]');

  if (previewPanel) {
    try {
      if (!localStorage.getItem('wagtail:side-panel-width')) {
        const width = Math.round(window.innerWidth * 0.6); 
        localStorage.setItem('wagtail:side-panel-width', width.toString());
      }
      if (!localStorage.getItem('wagtail:preview-panel-device')) {
        localStorage.setItem('wagtail:preview-panel-device', "desktop");
      }
    } catch (e) {
    }

    previewPanel.dispatchEvent(new CustomEvent('open'));

    const isEditOrAddPage = /\/(edit|add)\//.test(window.location.pathname);

    if (isEditOrAddPage) {
      setTimeout(() => {
        const sidebarAlreadyCollapsed = document.body.classList.contains('sidebar-collapsed');
        const toggleButton = document.querySelector('button.sidebar__collapse-toggle');

        if (!sidebarAlreadyCollapsed && toggleButton) {
          toggleButton.click();
        }
      }, 300);
    }
  }
});