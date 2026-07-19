"use strict";

const DEFAULTS = {
  apiBase: "https://philum-api.duckdns.org",
  frontendBase: "https://filum-eight.vercel.app",
};

async function load() {
  const stored = await chrome.storage.sync.get(DEFAULTS);
  document.getElementById("api-base").value = stored.apiBase;
  document.getElementById("frontend-base").value = stored.frontendBase;
}

document.getElementById("save-btn").addEventListener("click", async () => {
  const apiBase = document.getElementById("api-base").value.trim().replace(/\/+$/, "");
  const frontendBase = document.getElementById("frontend-base").value.trim().replace(/\/+$/, "");
  await chrome.storage.sync.set({
    apiBase: apiBase || DEFAULTS.apiBase,
    frontendBase: frontendBase || DEFAULTS.frontendBase,
  });
  const status = document.getElementById("status");
  status.textContent = "Enregistré ✓";
  setTimeout(() => (status.textContent = ""), 1500);
});

load();
