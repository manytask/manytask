/**
 * Shared Tabulator theme synchronisation.
 *
 * Keeps the Tabulator stylesheet in sync with Bootstrap's `data-bs-theme`
 * attribute on <html>, swapping between the light and `tabulator_midnight`
 * dark stylesheets and redrawing the active table on change.
 *
 * Expects two <link> elements to be present:
 *   <link id="light-theme" ...>
 *   <link id="dark-theme" ... disabled>
 *
 * Usage:
 *   const applyTabulatorTheme = initTabulatorTheme(() => window.tabulatorTable);
 *   // ... later, after lazily building a table:
 *   applyTabulatorTheme();
 *
 * @param {function(): (object|undefined)} getTable
 *        Callback returning the current Tabulator instance (or a falsy value
 *        if the table is not built yet). Called on every theme change so lazily
 *        initialised tables are picked up automatically.
 * @returns {function(): void}
 *        A function that re-applies the current theme on demand. Call it right
 *        after building a table that was created lazily (i.e. after the initial
 *        theme was already set), since the MutationObserver only reacts to
 *        subsequent attribute *changes*, not to a table appearing later.
 */
function initTabulatorTheme(getTable) {
    function applyTheme() {
        const isDark = document.documentElement.getAttribute('data-bs-theme') === 'dark';

        const lightTheme = document.getElementById('light-theme');
        const darkTheme = document.getElementById('dark-theme');

        if (lightTheme && darkTheme) {
            lightTheme.disabled = isDark;
            darkTheme.disabled = !isDark;
        }

        const table = typeof getTable === 'function' ? getTable() : undefined;
        if (table) {
            table.redraw(true);
        }
    }

    applyTheme();

    const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
            if (mutation.attributeName === 'data-bs-theme') {
                applyTheme();
            }
        });
    });
    observer.observe(document.documentElement, {
        attributes: true,
        attributeFilter: ['data-bs-theme'],
    });

    return applyTheme;
}
