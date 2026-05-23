/**
 * 86 Proof — Chat Panel
 * ─────────────────────────────────────────
 * Handles the conversational interface with Claude.
 *
 * Flow:
 *   1. User types a question, hits enter or clicks Send
 *   2. Message is rendered in the chat panel immediately
 *   3. POST request fires to /api/chat with message + history
 *   4. Loading indicator shows while waiting
 *   5. Claude's response is rendered when it returns
 *   6. History is maintained in browser memory for session
 */

(function() {
    'use strict';

    // ── ELEMENTS ──────────────────────────────────────
    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-input');
    const chatMessages = document.getElementById('chat-messages');

    // ── STATE ─────────────────────────────────────────
    let conversationHistory = [];
    let isLoading = false;

    // ── MESSAGE RENDERING ─────────────────────────────

    function appendUserMessage(text) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'flex justify-end';
        messageDiv.innerHTML = `
            <div class="bg-brand-green text-white rounded-lg px-3 py-2 max-w-[85%] text-sm">
                ${escapeHtml(text)}
            </div>
        `;
        chatMessages.appendChild(messageDiv);
        scrollToBottom();
    }

    function appendAssistantMessage(text) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'flex justify-start';
        messageDiv.innerHTML = `
            <div class="bg-gray-100 rounded-lg px-3 py-2 max-w-[90%] text-sm text-brand-dark whitespace-pre-wrap">
                ${formatMarkdown(escapeHtml(text))}
            </div>
        `;
        chatMessages.appendChild(messageDiv);
        scrollToBottom();
    }

    function appendLoadingMessage() {
        const loadingDiv = document.createElement('div');
        loadingDiv.id = 'loading-indicator';
        loadingDiv.className = 'flex justify-start';
        loadingDiv.innerHTML = `
            <div class="bg-gray-100 rounded-lg px-4 py-3 text-sm text-brand-light">
                <span class="inline-flex space-x-1">
                    <span class="w-1.5 h-1.5 bg-brand-light rounded-full animate-bounce" style="animation-delay: 0ms"></span>
                    <span class="w-1.5 h-1.5 bg-brand-light rounded-full animate-bounce" style="animation-delay: 150ms"></span>
                    <span class="w-1.5 h-1.5 bg-brand-light rounded-full animate-bounce" style="animation-delay: 300ms"></span>
                </span>
            </div>
        `;
        chatMessages.appendChild(loadingDiv);
        scrollToBottom();
    }

    function removeLoadingMessage() {
        const loading = document.getElementById('loading-indicator');
        if (loading) loading.remove();
    }

    function appendErrorMessage(text) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'flex justify-start';
        errorDiv.innerHTML = `
            <div class="bg-red-50 border border-red-200 rounded-lg px-3 py-2 text-sm text-red-700">
                ${escapeHtml(text)}
            </div>
        `;
        chatMessages.appendChild(errorDiv);
        scrollToBottom();
    }

    // ── HELPERS ───────────────────────────────────────

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function formatMarkdown(text) {
        // Light markdown formatting:
        //   **bold** → <strong>bold</strong>
        //   - bullet → · bullet (cleaner inline)
        //   newlines preserved via whitespace-pre-wrap in CSS
        return text
            .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
            .replace(/^- /gm, '· ')
            .replace(/^\* /gm, '· ');
    }

    function scrollToBottom() {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // ── API CALL ──────────────────────────────────────

    async function sendMessage(message) {
    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: message,
                history: conversationHistory,
            }),
        });

        // Try to parse JSON — may fail if server returned empty/HTML (e.g. waking up)
        let data;
        try {
            data = await response.json();
        } catch (parseErr) {
            // Server returned non-JSON — likely waking up from sleep
            throw new Error(
                'The server is waking up. This can take 30-60 seconds on the free hosting tier. ' +
                'Please try your question again in a moment.'
            );
        }

        if (!response.ok) {
            throw new Error(data.error || 'Something went wrong.');
        }

        return data.response;
    } catch (err) {
        throw err;
    }
}

    // ── FORM SUBMISSION ───────────────────────────────

    chatForm.addEventListener('submit', async function(e) {
        e.preventDefault();

        if (isLoading) return;

        const message = chatInput.value.trim();
        if (!message) return;

        // Clear input immediately
        chatInput.value = '';

        // Render the user's message
        appendUserMessage(message);

        // Show loading indicator
        isLoading = true;
        appendLoadingMessage();

        try {
            // Send to backend
            const response = await sendMessage(message);

            // Remove loading, render Claude's response
            removeLoadingMessage();
            appendAssistantMessage(response);

            // Update conversation history
            conversationHistory.push(
                { role: 'user', content: message },
                { role: 'assistant', content: response }
            );
        } catch (err) {
            removeLoadingMessage();
            appendErrorMessage(
                'Sorry, I had trouble responding. ' + (err.message || '')
            );
        } finally {
            isLoading = false;
            chatInput.focus();
        }
    });

    // Focus the input on load
    chatInput.focus();

})();