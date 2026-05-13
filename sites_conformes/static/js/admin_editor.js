window.addEventListener('DOMContentLoaded', (event) => {
    document.querySelectorAll('input[type="url"]').forEach(input => {
        input.addEventListener('paste', function (event) {
            const pastedData = (event.clipboardData || window.clipboardData).getData('text');
            if (pastedData.length > 2000) {
                alert(gettext("Warning: this URL is longer than the 2000 character limit for URL fields."));
            }
        });
    });
});
