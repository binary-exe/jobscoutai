/* global chrome */

function qs(id) {
  return document.getElementById(id);
}

function setText(id, text) {
  const el = qs(id);
  if (el) el.textContent = text;
}

function bgMessage(payload) {
  return new Promise((resolve) => chrome.runtime.sendMessage(payload, resolve));
}

async function refreshState() {
  const res = await bgMessage({ type: "GET_STATE" });
  if (!res?.ok) {
    setText("statusLine", `Error: ${res?.error || "unknown"}`);
    return null;
  }
  const state = res.state;

  qs("apiBase").value = state.apiBase || "";
  qs("appBase").value = state.appBase || "";

  const connected = state.token === "present";
  setText("statusLine", connected ? "Status: connected" : "Status: not connected");
  qs("disconnectBtn").disabled = !connected;
  qs("saveBtn").disabled = !connected;
  return state;
}

async function main() {
  await refreshState();

  qs("openAppBtn").addEventListener("click", async () => {
    const s = await refreshState();
    const appBase = s?.appBase || "https://jobscoutai.vercel.app";
    chrome.tabs.create({ url: `${appBase.replace(/\/+$/, "")}/` });
  });

  qs("connectBtn").addEventListener("click", async () => {
    setText("resultLine", "");
    setText("statusLine", "Connecting… (reading session from active tab)");
    const res = await bgMessage({ type: "CONNECT_FROM_ACTIVE_TAB" });
    if (!res?.ok) {
      setText("statusLine", "Status: not connected");
      setText("resultLine", `Connect failed: ${res?.error || "unknown"}`);
      await refreshState();
      return;
    }
    setText("resultLine", "Connected.");
    await refreshState();
  });

  qs("disconnectBtn").addEventListener("click", async () => {
    await bgMessage({ type: "DISCONNECT" });
    setText("resultLine", "Disconnected.");
    await refreshState();
  });

  qs("saveBtn").addEventListener("click", async () => {
    qs("saveBtn").disabled = true;
    setText("resultLine", "Saving…");
    qs("openApplyAfterSave")?.classList.add("hidden");
    const res = await bgMessage({ type: "SAVE_JOB_FROM_ACTIVE_TAB" });
    if (!res?.ok) {
      setText("resultLine", `Save failed: ${res?.error || "unknown"}`);
      await refreshState();
      qs("saveBtn").disabled = false;
      return;
    }
    const jt = res.data?.job_target_id;
    setText("resultLine", jt ? "Saved. Open Apply Workspace to get a Trust Report and pack." : "Saved.");
    if (jt) {
      const link = qs("openApplyAfterSave");
      if (link) {
        const s = await refreshState();
        const appBase = (s?.appBase || "https://jobscoutai.vercel.app").replace(/\/+$/, "");
        link.href = `${appBase}/apply?job_target_id=${jt}`;
        link.classList.remove("hidden");
      }
    }
    await refreshState();
    qs("saveBtn").disabled = false;
  });

  qs("openApplyBtn").addEventListener("click", async () => {
    await bgMessage({ type: "OPEN_APP_APPLY" });
  });

  qs("saveSettingsBtn").addEventListener("click", async () => {
    const apiBase = qs("apiBase").value;
    const appBase = qs("appBase").value;
    const res = await bgMessage({ type: "SET_SETTINGS", apiBase, appBase });
    setText("resultLine", res?.ok ? "Settings saved." : `Failed: ${res?.error || "unknown"}`);
    await refreshState();
  });
}

document.addEventListener("DOMContentLoaded", main);

