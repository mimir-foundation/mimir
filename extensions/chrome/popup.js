const contentEl = document.getElementById("content");
const captureBtn = document.getElementById("captureBtn");
const savePageBtn = document.getElementById("savePageBtn");
const statusEl = document.getElementById("status");
const settingsToggle = document.getElementById("settingsToggle");
const settingsPanel = document.getElementById("settingsPanel");
const serverUrlEl = document.getElementById("serverUrl");
const apiKeyEl = document.getElementById("apiKey");
const saveSettingsBtn = document.getElementById("saveSettings");

// Load settings
chrome.storage.sync.get(["serverUrl", "apiKey"], (result) => {
  serverUrlEl.value = result.serverUrl || "";
  apiKeyEl.value = result.apiKey || "";
});

// Try to get selection from active tab
chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
  if (tabs[0]) {
    chrome.tabs.sendMessage(tabs[0].id, { type: "get-selection" }, (response) => {
      if (chrome.runtime.lastError) return;
      if (response && response.selection) {
        contentEl.value = response.selection;
      }
    });
  }
});

// Capture note
captureBtn.addEventListener("click", async () => {
  const content = contentEl.value.trim();
  if (!content) {
    showStatus("Nothing to capture", "error");
    return;
  }

  captureBtn.disabled = true;
  showStatus("Capturing...", "");

  chrome.runtime.sendMessage(
    { type: "capture-note", content },
    (response) => {
      captureBtn.disabled = false;
      if (response && response.note_id) {
        showStatus("Captured!", "success");
        contentEl.value = "";
        setTimeout(() => window.close(), 1000);
      } else {
        showStatus(response?.error || "Failed to capture", "error");
      }
    },
  );
});

// Save page URL
savePageBtn.addEventListener("click", async () => {
  savePageBtn.disabled = true;
  showStatus("Saving page...", "");

  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (!tabs[0]) {
      showStatus("No active tab", "error");
      savePageBtn.disabled = false;
      return;
    }

    chrome.runtime.sendMessage(
      { type: "capture-url", url: tabs[0].url },
      (response) => {
        savePageBtn.disabled = false;
        if (response && response.note_id) {
          showStatus("Page saved!", "success");
          setTimeout(() => window.close(), 1000);
        } else {
          showStatus(response?.error || "Failed to save", "error");
        }
      },
    );
  });
});

// Settings toggle
settingsToggle.addEventListener("click", () => {
  settingsPanel.classList.toggle("show");
});

// Save settings
saveSettingsBtn.addEventListener("click", () => {
  chrome.storage.sync.set(
    {
      serverUrl: serverUrlEl.value.trim().replace(/\/$/, ""),
      apiKey: apiKeyEl.value.trim(),
    },
    () => {
      showStatus("Settings saved!", "success");
    },
  );
});

function showStatus(msg, type) {
  statusEl.textContent = msg;
  statusEl.className = `status ${type}`;
}
