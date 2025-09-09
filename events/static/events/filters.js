let dateFromField = document.querySelector("#id_date_from")
let dateToField = document.querySelector("#id_date_to")

function set_param_value(param, value) {
    /* update or remove a GET parameter from the current URL */
    if ('URLSearchParams' in window) {
        let searchParams = new URLSearchParams(window.location.search);
        if (value) {
            searchParams.set(param, value);
        } else {
            searchParams.delete(param);
        }
        window.location.hash = "#posts-list"
        window.location.search = searchParams.toString();
    }
}
dateFromField.addEventListener("change", function () {
    set_param_value("date_from", dateFromField.value);
});

dateToField.addEventListener("change", function () {
    set_param_value("date_to", dateToField.value);
});
