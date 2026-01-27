
// Tabulator Initialization for SnapAnalyst
// Handles loading data from hidden script tags via MutationObserver.
// NOTE: All data formatting is done server-side in Python using data_mapping.json.
// The JavaScript just displays pre-formatted values.

console.log("Tabulator Init Script Loaded - MutationObserver Version");

// =============================================================================
// SMART SORTING - Handles all data formats from data_mapping.json
// Formats: integer, rawint, year, currency, weight, text, boolean, datetime
// =============================================================================

// Parse a formatted value to a number (strips $, commas, %, etc.)
function parseFormattedNumber(val) {
    if (val === null || val === undefined || val === "") return null;
    const str = String(val).trim();
    if (str === "") return null;
    
    // Remove currency symbols, commas, percent signs, spaces
    const cleaned = str.replace(/[$€£¥,\s%]/g, '');
    const num = parseFloat(cleaned);
    return isNaN(num) ? null : num;
}

// Parse date strings (handles ISO, US, and YYYYMMDD formats)
function parseDate(val) {
    if (val === null || val === undefined || val === "") return null;
    const str = String(val).trim();
    
    // YYYYMMDD format (e.g., 20230115)
    if (/^\d{8}$/.test(str)) {
        const y = parseInt(str.substring(0, 4));
        const m = parseInt(str.substring(4, 6)) - 1;
        const d = parseInt(str.substring(6, 8));
        return new Date(y, m, d).getTime();
    }
    
    // YYYYMM format (e.g., 202301)
    if (/^\d{6}$/.test(str)) {
        const y = parseInt(str.substring(0, 4));
        const m = parseInt(str.substring(4, 6)) - 1;
        return new Date(y, m, 1).getTime();
    }
    
    // Try standard date parsing
    const d = new Date(str);
    return isNaN(d.getTime()) ? null : d.getTime();
}

// Custom sorter for formatted numbers (currency, integers, decimals)
function numericSorter(a, b, aRow, bRow, column, dir, sorterParams) {
    const numA = parseFormattedNumber(a);
    const numB = parseFormattedNumber(b);
    
    if (numA === null && numB === null) return 0;
    if (numA === null) return 1;  // Nulls at end
    if (numB === null) return -1;
    
    return numA - numB;
}

// Custom sorter for dates
function dateSorter(a, b, aRow, bRow, column, dir, sorterParams) {
    const dateA = parseDate(a);
    const dateB = parseDate(b);
    
    if (dateA === null && dateB === null) return 0;
    if (dateA === null) return 1;
    if (dateB === null) return -1;
    
    return dateA - dateB;
}

// Detect column type from data
function detectColumnType(data, field) {
    if (!data || data.length === 0) return "string";
    
    const fieldLower = field.toLowerCase();
    
    // Date columns by name pattern
    if (fieldLower.includes("date") || fieldLower.includes("_at") || 
        fieldLower === "created" || fieldLower === "updated" ||
        fieldLower.includes("timestamp")) {
        return "date";
    }
    
    // Sample values to detect type
    let numericCount = 0;
    let dateCount = 0;
    let checked = 0;
    
    for (const row of data) {
        const val = row[field];
        if (val !== null && val !== undefined && String(val).trim() !== "") {
            checked++;
            
            // Check if numeric (includes currency, percentages)
            if (parseFormattedNumber(val) !== null) {
                numericCount++;
            }
            
            // Check if date-like (YYYYMMDD, YYYYMM, or parseable date)
            const str = String(val).trim();
            if (/^\d{6,8}$/.test(str) || parseDate(val) !== null) {
                dateCount++;
            }
            
            if (checked >= 10) break;
        }
    }
    
    if (checked === 0) return "string";
    
    const numericRatio = numericCount / checked;
    const dateRatio = dateCount / checked;
    
    // Prefer numeric if most values are numeric
    if (numericRatio >= 0.7) return "number";
    if (dateRatio >= 0.7) return "date";
    
    return "string";
}

// Get the appropriate sorter for a column
function getSorterForColumn(data, field) {
    const type = detectColumnType(data, field);
    
    switch (type) {
        case "number":
            return numericSorter;
        case "date":
            return dateSorter;
        default:
            return "string";
    }
}

// Main initialization logic
function initializeTable(container) {
    // Avoid double initialization
    if (container.dataset.initialized === "true") return;
    
    // Find the data script inside the container
    const dataScript = container.querySelector('script[type="application/json"]');
    if (!dataScript) {
        console.warn("Tabulator container found but no data script present yet.", container);
        return;
    }

    const tableId = container.querySelector('div[id^="table-"]')?.id;
    if (!tableId) {
        console.error("No table ID found in container");
        return;
    }

    try {
        const tableData = JSON.parse(dataScript.textContent);
        
        // Auto-generate columns from first row if data exists
        // Values are pre-formatted by Python using data_mapping.json
        // Use smart sorter based on detected column type
        let columns = [];
        if (tableData.length > 0) {
            columns = Object.keys(tableData[0]).map(key => {
                const sorter = getSorterForColumn(tableData, key);
                const type = detectColumnType(tableData, key);
                console.log(`Column "${key}": type=${type}, sorter=${typeof sorter === 'function' ? 'custom' : sorter}`);
                return {
                    title: key.toUpperCase().replace(/_/g, ' '),
                    field: key,
                    sorter: sorter,
                    headerFilter: false  // Disable filters for cleaner look
                };
            });
        }

        // Initialize Tabulator
        new Tabulator(`#${tableId}`, {
            data: tableData,
            layout: "fitColumns",
            responsiveLayout: "collapse",
            pagination: "local",
            paginationSize: 10,
            paginationSizeSelector: [10, 25, 50, 100],
            movableColumns: true,
            resizableRows: false,
            placeholder: "No Data Available",
            columns: columns,
            maxHeight: "500px",
            renderVertical: "virtual", // Virtual DOM for performance
            
            // Interaction
            rowClick: function(e, row) {
                row.toggleSelect();
            },
        });
        
        // Mark as initialized
        container.dataset.initialized = "true";
        console.log(`Table ${tableId} initialized via MutationObserver.`);

    } catch (e) {
        console.error(`Failed to initialize Tabulator for ${tableId}:`, e);
    }
}

// Observe the document for new .tabulator-container elements
const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
        // Check added nodes
        mutation.addedNodes.forEach((node) => {
            if (node.nodeType === 1) { // Element node
                // Check if node itself is the container
                if (node.classList && node.classList.contains("tabulator-container")) {
                    initializeTable(node);
                }
                // Check if node contains the container
                const containers = node.querySelectorAll(".tabulator-container");
                containers.forEach(initializeTable);
            }
        });
    });
});

// Start observing the body for changes
// We use a slight delay to ensure the DOM is ready if loaded via script tag
document.addEventListener("DOMContentLoaded", () => {
    observer.observe(document.body, {
        childList: true,
        subtree: true
    });
    
    // Also process any existing containers that might have missed the observer start
    document.querySelectorAll(".tabulator-container").forEach(initializeTable);
});

// Fallback for immediate execution if already loaded
if (document.body) {
    observer.observe(document.body, {
        childList: true,
        subtree: true
    });
    document.querySelectorAll(".tabulator-container").forEach(initializeTable);
}

