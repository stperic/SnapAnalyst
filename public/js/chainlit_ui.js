// =============================================================================
// Chainlit UI Fixes
// Custom JavaScript for Chainlit interface improvements
// =============================================================================

console.log("Chainlit UI fixes loaded");

// =============================================================================
// Toggle Buttons for Knowledge Base and Last Data
// =============================================================================
let knowledgeBaseEnabled = false;
let lastDataEnabled = false;
let hasLastData = false;

function createToggleButton(iconPath, label, isActive, isVisible = true) {
    const button = document.createElement('button');
    button.type = 'button';
    button.setAttribute('aria-label', label);
    button.style.cssText = `
        display: ${isVisible ? 'flex' : 'none'};
        align-items: center;
        justify-content: center;
        width: 40px;
        height: 40px;
        border: none;
        background: transparent;
        cursor: pointer;
        border-radius: 4px;
        padding: 8px;
        transition: all 0.2s;
        opacity: ${isActive ? '1' : '0.5'};
        color: inherit;
    `;

    button.innerHTML = `
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            ${iconPath}
        </svg>
    `;

    button.addEventListener('mouseenter', () => button.style.backgroundColor = 'rgba(128, 128, 128, 0.1)');
    button.addEventListener('mouseleave', () => button.style.backgroundColor = 'transparent');
    return button;
}

function addToggleButtons() {
    if (document.getElementById('kb-toggle-btn')) return;

    // Find the input area and controls container
    const inputContainer =
        document.querySelector('form div[class*="MuiStack"]') ||
        document.querySelector('form > div:first-child') ||
        document.querySelector('[class*="inputArea"]') ||
        document.querySelector('form');

    if (!inputContainer) return;

    const allDivs = inputContainer.querySelectorAll('div');
    let controlsContainer = null;
    for (const div of allDivs) {
        const buttons = div.querySelectorAll('button');
        if (buttons.length >= 2) {
            const hasSvg = Array.from(buttons).some(btn => btn.querySelector('svg'));
            if (hasSvg) {
                controlsContainer = div;
                break;
            }
        }
    }
    if (!controlsContainer) return;

    const kbButton = createToggleButton(
        '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path>',
        'Toggle Knowledge Base',
        knowledgeBaseEnabled
    );
    kbButton.id = 'kb-toggle-btn';

    const dataButton = createToggleButton(
        '<ellipse cx="12" cy="5" rx="9" ry="3"></ellipse><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"></path><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"></path>',
        'Toggle Last Data Query',
        lastDataEnabled,
        hasLastData
    );
    dataButton.id = 'data-toggle-btn';

    kbButton.addEventListener('click', () => {
        knowledgeBaseEnabled = !knowledgeBaseEnabled;
        kbButton.style.opacity = knowledgeBaseEnabled ? '1' : '0.5';
        console.log('Knowledge Base:', knowledgeBaseEnabled ? 'ON' : 'OFF');
    });

    dataButton.addEventListener('click', () => {
        lastDataEnabled = !lastDataEnabled;
        dataButton.style.opacity = lastDataEnabled ? '1' : '0.5';
        console.log('Last Data:', lastDataEnabled ? 'ON' : 'OFF');
    });

    const firstChild = controlsContainer.firstChild;
    controlsContainer.insertBefore(dataButton, firstChild);
    controlsContainer.insertBefore(kbButton, firstChild);
    console.log('Toggle buttons added successfully');
}

function updateLastDataButton(hasData) {
    hasLastData = hasData;
    const dataButton = document.getElementById('data-toggle-btn');
    if (dataButton) dataButton.style.display = hasData ? 'flex' : 'none';
}

// Setup toggle buttons with retry
function setupToggleButtons(attempts = 0) {
    addToggleButtons();
    if (attempts < 60 && !document.getElementById('kb-toggle-btn')) {
        setTimeout(() => setupToggleButtons(attempts + 1), 1000);
    }
}

document.addEventListener('DOMContentLoaded', () => setTimeout(setupToggleButtons, 2000));
window.addEventListener('load', () => setTimeout(setupToggleButtons, 2000));
if (document.readyState !== 'loading') setTimeout(setupToggleButtons, 2000);

const toggleObserver = new MutationObserver(() => {
    if (!document.getElementById('kb-toggle-btn')) {
        addToggleButtons();
    }
});
if (document.body) {
    toggleObserver.observe(document.body, { childList: true, subtree: true });
}

// Expose functions globally for backend to call
window.updateLastDataButton = updateLastDataButton;
window.getToggleStates = () => ({
    knowledgeBase: knowledgeBaseEnabled,
    lastData: lastDataEnabled
});

// =============================================================================
// Login Page Customizations
// =============================================================================
function isLoginPage() {
    return !!document.querySelector('input[type="password"]');
}

function addLoginInstructions() {
    if (!isLoginPage()) return;

    // Check if instructions already added
    if (document.getElementById('login-instructions')) return;

    // Find the Sign In button
    const signInButton = document.querySelector('button[type="submit"]');
    if (!signInButton) return;

    // Create instruction text element
    const instructions = document.createElement('div');
    instructions.id = 'login-instructions';
    instructions.style.cssText = `
        margin-top: 1rem;
        padding: 0.75rem;
        text-align: center;
        font-size: 0.875rem;
        line-height: 1.5;
        border-radius: 0.375rem;
        opacity: 0.7;
    `;
    instructions.innerHTML = `
        <strong>First time here?</strong><br>
        Your first sign-in will automatically create an account.
    `;

    // Insert after the Sign In button's parent container
    const buttonContainer = signInButton.parentElement;
    if (buttonContainer) {
        buttonContainer.insertAdjacentElement('afterend', instructions);
    }
}

function hideLogoOnLoginPage() {
    if (!isLoginPage()) return;

    const hideElement = (el) => {
        if (!el) return;
        Object.assign(el.style, {
            display: 'none',
            visibility: 'hidden',
            height: '0',
            width: '0',
            overflow: 'hidden',
            position: 'absolute'
        });
    };

    const isInHeader = (rect) => rect.top >= 0 && rect.top < 200 && rect.height > 0;

    // Hide home links in header
    document.querySelectorAll('a[href="/"]').forEach(link => {
        if (isInHeader(link.getBoundingClientRect())) {
            hideElement(link);
        }
    });

    // Hide nav/header elements
    ['nav', 'header', '[role="navigation"]', '[role="banner"]'].forEach(selector => {
        document.querySelectorAll(selector).forEach(el => {
            const rect = el.getBoundingClientRect();
            if (isInHeader(rect) && rect.height < 200) {
                hideElement(el);
            }
        });
    });

    // Hide logo images
    document.querySelectorAll('img').forEach(img => {
        const src = img.src?.toLowerCase() || '';
        const alt = img.alt?.toLowerCase() || '';
        if ((src.includes('logo') || alt.includes('logo')) && isInHeader(img.getBoundingClientRect())) {
            hideElement(img.closest('a') || img.parentElement);
        }
    });

    // Hide app name text in header
    ['SnapAnalyst', 'Snap Analyst', 'Assistant'].forEach(name => {
        document.querySelectorAll('*').forEach(el => {
            const directText = Array.from(el.childNodes)
                .filter(node => node.nodeType === Node.TEXT_NODE)
                .map(node => node.textContent.trim())
                .join(' ');
            if (directText === name && isInHeader(el.getBoundingClientRect())) {
                hideElement(el.closest('a') || el);
            }
        });
    });

    // Hide SVG logos in header
    document.querySelectorAll('svg').forEach(svg => {
        const rect = svg.getBoundingClientRect();
        if (isInHeader(rect) && rect.height < 100 && rect.width < 200) {
            const container = svg.closest('a') || svg.parentElement;
            if (container?.parentElement?.getBoundingClientRect().top < 200) {
                hideElement(container);
            }
        }
    });
}

// Setup with retry and observer
function setupLoginPageCustomizations() {
    hideLogoOnLoginPage();
    addLoginInstructions();
    for (let i = 1; i <= 50; i++) {
        setTimeout(() => {
            hideLogoOnLoginPage();
            addLoginInstructions();
        }, i * 100);
    }
}

document.addEventListener('DOMContentLoaded', setupLoginPageCustomizations);
window.addEventListener('load', setupLoginPageCustomizations);
if (document.readyState !== 'loading') setupLoginPageCustomizations();

const loginObserver = new MutationObserver(() => {
    if (isLoginPage()) {
        hideLogoOnLoginPage();
        addLoginInstructions();
    }
});
if (document.body) {
    loginObserver.observe(document.body, { childList: true, subtree: true });
} else {
    document.addEventListener('DOMContentLoaded', () => {
        loginObserver.observe(document.body, { childList: true, subtree: true });
    });
}

// =============================================================================
// Enter Key Sends Message (Enter = send, Shift+Enter = new line)
// =============================================================================

document.addEventListener('keydown', (e) => {
    const textarea = document.querySelector('textarea');
    if (e.key === 'Enter' && !e.shiftKey && document.activeElement === textarea) {
        e.preventDefault();
        const sendButton = document.querySelector('button[type="submit"]');
        if (sendButton) {
            sendButton.click();
        }
    }
});

// =============================================================================
// Command Mode: Placeholder Text
// When Insights or Knowledge mode is selected, update the textarea placeholder.
//
// Strategy:
//   - Track active mode via click events on command buttons (toggle on/off).
//   - Use Object.defineProperty to intercept React's placeholder writes.
//   - Poll every 250ms as a fallback to catch edge cases (React re-renders,
//     page navigation, etc.).
// =============================================================================

const MODE_PLACEHOLDERS = {
    'insights': 'Ask a follow-up question to analyze your previous query results...',
    'knowledge': 'Ask a question or make a request to search your knowledge base...',
};
const DEFAULT_PLACEHOLDER = 'Ask a question to query your SNAP QC data...';

let _activeCommandMode = null;
let _patchedTextarea = null;
const _nativePlaceholderDesc = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'placeholder');

function getDesiredPlaceholder() {
    return _activeCommandMode ? MODE_PLACEHOLDERS[_activeCommandMode] : DEFAULT_PLACEHOLDER;
}

/** Patch a textarea so React's placeholder writes are intercepted. */
function patchTextarea(textarea) {
    if (textarea === _patchedTextarea) return;
    _patchedTextarea = textarea;
    Object.defineProperty(textarea, 'placeholder', {
        get() { return _nativePlaceholderDesc.get.call(this); },
        set(val) { _nativePlaceholderDesc.set.call(this, getDesiredPlaceholder()); },
        configurable: true,
    });
}

/** Force the correct placeholder onto the textarea. */
function applyPlaceholder() {
    const textarea = document.querySelector('textarea');
    if (!textarea) return;
    patchTextarea(textarea);
    const desired = getDesiredPlaceholder();
    if (_nativePlaceholderDesc.get.call(textarea) !== desired) {
        _nativePlaceholderDesc.set.call(textarea, desired);
    }
}

// Detect command button clicks via event delegation
document.addEventListener('click', (e) => {
    const btn = e.target.closest('button.command-button');
    if (!btn) return;

    const id = (btn.id || '').toLowerCase();
    let mode = null;
    if (id === 'command-insights') mode = 'insights';
    else if (id === 'command-knowledge') mode = 'knowledge';
    if (!mode) return;

    // Toggle: clicking active mode deactivates it, otherwise activate
    _activeCommandMode = (_activeCommandMode === mode) ? null : mode;

    // Apply after a tick so React finishes its update first
    setTimeout(applyPlaceholder, 50);
});

// Poll as fallback — lightweight, catches React re-renders and navigation
setInterval(applyPlaceholder, 250);

// =============================================================================
// Arrow Up/Down History Navigation
// =============================================================================

const inputHistory = [];
let historyIndex = -1;
let currentInput = '';

function setupHistoryNavigation() {
    document.querySelectorAll('textarea:not([data-history-fixed="true"])').forEach(textarea => {
        if (textarea.offsetParent === null) return;

        // Capture message on submit (before it's cleared)
        const form = textarea.closest('form');
        if (form && !form.dataset.historyCapture) {
            form.addEventListener('submit', () => {
                const value = textarea.value.trim();
                if (value && (inputHistory.length === 0 || inputHistory[inputHistory.length - 1] !== value)) {
                    inputHistory.push(value);
                    // Keep last 50 entries
                    if (inputHistory.length > 50) inputHistory.shift();
                }
                historyIndex = -1;
                currentInput = '';
            });
            form.dataset.historyCapture = 'true';
        }

        textarea.addEventListener('keydown', function (e) {
            // Only handle arrow keys when cursor is at start/end of input
            if (e.key === 'ArrowUp') {
                // Navigate to older history
                if (inputHistory.length === 0) return;

                // Save current input if starting navigation
                if (historyIndex === -1) {
                    currentInput = textarea.value;
                }

                if (historyIndex < inputHistory.length - 1) {
                    historyIndex++;
                    textarea.value = inputHistory[inputHistory.length - 1 - historyIndex];
                    // Move cursor to end
                    setTimeout(() => {
                        textarea.selectionStart = textarea.selectionEnd = textarea.value.length;
                    }, 0);
                    e.preventDefault();
                }
            } else if (e.key === 'ArrowDown') {
                // Navigate to newer history
                if (historyIndex > 0) {
                    historyIndex--;
                    textarea.value = inputHistory[inputHistory.length - 1 - historyIndex];
                    setTimeout(() => {
                        textarea.selectionStart = textarea.selectionEnd = textarea.value.length;
                    }, 0);
                    e.preventDefault();
                } else if (historyIndex === 0) {
                    // Return to current input
                    historyIndex = -1;
                    textarea.value = currentInput;
                    setTimeout(() => {
                        textarea.selectionStart = textarea.selectionEnd = textarea.value.length;
                    }, 0);
                    e.preventDefault();
                }
            }
        });

        textarea.dataset.historyFixed = 'true';
    });
}

// Initialize history navigation
document.addEventListener('DOMContentLoaded', () => setTimeout(setupHistoryNavigation, 1000));
window.addEventListener('load', () => setTimeout(setupHistoryNavigation, 1000));

const historyObserver = new MutationObserver(setupHistoryNavigation);
if (document.body) {
    historyObserver.observe(document.body, { childList: true, subtree: true });
}

// =============================================================================
// Sidebar Panel Interaction
// Panels now use Chainlit CustomElement (JSX) with built-in callAction().
// No event delegation needed — all interactivity is handled in JSX components:
//   public/elements/MemPanel.jsx
//   public/elements/MemsqlPanel.jsx
// =============================================================================

// =============================================================================
// Settings Header Button (next to Readme in the top-right header bar)
//
// Header layout: <div id="header"> ... <div class="flex items-center gap-1">
//   [messages] [Readme button#readme-button] [theme toggle] [user menu]
// </div>
//
// We insert a "Settings" button right before #readme-button. The gap-1 class
// on the parent handles spacing automatically.
// =============================================================================

let _chainlitSessionId = null;

// Capture sessionId from fetch (used for action calls, file uploads, etc.)
const _origFetch = window.fetch;
window.fetch = function (...args) {
    const [url, opts] = args;
    if (opts && opts.body && typeof opts.body === 'string') {
        try {
            const body = JSON.parse(opts.body);
            if (body.sessionId) _chainlitSessionId = body.sessionId;
        } catch (_) {}
    }
    return _origFetch.apply(this, args);
};

// Capture sessionId from XMLHttpRequest (Socket.IO polling sends auth here)
const _origXhrSend = XMLHttpRequest.prototype.send;
XMLHttpRequest.prototype.send = function (body) {
    if (body && typeof body === 'string') {
        try {
            // Socket.IO polling sends JSON with sessionId in the auth payload
            // Format varies: could be plain JSON or a Socket.IO packet like "40{...}"
            const jsonStr = body.replace(/^\d+/, ''); // strip Socket.IO packet prefix
            if (jsonStr.includes('sessionId')) {
                const parsed = JSON.parse(jsonStr);
                if (parsed.sessionId) _chainlitSessionId = parsed.sessionId;
                // Socket.IO auth is sometimes nested
                if (parsed.auth?.sessionId) _chainlitSessionId = parsed.auth.sessionId;
            }
        } catch (_) {}
    }
    return _origXhrSend.apply(this, arguments);
};

// Capture sessionId from WebSocket messages (Socket.IO upgrade handshake)
const _origWsSend = WebSocket.prototype.send;
WebSocket.prototype.send = function (data) {
    if (typeof data === 'string' && data.includes('sessionId')) {
        try {
            const jsonStr = data.replace(/^\d+/, '');
            const parsed = JSON.parse(jsonStr);
            if (parsed.sessionId) _chainlitSessionId = parsed.sessionId;
            if (parsed.auth?.sessionId) _chainlitSessionId = parsed.auth.sessionId;
        } catch (_) {}
    }
    return _origWsSend.apply(this, arguments);
};

async function openReadmePanel() {
    if (!_chainlitSessionId) {
        console.warn('Readme: no session ID captured yet. Send a message first.');
        return;
    }
    try {
        await _origFetch('/project/action', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({
                sessionId: _chainlitSessionId,
                action: { name: 'open_readme_panel', payload: {} }
            })
        });
    } catch (e) {
        console.error('Readme action error:', e);
    }
}

async function openSettingsPanel() {
    if (!_chainlitSessionId) {
        console.warn('Settings: no session ID captured yet. Send a message first.');
        return;
    }
    try {
        await _origFetch('/project/action', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({
                sessionId: _chainlitSessionId,
                action: { name: 'open_settings_panel', payload: { panel: 'settings' } }
            })
        });
    } catch (e) {
        console.error('Settings action error:', e);
    }
}

function addSettingsHeaderButton() {
    if (document.getElementById('settings-header-btn')) return;

    // Find #readme-button — Chainlit renders it with this exact ID
    const readmeBtn = document.getElementById('readme-button');
    if (!readmeBtn) return;

    // The Readme button sits inside a Dialog trigger wrapper.
    // Its closest parent in the header bar is the <div class="flex items-center gap-1">.
    // We need to insert at THAT level, not inside the Dialog trigger.
    // Walk up from readmeBtn to find the gap-1 container.
    let headerBar = readmeBtn.parentElement;
    while (headerBar && !headerBar.className?.includes('gap-')) {
        headerBar = headerBar.parentElement;
    }
    if (!headerBar) return;

    // Find the Dialog wrapper that contains the readme button
    // (it's the direct child of headerBar that contains readmeBtn)
    let readmeWrapper = readmeBtn;
    while (readmeWrapper.parentElement !== headerBar) {
        readmeWrapper = readmeWrapper.parentElement;
        if (!readmeWrapper) return;
    }

    // Create Settings button — clone readmeBtn for identical styling
    const settingsBtn = readmeBtn.cloneNode(false);
    settingsBtn.id = 'settings-header-btn';
    settingsBtn.textContent = 'Settings';
    settingsBtn.removeAttribute('data-state');

    settingsBtn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        openSettingsPanel();
    });

    // Insert after the Readme wrapper in the header bar
    readmeWrapper.insertAdjacentElement('afterend', settingsBtn);

    // Override Readme button: overlay to intercept clicks before the Dialog opens
    if (!readmeBtn.querySelector('.readme-overlay')) {
        readmeBtn.style.position = 'relative';
        const overlay = document.createElement('div');
        overlay.className = 'readme-overlay';
        overlay.style.cssText =
            'position:absolute;top:0;left:0;width:100%;height:100%;z-index:50;cursor:pointer;';
        overlay.addEventListener('click', function (e) {
            e.stopPropagation();
            e.stopImmediatePropagation();
            e.preventDefault();
            openReadmePanel();
        }, true);
        readmeBtn.appendChild(overlay);
    }

    console.log('Header buttons configured');
}

function setupSettingsHeaderButton(attempts = 0) {
    addSettingsHeaderButton();
    if (attempts < 60 && !document.getElementById('settings-header-btn')) {
        setTimeout(() => setupSettingsHeaderButton(attempts + 1), 1000);
    }
}

document.addEventListener('DOMContentLoaded', () => setTimeout(setupSettingsHeaderButton, 2000));
window.addEventListener('load', () => setTimeout(setupSettingsHeaderButton, 2000));
if (document.readyState !== 'loading') setTimeout(setupSettingsHeaderButton, 2000);

const settingsHeaderObserver = new MutationObserver(() => {
    if (!document.getElementById('settings-header-btn')) {
        addSettingsHeaderButton();
    }
});
if (document.body) {
    settingsHeaderObserver.observe(document.body, { childList: true, subtree: true });
}

// =============================================================================
// Sidebar Back Button Override
//
// Chainlit's sidebar back button (#side-view-title > button) sets the Recoil
// atom to undefined, closing the sidebar. React 18 uses event delegation at the
// root, so stopPropagation on a DOM listener won't prevent React's handler.
//
// Solution: place an invisible overlay div on top of the native button. The
// overlay receives the click at the DOM level AND prevents the event from ever
// reaching React's delegation root. On child panels it navigates to Settings;
// on the Settings hub it removes itself and re-dispatches the click so the
// native close works.
//
// #side-view-title is a stable id hardcoded in Chainlit's compiled source.
// =============================================================================

const SETTINGS_CHILD_TITLES = new Set([
    'Data Filters', 'LLM Params', 'Database', 'Knowledge', 'Knowledge SQL'
]);

function getSidebarTitle() {
    const titleDiv = document.getElementById('side-view-title');
    if (!titleDiv) return null;
    let text = '';
    for (const node of titleDiv.childNodes) {
        if (node.nodeType === Node.TEXT_NODE) text += node.textContent;
    }
    return text.trim();
}

function setupSidebarOverlay() {
    const titleDiv = document.getElementById('side-view-title');
    if (!titleDiv) return;

    const nativeBtn = titleDiv.querySelector('button');
    if (!nativeBtn) return;

    // Already set up?
    if (nativeBtn.parentElement.querySelector('.sidebar-back-overlay')) return;

    // Make the button container position:relative so overlay aligns to it
    nativeBtn.style.position = 'relative';

    const overlay = document.createElement('div');
    overlay.className = 'sidebar-back-overlay';
    overlay.style.cssText =
        'position:absolute;top:0;left:0;width:100%;height:100%;z-index:50;cursor:pointer;';

    overlay.addEventListener('click', function (e) {
        e.stopPropagation();
        e.stopImmediatePropagation();
        e.preventDefault();

        const title = getSidebarTitle();
        if (title && SETTINGS_CHILD_TITLES.has(title) && _chainlitSessionId) {
            // Child panel → go back to Settings
            openSettingsPanel();
        } else {
            // Settings hub → close sidebar via native button
            overlay.remove();
            nativeBtn.click();
        }
    }, true);

    nativeBtn.appendChild(overlay);
}

const sidebarBackObserver = new MutationObserver(() => {
    if (document.getElementById('side-view-title')) {
        requestAnimationFrame(setupSidebarOverlay);
    }
});
if (document.body) {
    sidebarBackObserver.observe(document.body, { childList: true, subtree: true });
}

// =============================================================================
// Loading Indicator
// Note: Chainlit has its own loading indicator (white dot with shading)
// =============================================================================
