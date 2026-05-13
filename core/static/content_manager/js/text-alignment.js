(function() {
    'use strict';

    const ALIGNMENTS = ['left', 'center', 'right'];

    function resetAlignmentsInEditor(editorContainer) {
        if (editorContainer) {
            editorContainer.querySelectorAll('*').forEach(function(el) {
                const currentAlign = el.style.textAlign;
                if (currentAlign && ALIGNMENTS.indexOf(currentAlign) !== -1) {
                    el.style.textAlign = '';
                }
            });
        }
    }

    function updateBlockAlignmentInEditor(editorRoot) {
        resetAlignmentsInEditor(editorRoot);

        const contentBlocks = editorRoot.querySelectorAll(
            '[data-contents="true"] [data-block="true"], .public-DraftStyleDefault-block'
        );
        contentBlocks.forEach(function(block) {
            let alignment = null;
            let checkElement = block;

            while (checkElement && !alignment) {
                const blockType = checkElement.getAttribute('data-block-type');

                // Check for text-left, text-center, or text-right block types
                for (let i = 0; i < ALIGNMENTS.length; i++) {
                    const align = ALIGNMENTS[i];
                    if (blockType === 'text-' + align ||
                        (checkElement.classList && checkElement.classList.contains('Draftail-block--text-' + align))) {
                        alignment = align;
                        break;
                    }
                }

                checkElement = checkElement.parentElement;
                if (checkElement === editorRoot) {
                    break;
                }
            }

            if (alignment) {
                block.style.textAlign = alignment;
                block.querySelectorAll('*').forEach(function(child) {
                    child.style.textAlign = alignment;
                });
            }
        });

        // Also apply to blocks with alignment data attributes or classes
        ALIGNMENTS.forEach(function(align) {
            const selector = '[data-block-type="text-' + align + '"], .Draftail-block--text-' + align;
            editorRoot.querySelectorAll(selector).forEach(function(block) {
                block.style.textAlign = align;
                block.querySelectorAll('*').forEach(function(child) {
                    child.style.textAlign = align;
                });
            });
        });
    }

    function updateAllEditors() {
        document.querySelectorAll('.DraftEditor-root, .Draftail-Editor').forEach(function(editor) {
            updateBlockAlignmentInEditor(editor);
        });
    }

    let updateTimeout;
    const observer = new MutationObserver(function(mutations) {
        clearTimeout(updateTimeout);
        updateTimeout = setTimeout(function() {
            updateAllEditors();
        }, 50);
    });

    function startObserving() {
        observer.observe(document.body, {
            childList: true,
            subtree: true,
            attributes: true,
            attributeFilter: ['data-block-type', 'class']
        });
        updateAllEditors();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', startObserving);
    } else {
        startObserving();
    }

    // Check for dynamically added editors after initial load
    setTimeout(startObserving, 500);
})();
