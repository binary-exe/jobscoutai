/* global chrome */

const DEFAULTS = {
  apiBase: "https://jobscout-api.fly.dev/api/v1",
  appBase: "https://jobscoutai.vercel.app",
  token: null,
  tokenCapturedAt: null
};

async function getState() {
  const data = await chrome.storage.local.get(DEFAULTS);
  return { ...DEFAULTS, ...data };
}

async function setState(patch) {
  await chrome.storage.local.set(patch);
}

function normalizeApiBase(url) {
  const u = String(url || "").trim().replace(/\/+$/, "");
  return u || DEFAULTS.apiBase;
}

function normalizeAppBase(url) {
  const u = String(url || "").trim().replace(/\/+$/, "");
  return u || DEFAULTS.appBase;
}

async function getActiveTab() {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  return tabs && tabs[0] ? tabs[0] : null;
}

async function executeInActiveTab(fn, args = []) {
  const tab = await getActiveTab();
  if (!tab?.id) throw new Error("No active tab found");
  const [{ result }] = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    world: "MAIN",
    func: fn,
    args
  });
  return result;
}

function _captureSupabaseAccessTokenInPage() {
  try {
    const keys = Object.keys(window.localStorage || {});
    const candidateKeys = keys.filter((k) => /^sb-.*-auth-token$/.test(k));
    for (const k of candidateKeys) {
      const raw = window.localStorage.getItem(k);
      if (!raw) continue;
      const parsed = JSON.parse(raw);
      const token = parsed?.access_token || parsed?.currentSession?.access_token;
      if (token && typeof token === "string" && token.length > 20) {
        return { ok: true, token, key: k };
      }
    }
    return { ok: false, error: "No Supabase session found. Make sure you are logged in to JobScoutAI in this tab." };
  } catch (e) {
    return { ok: false, error: e?.message || "Failed to read session token" };
  }
}

function _extractJobFromPage() {
  const stripHtml = (html) =>
    String(html || "")
      .replace(/<script[\s\S]*?>[\s\S]*?<\/script>/gi, " ")
      .replace(/<style[\s\S]*?>[\s\S]*?<\/style>/gi, " ")
      .replace(/<[^>]+>/g, " ")
      .replace(/\s+/g, " ")
      .trim();

  const firstText = (...sels) => {
    for (const sel of sels) {
      const el = document.querySelector(sel);
      const t = el?.textContent?.trim();
      if (t) return t;
    }
    return null;
  };

  const firstHref = (pred) => {
    const anchors = Array.from(document.querySelectorAll("a[href]"));
    for (const a of anchors) {
      const href = a.getAttribute("href") || "";
      const text = (a.textContent || "").trim().toLowerCase();
      if (pred({ href, text, a })) {
        try {
          return new URL(href, window.location.href).toString();
        } catch {
          return href;
        }
      }
    }
    return null;
  };

  const url = window.location.href;
  const host = window.location.hostname;

  // ---- JSON-LD (schema.org JobPosting) ----
  let jsonLdJob = null;
  try {
    const scripts = Array.from(document.querySelectorAll('script[type="application/ld+json"]'));
    for (const s of scripts) {
      const raw = s.textContent?.trim();
      if (!raw) continue;
      let parsed = null;
      try {
        parsed = JSON.parse(raw);
      } catch {
        continue;
      }
      const items = Array.isArray(parsed) ? parsed : [parsed];
      for (const item of items) {
        const t = item?.["@type"];
        const types = Array.isArray(t) ? t : [t].filter(Boolean);
        if (types.includes("JobPosting")) {
          jsonLdJob = item;
          break;
        }
      }
      if (jsonLdJob) break;
    }
  } catch {
    // ignore
  }

  let title =
    jsonLdJob?.title ||
    document.querySelector('meta[property="og:title"]')?.getAttribute("content") ||
    document.title ||
    null;
  if (title) title = String(title).replace(/\s+\|\s+LinkedIn.*/i, "").trim();

  const companyFromJsonLd = jsonLdJob?.hiringOrganization?.name || null;
  const companyFromMeta = document.querySelector('meta[property="og:site_name"]')?.getAttribute("content") || null;
  const company =
    companyFromJsonLd ||
    firstText(
      // LinkedIn
      ".jobs-unified-top-card__company-name",
      ".jobs-company__name",
      // Indeed
      '[data-testid="inlineHeader-companyName"]',
      ".jobsearch-CompanyInfoWithoutHeaderImage a",
      // Generic/ATS
      '[data-ui="job-company"]',
      ".company",
      "[itemprop='hiringOrganization']"
    ) ||
    companyFromMeta ||
    null;

  // Location (best-effort)
  let locationRaw = null;
  try {
    const jl = jsonLdJob?.jobLocation;
    const jl0 = Array.isArray(jl) ? jl[0] : jl;
    const addr = jl0?.address;
    const parts = [
      addr?.addressLocality,
      addr?.addressRegion,
      addr?.addressCountry
    ].filter(Boolean);
    if (parts.length) locationRaw = parts.join(", ");
  } catch {
    // ignore
  }
  locationRaw =
    locationRaw ||
    firstText(
      // LinkedIn
      ".jobs-unified-top-card__bullet",
      ".jobs-unified-top-card__workplace-type",
      // Indeed
      '[data-testid="job-location"]',
      ".jobsearch-JobInfoHeader-subtitle div:nth-child(2)",
      // Generic
      "[data-ui='job-location']",
      ".location"
    );

  // Description
  const descriptionHtml =
    jsonLdJob?.description ||
    document.querySelector('[data-testid="jobDescriptionText"]')?.innerHTML ||
    document.querySelector(".jobs-description-content__text")?.innerHTML ||
    document.querySelector(".show-more-less-html__markup")?.innerHTML ||
    document.querySelector("[itemprop='description']")?.innerHTML ||
    null;
  const descriptionText = stripHtml(descriptionHtml || "");

  // Apply URL (best-effort: explicit apply button/link)
  const applyUrlFromJsonLd = jsonLdJob?.url || null;
  const applyUrl =
    firstHref(({ href, text }) => {
      if (!href) return false;
      if (href.startsWith("#")) return false;
      if (text.includes("apply")) return true;
      // common ATS "apply now"
      if (text.includes("apply now")) return true;
      return false;
    }) || applyUrlFromJsonLd || url;

  // Heuristic captured_from label
  const capturedFrom = (() => {
    const h = host.toLowerCase();
    if (h.includes("linkedin.")) return "linkedin";
    if (h.includes("indeed.")) return "indeed";
    if (h.includes("greenhouse")) return "greenhouse";
    if (h.includes("lever.co")) return "lever";
    if (h.includes("workday")) return "workday";
    if (h.includes("taleo")) return "taleo";
    return "ats";
  })();

  // Basic validation
  if (!title || title.length < 2) {
    title = firstText("h1", "h2");
  }

  return {
    ok: true,
    job: {
      source: "extension",
      captured_from: capturedFrom,
      job_url: url,
      apply_url: applyUrl,
      title: title || "Untitled role",
      company: company || "Unknown company",
      location_raw: locationRaw || null,
      description_text: descriptionText || null
    }
  };
}

async function saveCapturedJob() {
  const state = await getState();
  if (!state.token) throw new Error("Not connected. Open JobScoutAI, log in, then click Connect in the extension.");

  const extraction = await executeInActiveTab(_extractJobFromPage);
  if (!extraction?.ok) throw new Error(extraction?.error || "Failed to extract job data");
  const job = extraction.job;

  const apiBase = normalizeApiBase(state.apiBase);
  const resp = await fetch(`${apiBase}/apply/job/import`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${state.token}`
    },
    body: JSON.stringify(job)
  });

  const text = await resp.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = null;
  }

  if (!resp.ok) {
    const msg = data?.detail || `Save failed (HTTP ${resp.status})`;
    throw new Error(msg);
  }

  return { ok: true, data };
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  (async () => {
    try {
      if (msg?.type === "GET_STATE") {
        const state = await getState();
        sendResponse({ ok: true, state: { ...state, token: state.token ? "present" : null } });
        return;
      }

      if (msg?.type === "SET_SETTINGS") {
        await setState({
          apiBase: normalizeApiBase(msg.apiBase),
          appBase: normalizeAppBase(msg.appBase)
        });
        sendResponse({ ok: true });
        return;
      }

      if (msg?.type === "DISCONNECT") {
        await setState({ token: null, tokenCapturedAt: null });
        sendResponse({ ok: true });
        return;
      }

      if (msg?.type === "CONNECT_FROM_ACTIVE_TAB") {
        const result = await executeInActiveTab(_captureSupabaseAccessTokenInPage);
        if (!result?.ok) throw new Error(result?.error || "Failed to capture token");
        await setState({ token: result.token, tokenCapturedAt: Date.now() });
        sendResponse({ ok: true });
        return;
      }

      if (msg?.type === "SAVE_JOB_FROM_ACTIVE_TAB") {
        const out = await saveCapturedJob();
        sendResponse(out);
        return;
      }

      if (msg?.type === "OPEN_APP_APPLY") {
        const state = await getState();
        const appBase = normalizeAppBase(state.appBase);
        await chrome.tabs.create({ url: `${appBase}/apply` });
        sendResponse({ ok: true });
        return;
      }

      sendResponse({ ok: false, error: "Unknown message" });
    } catch (e) {
      sendResponse({ ok: false, error: e?.message || String(e) });
    }
  })();

  // Keep message channel open for async response
  return true;
});

