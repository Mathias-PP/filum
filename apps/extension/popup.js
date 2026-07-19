"use strict";

const DEFAULTS = {
  apiBase: "https://philum-api.duckdns.org",
  frontendBase: "https://filum-eight.vercel.app",
};

const CATEGORIES = [
  ["article-scientifique", "Article scientifique"],
  ["preprint", "Préprint"],
  ["article-presse", "Article de presse"],
  ["communique", "Communiqué"],
  ["documentaire", "Documentaire"],
  ["interview", "Interview"],
  ["podcast", "Podcast"],
  ["blog", "Blog"],
  ["post-social", "Post réseau social"],
  ["livre", "Livre"],
  ["page-web", "Page web"],
  ["notes", "Notes"],
];

const FORMATS = [
  ["texte", "Texte"],
  ["video", "Vidéo"],
  ["image", "Image"],
  ["audio", "Audio"],
  ["data", "Données"],
];

const AUTHOR_KINDS = [
  ["chercheur", "Chercheur·euse"],
  ["media", "Média"],
  ["institution-publique", "Institution publique"],
  ["gouvernement", "Gouvernement"],
  ["ecole", "École"],
  ["laboratoire", "Laboratoire"],
  ["entreprise", "Entreprise"],
  ["asso", "Association"],
  ["individu", "Individu"],
];

const $ = (id) => document.getElementById(id);

function show(stateId) {
  for (const id of ["state-loading", "state-logged-out", "state-error", "state-form"]) {
    $(id).classList.toggle("hidden", id !== stateId);
  }
}

function fillSelect(select, options, selected) {
  select.innerHTML = "";
  for (const [value, label] of options) {
    const opt = document.createElement("option");
    opt.value = value;
    opt.textContent = label;
    if (value === selected) opt.selected = true;
    select.appendChild(opt);
  }
}

async function getSettings() {
  const stored = await chrome.storage.sync.get(DEFAULTS);
  return { ...DEFAULTS, ...stored };
}

async function api(base, path, init = {}) {
  const resp = await fetch(`${base}/api/v1${path}`, {
    credentials: "include",
    ...init,
  });
  return resp;
}

async function getActiveTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab;
}

function guessTaxonomy(url) {
  const guess = { category: "page-web", format: "texte", author_kind: "individu" };
  try {
    const host = new URL(url).hostname.replace(/^www\./, "");
    if (/youtube\.com|youtu\.be|vimeo\.com/.test(host)) {
      return { category: "documentaire", format: "video", author_kind: "individu" };
    }
    if (/doi\.org|arxiv\.org|pubmed|sciencedirect|springer|nature\.com|wiley/.test(host)) {
      return { category: "article-scientifique", format: "texte", author_kind: "chercheur" };
    }
  } catch {
    /* URL invalide : défauts */
  }
  return guess;
}

async function init() {
  const settings = await getSettings();
  $("login-link").href = settings.frontendBase;
  $("settings-btn").addEventListener("click", () => chrome.runtime.openOptionsPage());

  let me;
  try {
    me = await api(settings.apiBase, "/auth/me");
  } catch {
    $("error-message").textContent =
      `Impossible de joindre l'API (${settings.apiBase}). Vérifiez les réglages.`;
    show("state-error");
    return;
  }
  if (me.status === 401) {
    show("state-logged-out");
    return;
  }
  if (!me.ok) {
    $("error-message").textContent = `Erreur API (${me.status}).`;
    show("state-error");
    return;
  }

  const tab = await getActiveTab();
  if (!tab || !tab.url || !/^https?:\/\//.test(tab.url)) {
    $("error-message").textContent =
      "Cette page ne peut pas être ajoutée comme source (URL non http/https).";
    show("state-error");
    return;
  }

  const cardsResp = await api(settings.apiBase, "/cards?limit=100");
  if (!cardsResp.ok) {
    $("error-message").textContent = "Impossible de charger vos fiches.";
    show("state-error");
    return;
  }
  const cards = await cardsResp.json();
  if (cards.length === 0) {
    $("error-message").textContent =
      "Vous n'avez aucune fiche. Créez-en une sur Philum d'abord.";
    show("state-error");
    return;
  }

  const { lastCardId } = await chrome.storage.sync.get({ lastCardId: null });
  fillSelect(
    $("card-select"),
    cards.map((c) => [c.id, `${c.title}${c.status === "draft" ? " (brouillon)" : ""}`]),
    lastCardId,
  );

  $("page-title").textContent = tab.title || tab.url;
  $("page-url").textContent = tab.url;
  $("title-input").value = tab.title || "";

  const guess = guessTaxonomy(tab.url);
  fillSelect($("category-select"), CATEGORIES, guess.category);
  fillSelect($("format-select"), FORMATS, guess.format);
  fillSelect($("author-kind-select"), AUTHOR_KINDS, guess.author_kind);
  show("state-form");

  // Enrichissement best-effort via l'endpoint public d'extraction.
  api(settings.apiBase, `/sources/extract?url=${encodeURIComponent(tab.url)}`)
    .then(async (r) => {
      if (!r.ok) return;
      const meta = await r.json();
      if (meta.title) $("title-input").value = meta.title;
      if (meta.authors) $("authors-input").value = meta.authors;
      if (meta.category) fillSelect($("category-select"), CATEGORIES, meta.category);
      if (meta.format) fillSelect($("format-select"), FORMATS, meta.format);
      if (meta.author_kind) fillSelect($("author-kind-select"), AUTHOR_KINDS, meta.author_kind);
    })
    .catch(() => {});

  $("state-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = $("submit-btn");
    const feedback = $("form-feedback");
    btn.disabled = true;
    feedback.classList.add("hidden");

    const cardId = $("card-select").value;
    const payload = {
      url: tab.url,
      title: $("title-input").value.trim() || null,
      authors: $("authors-input").value.trim() || null,
      format: $("format-select").value,
      category: $("category-select").value,
      author_kind: $("author-kind-select").value,
      annotation: $("annotation-input").value.trim() || null,
    };

    try {
      const resp = await api(
        settings.apiBase,
        `/sources?card_id=${encodeURIComponent(cardId)}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        },
      );
      if (resp.ok) {
        await chrome.storage.sync.set({ lastCardId: cardId });
        feedback.textContent = "Source ajoutée ✓";
        feedback.className = "feedback ok";
        btn.textContent = "Ajoutée";
      } else {
        const body = await resp.json().catch(() => null);
        feedback.textContent =
          body?.error?.message || `Échec de l'ajout (${resp.status}).`;
        feedback.className = "feedback err";
        btn.disabled = false;
      }
    } catch {
      feedback.textContent = "Erreur réseau — la source n'a pas été ajoutée.";
      feedback.className = "feedback err";
      btn.disabled = false;
    }
  });
}

init();
