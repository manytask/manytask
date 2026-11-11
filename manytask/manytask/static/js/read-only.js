// Presentation only: the server and PostgreSQL enforce the restriction.
(() => {
    const message = document.getElementById('read-only-banner').textContent;
    const actionSelector = '[data-read-only-action], .admin-btn, .role-select, '
        + '[onclick^="save"], [onclick^="addUser"], [onclick^="createNamespace"], '
        + '[onclick^="assignRoleInNamespace"], button[form], .course-access-revoke, '
        + '#grantCourseAdminSubmit, #clearOverrideBtn';

    document.querySelectorAll(actionSelector).forEach(element => {
        element.title = message;
        if (element.matches('form')) {
            element.querySelectorAll('input, select, textarea, button').forEach(control => {
                control.disabled = true;
                control.title = message;
            });
        } else {
            element.setAttribute('aria-disabled', 'true');
            if (element.matches('a')) {
                element.classList.add('disabled');
            } else {
                element.disabled = true;
            }
        }
    });

    // Capture before existing handlers, including controls that scripts re-enable.
    for (const eventName of ['click', 'change', 'submit']) {
        document.addEventListener(eventName, event => {
            if (event.target.closest(actionSelector)) {
                event.preventDefault();
                event.stopImmediatePropagation();
            }
        }, true);
    }
})();
