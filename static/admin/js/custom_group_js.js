/**
 * Enhanced Group Permission Selector
 * This script groups permissions by Application/Model to make it easier to manage rights.
 */

window.addEventListener('load', function() {
    // Wait for the dual listbox to be initialized by Django
    setTimeout(function() {
        const selects = document.querySelectorAll('.selector-available select, .selector-chosen select');
        
        selects.forEach(select => {
            const options = Array.from(select.options);
            // Sort by text to group by App | Model
            options.sort((a, b) => a.text.localeCompare(b.text));
            
            // Re-append sorted options
            select.innerHTML = '';
            let currentApp = '';
            
            options.forEach(opt => {
                const parts = opt.text.split('|');
                if (parts.length > 1) {
                    const appName = parts[0].trim();
                    if (appName !== currentApp) {
                        // Create a separator option (disabled)
                        const separator = document.createElement('option');
                        separator.disabled = true;
                        separator.text = `─── ${appName.toUpperCase()} ───`;
                        separator.style.fontWeight = 'bold';
                        separator.style.color = '#007bff';
                        separator.style.backgroundColor = '#f8f9fa';
                        select.add(separator);
                        currentApp = appName;
                    }
                }
                select.add(opt);
            });
        });
    }, 500); // Small delay to ensure Django's JS has run
});
