// Progressive enhancement only: every page works without JavaScript.
(function () {
  "use strict";

  // Loading state: disable the submit button once the form is valid and sent.
  document.querySelectorAll("form").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      if (event.defaultPrevented) return;
      var btn = form.querySelector("button[data-loading]");
      if (btn) {
        setTimeout(function () { btn.disabled = true; btn.textContent = btn.dataset.loading; }, 0);
      }
    });
  });

  // Client-side validation for forms marked data-validate (server validates again).
  document.querySelectorAll("form[data-validate]").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      var bad = false;
      form.querySelectorAll("input, select, textarea").forEach(function (el) {
        var ok = el.checkValidity();
        el.classList.toggle("invalid", !ok);
        if (!ok) bad = true;
      });
      var pw = form.querySelector("#password"), cf = form.querySelector("#confirm_password");
      if (pw && cf && pw.value !== cf.value) { cf.classList.add("invalid"); bad = true; }
      if (bad) { event.preventDefault(); var first = form.querySelector(".invalid"); if (first) first.focus(); }
    });
  });

  // Image preview before upload.
  document.querySelectorAll("input[type=file][data-preview]").forEach(function (input) {
    var box = document.querySelector(input.dataset.preview);
    input.addEventListener("change", function () {
      box.textContent = "";
      Array.prototype.slice.call(input.files, 0, 5).forEach(function (file) {
        if (!file.type.startsWith("image/")) return;
        var img = document.createElement("img");
        img.alt = "Preview of " + file.name;
        img.src = URL.createObjectURL(file);
        box.appendChild(img);
      });
    });
  });
})();
