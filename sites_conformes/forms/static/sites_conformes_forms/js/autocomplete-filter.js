// Restricts the autocomplete options of a form field to those compatible with its field type.
(function () {
  "use strict";

  // Field types for which the autocomplete value cannot be left empty (see MANDATORY_AUTOCOMPLETE)
  const MANDATORY_AUTOCOMPLETE = { email: "email" };

  function getAutocompleteSelect(fieldTypeSelect) {
    const prefix = fieldTypeSelect.name.replace(/field_type$/, "");
    return document.querySelector(`select[name="${prefix}autocomplete"]`);
  }

  function getFieldTypeSelect(autocompleteSelect) {
    const prefix = autocompleteSelect.name.replace(/autocomplete$/, "");
    return document.querySelector(`select[name="${prefix}field_type"]`);
  }

  function filterOptions(fieldTypeSelect, autocompleteSelect) {
    if (!fieldTypeSelect || !autocompleteSelect) return;

    const fieldType = fieldTypeSelect.value;
    const mandatoryValue = MANDATORY_AUTOCOMPLETE[fieldType];

    for (const option of autocompleteSelect.options) {
      let visible;
      if (!option.value) {
        visible = !mandatoryValue;
      } else {
        const fieldTypes = (option.dataset.fieldTypes || "").split(" ");
        visible = fieldTypes.includes(fieldType);
      }
      option.hidden = !visible;
      option.disabled = !visible;
    }

    for (const group of autocompleteSelect.querySelectorAll("optgroup")) {
      group.hidden = !Array.from(group.children).some((option) => !option.hidden);
    }

    const selected = autocompleteSelect.selectedOptions[0];
    if (!selected || selected.disabled) {
      autocompleteSelect.value = mandatoryValue || "";
    }
  }

  function isFieldTypeSelect(element) {
    return element instanceof HTMLSelectElement && /^form_fields-.+-field_type$/.test(element.name);
  }

  function isAutocompleteSelect(element) {
    return element instanceof HTMLSelectElement && /^form_fields-.+-autocomplete$/.test(element.name);
  }

  document.addEventListener("change", (event) => {
    if (isFieldTypeSelect(event.target)) {
      filterOptions(event.target, getAutocompleteSelect(event.target));
    }
  });

  // Covers inline children added dynamically after page load
  document.addEventListener("focusin", (event) => {
    if (isAutocompleteSelect(event.target)) {
      filterOptions(getFieldTypeSelect(event.target), event.target);
    }
  });

  function filterAll() {
    document.querySelectorAll('select[name^="form_fields-"][name$="-field_type"]').forEach((select) => {
      filterOptions(select, getAutocompleteSelect(select));
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", filterAll);
  } else {
    filterAll();
  }
})();
