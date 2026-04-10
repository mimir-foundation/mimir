// Context menu: right-click selected text -> "Save to Mimir"
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "save-to-mimir",
    title: "Save to Mimir",
    contexts: ["selection"],
  });

  chrome.contextMenus.create({
    id: "save-page-to-mimir",
    title: "Save page to Mimir",
    contexts: ["page"],
  });
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  const config = await getConfig();
  if (!config.serverUrl) {
    console.error("Mimir server URL not configured");
    return;
  }

  if (info.menuItemId === "save-to-mimir" && info.selectionText) {
    await captureHighlight(config, info.selectionText, tab.url);
  } else if (info.menuItemId === "save-page-to-mimir") {
    await captureUrl(config, tab.url);
  }
});

// Listen for messages from popup/content scripts
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "capture-note") {
    getConfig().then((config) => {
      captureNote(config, message.content, message.title).then(sendResponse);
    });
    return true;
  }
  if (message.type === "capture-url") {
    getConfig().then((config) => {
      captureUrl(config, message.url).then(sendResponse);
    });
    return true;
  }
  if (message.type === "capture-highlight") {
    getConfig().then((config) => {
      captureHighlight(config, message.content, message.sourceUri).then(
        sendResponse,
      );
    });
    return true;
  }
});

async function getConfig() {
  const result = await chrome.storage.sync.get(["serverUrl", "apiKey"]);
  return {
    serverUrl: result.serverUrl || "",
    apiKey: result.apiKey || "",
  };
}

function getHeaders(config) {
  const headers = { "Content-Type": "application/json" };
  if (config.apiKey) {
    headers["Authorization"] = `Bearer ${config.apiKey}`;
  }
  return headers;
}

async function captureNote(config, content, title) {
  try {
    const resp = await fetch(`${config.serverUrl}/api/capture/note`, {
      method: "POST",
      headers: getHeaders(config),
      body: JSON.stringify({ content, title }),
    });
    return await resp.json();
  } catch (e) {
    return { error: e.message };
  }
}

async function captureUrl(config, url) {
  try {
    const resp = await fetch(`${config.serverUrl}/api/capture/url`, {
      method: "POST",
      headers: getHeaders(config),
      body: JSON.stringify({ url }),
    });
    return await resp.json();
  } catch (e) {
    return { error: e.message };
  }
}

async function captureHighlight(config, content, sourceUri) {
  try {
    const resp = await fetch(`${config.serverUrl}/api/capture/highlight`, {
      method: "POST",
      headers: getHeaders(config),
      body: JSON.stringify({ content, source_uri: sourceUri }),
    });
    return await resp.json();
  } catch (e) {
    return { error: e.message };
  }
}
