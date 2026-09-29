// Assignments preference, isolated by user and course in this browser.
function initTaskGroupOrder(button) {
    const key = 'manytask:task-group-order:' + JSON.stringify([
        button.dataset.username, button.dataset.courseName,
    ]);
    button.value = 'desc';
    try {
        const stored = localStorage.getItem(key);
        if (stored === 'asc' || stored === 'desc') button.value = stored;
    } catch {
        // Sorting remains available when the browser blocks storage.
    }
    function updateLabel() {
        button.textContent = button.value === 'asc' ? 'Show newest first' : 'Show oldest first';
    }
    updateLabel();
    button.addEventListener('click', () => {
        button.value = button.value === 'asc' ? 'desc' : 'asc';
        updateLabel();
        try {
            localStorage.setItem(key, button.value);
        } catch {
            // Keep the selection for this page even when it cannot be saved.
        }
    });
}

function sortTaskGroups(groups, order) {
    const direction = order === 'asc' ? 1 : -1;
    // Stable sorting preserves the configured order for groups opened at the same time.
    return [...groups].sort((a, b) => direction * (Date.parse(a.start) - Date.parse(b.start)));
}
