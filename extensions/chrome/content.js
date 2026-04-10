// Content script: enables selection capture from any page
// Listens for messages from the popup to get the current selection

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "get-selection") {
    const selection = window.getSelection().toString().trim();
    sendResponse({ selection, url: window.location.href, title: document.title });
  }
});
