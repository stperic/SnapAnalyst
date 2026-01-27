// =============================================================================
// SnapAnalyst Custom JavaScript - Main Entry Point
// 
// This file is loaded by Chainlit via custom_js config.
// It dynamically loads all required scripts:
// - chainlit_ui.js: Chainlit UI fixes (Enter-to-send, etc.)
// - tabulator_bundle.js: Data table library + initialization
// =============================================================================

console.log("SnapAnalyst main.js loading...");

function loadScript(src) {
    return new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = src;
        script.onload = resolve;
        script.onerror = reject;
        document.head.appendChild(script);
    });
}

// Load scripts in order
(async function() {
    try {
        // Load Chainlit UI fixes first (includes Enter-to-send)
        await loadScript('/public/js/chainlit_ui.js');
        console.log("Chainlit UI fixes loaded");
        
        // Load Tabulator bundle (table library + init)
        await loadScript('/public/js/tabulator_bundle.js');
        console.log("Tabulator bundle loaded");
        
        console.log("All SnapAnalyst scripts loaded successfully");
    } catch (e) {
        console.error("Error loading SnapAnalyst scripts:", e);
    }
})();
