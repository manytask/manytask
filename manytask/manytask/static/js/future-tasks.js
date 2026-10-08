// Assignments preference, isolated by user and course in this browser.
function initFutureTasks(button, groups) {
    const key = 'manytask:future-tasks:' + JSON.stringify([
        button.dataset.username, button.dataset.courseName,
    ]);
    let showFutureTasks = false;
    try {
        showFutureTasks = localStorage.getItem(key) === 'true';
    } catch {
        // The toggle remains available when the browser blocks storage.
    }

    function updateVisibility() {
        groups.forEach(group => { group.hidden = !showFutureTasks; });
        button.textContent = showFutureTasks ? 'Hide future tasks' : 'Show future tasks';
        button.setAttribute('aria-pressed', String(showFutureTasks));
    }

    updateVisibility();
    button.addEventListener('click', () => {
        showFutureTasks = !showFutureTasks;
        updateVisibility();
        try {
            localStorage.setItem(key, String(showFutureTasks));
        } catch {
            // Keep the selection for this page even when it cannot be saved.
        }
    });
}
