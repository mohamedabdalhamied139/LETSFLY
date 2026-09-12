// Accessibility & Language Switcher Logic for LetsFly Web & Help Center
document.addEventListener("DOMContentLoaded", () => {
    // Check saved language or default to Arabic
    const savedLang = localStorage.getItem("letsfly_lang") || "ar";
    switchLanguage(savedLang);

    // Bind lang buttons
    document.querySelectorAll(".lang-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            const lang = btn.getAttribute("data-lang");
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

    // Update active button state
    document.querySelectorAll(".lang-btn").forEach(btn => {
        const isCurrent = btn.getAttribute("data-lang") === lang;
        btn.classList.toggle("active", isCurrent);
        btn.setAttribute("aria-pressed", isCurrent ? "true" : "false");
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
