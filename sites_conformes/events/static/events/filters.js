/*
 * Progressive enhancement of the events filters form:
 * the results are updated in place on submit, without moving the focus,
 * and the number of results is announced through an aria-live region.
 * Without JS, the form is submitted as a regular GET form.
 */
let filtersForm = document.querySelector("#events-filters-form");

function build_url(form) {
    /* build the GET URL from the form, leaving out the empty values */
    let url = new URL(form.action, window.location.href);
    url.search = "";
    url.hash = "";
    for (let [name, value] of new FormData(form)) {
        if (value) {
            url.searchParams.append(name, value);
        }
    }
    return url;
}

function replace_content(doc, selector) {
    let current = document.querySelector(selector);
    let updated = doc.querySelector(selector);
    if (current && updated) {
        current.replaceWith(updated);
    }
}

if (filtersForm && "fetch" in window && "URLSearchParams" in window) {
    filtersForm.addEventListener("submit", async function (event) {
        event.preventDefault();
        let url = build_url(filtersForm);
        try {
            let response = await fetch(url);
            if (!response.ok) {
                throw new Error(response.statusText);
            }
            let doc = new DOMParser().parseFromString(await response.text(), "text/html");
            if (doc.querySelector("#events-filters-form .fr-input-group--error")) {
                // Let the full page reload display the errors and focus the first invalid field
                throw new Error("Invalid form");
            }

            // Date fields, to clear any previous error message
            let focusedId = document.activeElement ? document.activeElement.id : "";
            for (let field of ["date_from", "date_to"]) {
                let current = document.querySelector(`#id_${field}`)?.closest(".fr-fieldset__element");
                let updated = doc.querySelector(`#id_${field}`)?.closest(".fr-fieldset__element");
                if (current && updated) {
                    current.replaceWith(updated);
                }
            }
            if (focusedId && document.activeElement !== document.getElementById(focusedId)) {
                document.getElementById(focusedId)?.focus();
            }

            replace_content(doc, "#events-results");
            // The links of the other filters include the current dates in their URL
            replace_content(doc, "#events-other-filters");

            // Only the content of the live region is changed, so that it is announced
            let count = document.querySelector("#events-results-count");
            let newCount = doc.querySelector("#events-results-count");
            if (count && newCount) {
                count.textContent = newCount.textContent.trim();
            }

            document.title = doc.title;
            history.pushState(null, "", url);
        } catch (error) {
            filtersForm.submit();
        }
    });

    window.addEventListener("popstate", function () {
        window.location.reload();
    });
}
