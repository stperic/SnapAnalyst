// Custom JavaScript for SnapAnalyst

/**
 * Sort table by column
 * Uses event delegation to handle dynamically added tables
 */
function initTableSorting() {
    // Use event delegation on document body
    document.body.addEventListener('click', function(e) {
        // Check if clicked element is a sortable header
        const header = e.target.closest('.sortable-header');
        if (!header) return;
        
        const table = header.closest('table');
        if (!table) return;
        
        const tbody = table.querySelector('tbody');
        const headerRow = header.parentElement;
        const headers = Array.from(headerRow.querySelectorAll('th'));
        const columnIndex = headers.indexOf(header);
        
        // Get current sort direction
        const currentDirection = header.dataset.sortDirection || 'none';
        let newDirection = currentDirection === 'asc' ? 'desc' : 'asc';
        
        // Clear all sort indicators in this table
        headers.forEach(h => {
            h.dataset.sortDirection = 'none';
            const sortIcon = h.querySelector('span');
            if (sortIcon) {
                sortIcon.textContent = '⇅';
                sortIcon.style.color = '#94a3b8';
            }
        });
        
        // Set new sort direction
        header.dataset.sortDirection = newDirection;
        const sortIcon = header.querySelector('span');
        if (sortIcon) {
            sortIcon.textContent = newDirection === 'asc' ? '↑' : '↓';
            sortIcon.style.color = '#0284c7';
        }
        
        // Get all rows
        const rows = Array.from(tbody.querySelectorAll('tr'));
        
        // Sort rows
        rows.sort((a, b) => {
            const aCell = a.children[columnIndex];
            const bCell = b.children[columnIndex];
            
            if (!aCell || !bCell) return 0;
            
            // Get text content, handling NULL values
            let aValue = aCell.textContent.trim();
            let bValue = bCell.textContent.trim();
            
            // Handle NULL values - always put them at the end
            if (aValue === 'NULL') return 1;
            if (bValue === 'NULL') return -1;
            
            // Try to parse as numbers
            const aNum = parseFloat(aValue);
            const bNum = parseFloat(bValue);
            
            let comparison = 0;
            
            if (!isNaN(aNum) && !isNaN(bNum)) {
                // Numeric comparison
                comparison = aNum - bNum;
            } else {
                // String comparison
                comparison = aValue.localeCompare(bValue, undefined, {numeric: true, sensitivity: 'base'});
            }
            
            return newDirection === 'asc' ? comparison : -comparison;
        });
        
        // Re-append rows in sorted order and update alternating colors
        rows.forEach((row, index) => {
            tbody.appendChild(row);
            // Update alternating row colors
            row.style.background = index % 2 === 0 ? '#ffffff' : '#f8fafc';
        });
    });
    
    console.log('SnapAnalyst: Table sorting initialized with event delegation');
}

// Initialize immediately and on DOMContentLoaded
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initTableSorting);
} else {
    initTableSorting();
}

// Also reinitialize when new content is added (for Chainlit's dynamic content)
const observer = new MutationObserver(function(mutations) {
    mutations.forEach(function(mutation) {
        if (mutation.addedNodes.length) {
            // Check if any added nodes contain sortable tables
            mutation.addedNodes.forEach(node => {
                if (node.nodeType === 1 && (node.classList?.contains('sortable-table') || node.querySelector?.('.sortable-table'))) {
                    console.log('SnapAnalyst: New sortable table detected');
                }
            });
        }
    });
});

// Start observing
observer.observe(document.body, {
    childList: true,
    subtree: true
});

console.log('SnapAnalyst custom JS loaded - table sorting with event delegation enabled');
