/**
 * FOOD MAN - AI ASSISTANT CHATBOT CONTROLLER
 * Phase 6 — Advanced Features & Polish
 * Embeds a domain-aware conversational assistant to query:
 * - Inventory & FEFO expiration
 * - 7-tier traceability
 * - QC queue & AI defect results
 * - Production batches & BOM availability
 * - Cold-chain dispatches & system alerts
 */

const FoodManChatbot = (() => {
  let isOpen = false;
  let isSending = false;

  function init() {
    setupUI();
  }

  function setupUI() {
    const triggerBtn = document.getElementById('btnChatbotTrigger');
    const panel = document.getElementById('chatbotPanel');
    const closeBtn = document.getElementById('btnChatbotClose');
    const sendBtn = document.getElementById('btnChatbotSend');
    const inputField = document.getElementById('chatbotInput');

    if (triggerBtn) {
      triggerBtn.addEventListener('click', toggleChatbot);
    }
    if (closeBtn) {
      closeBtn.addEventListener('click', closeChatbot);
    }
    if (sendBtn) {
      sendBtn.addEventListener('click', sendMessage);
    }
    if (inputField) {
      inputField.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          sendMessage();
        }
      });
    }
  }

  function toggleChatbot() {
    if (isOpen) {
      closeChatbot();
    } else {
      openChatbot();
    }
  }

  function openChatbot() {
    const panel = document.getElementById('chatbotPanel');
    const triggerBtn = document.getElementById('btnChatbotTrigger');
    if (panel) {
      panel.classList.add('is-open');
      isOpen = true;
      if (triggerBtn) triggerBtn.classList.add('is-active');
      const inputField = document.getElementById('chatbotInput');
      if (inputField) setTimeout(() => inputField.focus(), 150);
    }
  }

  function closeChatbot() {
    const panel = document.getElementById('chatbotPanel');
    const triggerBtn = document.getElementById('btnChatbotTrigger');
    if (panel) {
      panel.classList.remove('is-open');
      isOpen = false;
      if (triggerBtn) triggerBtn.classList.remove('is-active');
    }
  }

  function sendSuggestedQuery(text) {
    const inputField = document.getElementById('chatbotInput');
    if (inputField) {
      inputField.value = text;
      sendMessage();
    }
  }

  async function sendMessage() {
    const inputField = document.getElementById('chatbotInput');
    if (!inputField || isSending) return;

    const message = inputField.value.trim();
    if (!message) return;

    // Append User Message
    appendMessage('user', message);
    inputField.value = '';

    // Show Typing Indicator
    showTyping();
    isSending = true;

    try {
      const res = await fetch('/api/chatbot/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: message })
      });
      const data = await res.json();
      hideTyping();

      if (data.success) {
        appendMessage('bot', data.reply, data.suggestions);
      } else {
        appendMessage('bot', data.reply || "Sorry, an error occurred while fetching data.");
      }
    } catch (err) {
      hideTyping();
      appendMessage('bot', "⚠ Unable to connect to AI server. Please check your network connection.");
    } finally {
      isSending = false;
    }
  }

  function appendMessage(sender, text, suggestions = []) {
    const messagesContainer = document.getElementById('chatbotMessages');
    if (!messagesContainer) return;

    const msgDiv = document.createElement('div');
    msgDiv.className = sender === 'user' ? 'chatbot-msg-user' : 'chatbot-msg-bot';

    const formattedText = parseMarkdown(text);

    if (sender === 'user') {
      msgDiv.innerHTML = `
        <div class="msg-bubble user-bubble">${escapeHtml(text)}</div>
      `;
    } else {
      let suggestionsHtml = '';
      if (suggestions && suggestions.length > 0) {
        suggestionsHtml = `
          <div class="chatbot-suggestions-row">
            ${suggestions.map(s => `
              <button class="chip-suggestion" onclick="FoodManChatbot.sendSuggestedQuery('${escapeHtml(s)}')">${escapeHtml(s)}</button>
            `).join('')}
          </div>
        `;
      }

      msgDiv.innerHTML = `
        <div class="bot-avatar-icon">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="12 2 2 7 12 12 22 7 12 2"></polygon><polyline points="2 17 12 22 22 17"></polyline><polyline points="2 12 12 17 22 12"></polyline></svg>
        </div>
        <div class="msg-content-wrapper">
          <div class="msg-bubble bot-bubble">${formattedText}</div>
          ${suggestionsHtml}
        </div>
      `;
    }

    messagesContainer.appendChild(msgDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  }

  function showTyping() {
    const messagesContainer = document.getElementById('chatbotMessages');
    if (!messagesContainer) return;

    const typingDiv = document.createElement('div');
    typingDiv.id = 'chatbotTypingIndicator';
    typingDiv.className = 'chatbot-msg-bot typing-state';
    typingDiv.innerHTML = `
      <div class="bot-avatar-icon">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="12 2 2 7 12 12 22 7 12 2"></polygon><polyline points="2 17 12 22 22 17"></polyline><polyline points="2 12 12 17 22 12"></polyline></svg>
      </div>
      <div class="msg-bubble bot-bubble typing-dots">
        <span></span><span></span><span></span>
      </div>
    `;
    messagesContainer.appendChild(typingDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  }

  function hideTyping() {
    const typing = document.getElementById('chatbotTypingIndicator');
    if (typing) typing.remove();
  }

  function parseMarkdown(text) {
    if (!text) return '';
    let parsed = text;
    // Headings
    parsed = parsed.replace(/^### (.*$)/gim, '<h4 style="font-size:13px;font-weight:800;color:var(--accent-navy);margin:6px 0 8px 0;">$1</h4>');
    // Bold
    parsed = parsed.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    // Italic
    parsed = parsed.replace(/\*(.*?)\*/g, '<em>$1</em>');
    // Inline code
    parsed = parsed.replace(/`([^`]+)`/g, '<code style="background:#F1F5F9;color:var(--accent-navy);padding:2px 5px;border-radius:4px;font-size:11.5px;font-weight:700;">$1</code>');
    // Links
    parsed = parsed.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" class="chatbot-inline-link" style="color:var(--accent-navy);font-weight:700;text-decoration:underline;">$1</a>');
    // Bullet lists
    parsed = parsed.replace(/^- (.*$)/gim, '<div style="display:flex;gap:6px;margin-bottom:3px;"><span style="color:var(--accent-navy);">•</span><span>$1</span></div>');
    // Line breaks
    parsed = parsed.replace(/\n\n/g, '<div style="height:6px;"></div>');
    return parsed;
  }

  function escapeHtml(unsafe) {
    return unsafe
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  return {
    init,
    toggleChatbot,
    openChatbot,
    closeChatbot,
    sendSuggestedQuery,
    sendMessage
  };
})();

document.addEventListener('DOMContentLoaded', FoodManChatbot.init);
