/* ═══════════════════════════════════════════════════════════════
   Semetra.ch — i18n (Deutsch / English)
   Lightweight language switcher for the static marketing site.

   New toggle (DE|EN pill):
     <div class="lang-switch" onclick="toggleLang()">
       <span class="lang-opt" data-lang="de">DE</span>
       <span class="lang-opt" data-lang="en">EN</span>
     </div>

   Legacy toggle (still supported):
     <button class="lang-toggle" onclick="toggleLang()">DE</button>

   Text translation:
     <span data-de="Deutsch" data-en="English"></span>
   ═══════════════════════════════════════════════════════════════ */

const LANG_KEY = "semetra_lang";
const SUPPORTED = ["de", "en"];
const DEFAULT_LANG = "de";

function getLang() {
  const stored = localStorage.getItem(LANG_KEY);
  if (stored && SUPPORTED.includes(stored)) return stored;
  const browser = (navigator.language || "de").slice(0, 2).toLowerCase();
  return SUPPORTED.includes(browser) ? browser : DEFAULT_LANG;
}

function setLang(lang) {
  if (!SUPPORTED.includes(lang)) return;
  localStorage.setItem(LANG_KEY, lang);
  applyLang(lang);
}

function toggleLang() {
  const current = getLang();
  setLang(current === "de" ? "en" : "de");
}

function applyLang(lang) {
  // 1. Set html lang
  document.documentElement.lang = lang;

  // 2. Translate data-de / data-en text
  document.querySelectorAll("[data-de][data-en]").forEach(function (el) {
    // Skip elements that are lang-opt pills (they always show DE/EN)
    if (el.classList.contains("lang-opt")) return;
    el.textContent = el.getAttribute("data-" + lang);
  });

  // 3. Translate data-de-html / data-en-html (HTML content)
  document.querySelectorAll("[data-de-html][data-en-html]").forEach(function (el) {
    el.innerHTML = el.getAttribute("data-" + lang + "-html");
  });

  // 4. Toggle visibility classes
  document.querySelectorAll(".lang-de").forEach(function (el) {
    el.style.display = lang === "de" ? "" : "none";
  });
  document.querySelectorAll(".lang-en").forEach(function (el) {
    el.style.display = lang === "en" ? "" : "none";
  });

  // 5. Update new DE|EN pill toggles — highlight active
  document.querySelectorAll(".lang-opt").forEach(function (opt) {
    if (opt.getAttribute("data-lang") === lang) {
      opt.classList.add("active");
    } else {
      opt.classList.remove("active");
    }
  });

  // 6. Update legacy toggle buttons
  document.querySelectorAll(".lang-toggle, .lang-toggle-light").forEach(function (btn) {
    btn.textContent = lang === "de" ? "Deutsch" : "English";
    btn.setAttribute("title", lang === "de" ? "Switch to English" : "Auf Deutsch wechseln");
  });

  // 7. Update placeholders
  document.querySelectorAll("[data-de-placeholder][data-en-placeholder]").forEach(function (el) {
    el.placeholder = el.getAttribute("data-" + lang + "-placeholder");
  });

  // 8. Update title
  var titleEl = document.querySelector("title[data-de][data-en]");
  if (titleEl) {
    document.title = titleEl.getAttribute("data-" + lang);
  }

  // 9. Update meta description
  var metaDesc = document.querySelector('meta[name="description"][data-de][data-en]');
  if (metaDesc) {
    metaDesc.setAttribute("content", metaDesc.getAttribute("data-" + lang));
  }
}

// Init
document.addEventListener("DOMContentLoaded", function () {
  applyLang(getLang());
});
