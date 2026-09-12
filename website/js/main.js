// Accessibility & Language Switcher Logic for LetsFly Web & Help Center
document.addEventListener("DOMContentLoaded", () => {
    // Check saved language or default to Arabic
    const savedLang = localStorage.getItem("letsfly_lang") || "ar";
    switchLanguage(savedLang);

    // Bind lang select combo-box
    document.querySelectorAll(".lang-select").forEach(select => {
        select.value = savedLang;
        select.addEventListener("change", (e) => {
            const lang = e.target.value;
            if (lang) {
                switchLanguage(lang);
                localStorage.setItem("letsfly_lang", lang);
            }
        });
    });
});

function switchLanguage(lang) {
    const htmlTag = document.documentElement;
    htmlTag.setAttribute("lang", lang);
    htmlTag.setAttribute("dir", lang === "ar" ? "rtl" : "ltr");

    // Update all select dropdowns
    document.querySelectorAll(".lang-select").forEach(select => {
        select.value = lang;
    });

    // Show/hide multilingual sections
    document.querySelectorAll("[data-lang-content]").forEach(el => {
        if (el.getAttribute("data-lang-content") === lang) {
            el.style.display = "";
            el.removeAttribute("aria-hidden");
        } else {
            el.style.display = "none";
            el.setAttribute("aria-hidden", "true");
        }
    });
}
