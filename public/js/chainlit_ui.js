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
    `;

    button.innerHTML = `
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            ${iconPath}
        </svg>
    `;

    // Hover effect
    button.addEventListener('mouseenter', () => {
        button.style.backgroundColor = 'rgba(128, 128, 128, 0.1)';
    });
    button.addEventListener('mouseleave', () => {
        button.style.backgroundColor = 'transparent';
    });

    return button;
}

function addToggleButtons() {
    // Find the input area - try multiple approaches
    const inputContainer =
        document.querySelector('form div[class*="MuiStack"]') ||
        document.querySelector('form > div:first-child') ||
        document.querySelector('[class*="inputArea"]') ||
        document.querySelector('form');

    if (!inputContainer) {
        console.log('No input container found');
        return;
    }

    // Find the div that contains action buttons (clip, gear, etc.)
    // Look for a div with buttons that have SVG icons
    const allDivs = inputContainer.querySelectorAll('div');
    let controlsContainer = null;

    for (const div of allDivs) {
        const buttons = div.querySelectorAll('button');
        if (buttons.length >= 2) {
            // Check if it has SVG icons (attachment, settings, etc.)
            const hasSvg = Array.from(buttons).some(btn => btn.querySelector('svg'));
            if (hasSvg) {
                controlsContainer = div;
                break;
            }
        }
    }

    if (!controlsContainer) {
        console.log('No controls container found');
        return;
    }

    // Check if buttons already exist
    if (document.getElementById('kb-toggle-btn')) {
        console.log('Toggle buttons already exist');
        return;
    }

    console.log('Adding toggle buttons to container');

    // Create Knowledge Base button (book icon)
    const kbButton = createToggleButton(
        '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path>',
        'Toggle Knowledge Base',
        knowledgeBaseEnabled
    );
    kbButton.id = 'kb-toggle-btn';

    // Create Last Data button (database icon)
    const dataButton = createToggleButton(
        '<ellipse cx="12" cy="5" rx="9" ry="3"></ellipse><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"></path><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"></path>',
        'Toggle Last Data Query',
        lastDataEnabled,
        hasLastData
    );
    dataButton.id = 'data-toggle-btn';

    // Add click handlers
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

    // Insert buttons at the beginning of the controls container
    const firstButton = controlsContainer.querySelector('button');
    if (firstButton) {
        controlsContainer.insertBefore(dataButton, firstButton);
        controlsContainer.insertBefore(kbButton, firstButton);
        console.log('Toggle buttons added successfully');
    } else {
        controlsContainer.appendChild(kbButton);
        controlsContainer.appendChild(dataButton);
        console.log('Toggle buttons appended successfully');
    }
}

// Function to show/hide the Last Data button
function updateLastDataButton(hasData) {
    hasLastData = hasData;
    const dataButton = document.getElementById('data-toggle-btn');
    if (dataButton) {
        dataButton.style.display = hasData ? 'flex' : 'none';
    }
}

// Setup toggle buttons with retry
function setupToggleButtons(attempts = 0) {
    console.log(`Attempting to add toggle buttons (attempt ${attempts + 1})`);
    addToggleButtons();
    if (attempts < 60 && !document.getElementById('kb-toggle-btn')) {
        setTimeout(() => setupToggleButtons(attempts + 1), 1000);
    }
}

// Initialize on load with multiple triggers
document.addEventListener('DOMContentLoaded', () => {
    console.log('DOMContentLoaded - starting toggle button setup');
    setTimeout(setupToggleButtons, 2000);
});
window.addEventListener('load', () => {
    console.log('Window loaded - starting toggle button setup');
    setTimeout(setupToggleButtons, 2000);
});
if (document.readyState !== 'loading') {
    console.log('Document already loaded - starting toggle button setup');
    setTimeout(setupToggleButtons, 2000);
}

// Watch for DOM changes to add buttons if they disappear
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
// Enter Key Sends Message
// =============================================================================
function setupEnterToSend() {
    document.querySelectorAll('textarea:not([data-enter-fixed="true"])').forEach(textarea => {
        if (textarea.offsetParent === null) return;

        textarea.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                e.stopPropagation();

                const form = textarea.closest('form');
                const submitBtn = form?.querySelector('button[type="submit"]') ||
                    form?.querySelector('button:last-of-type');

                if (submitBtn) {
                    submitBtn.click();
                } else {
                    const parent = textarea.parentElement?.parentElement?.parentElement;
                    const buttons = parent?.querySelectorAll('button');
                    if (buttons?.length > 0) {
                        buttons[buttons.length - 1].click();
                    } else if (form) {
                        form.requestSubmit();
                    }
                }
            }
        }, true);

        textarea.dataset.enterFixed = "true";
    });
}

function trySetupEnterToSend(attempts = 0) {
    setupEnterToSend();
    if (attempts < 60) {
        setTimeout(() => trySetupEnterToSend(attempts + 1), 500);
    }
}

document.addEventListener("DOMContentLoaded", () => setTimeout(trySetupEnterToSend, 500));

const inputObserver = new MutationObserver(setupEnterToSend);
if (document.body) {
    inputObserver.observe(document.body, { childList: true, subtree: true });
    setTimeout(trySetupEnterToSend, 500);
}

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
// Loading Indicator
// Note: Chainlit has its own loading indicator (white dot with shading)
// =============================================================================
