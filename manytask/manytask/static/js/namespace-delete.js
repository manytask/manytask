(() => {
    const form = document.getElementById('deleteNamespaceForm');
    const nameInput = document.getElementById('deleteNamespaceName');
    const errorDiv = document.getElementById('deleteNamespaceError');
    const deleteButton = form.querySelector('[type="submit"]');
    const currentName = () => document.getElementById('namespaceDisplayName').textContent;
    let deleting = false;

    document.getElementById('deleteNamespaceModal').addEventListener('show.bs.modal', () => {
        if (deleting) return;
        document.getElementById('deleteNamespaceExpectedName').textContent = currentName();
        nameInput.value = '';
        errorDiv.classList.add('d-none');
        deleteButton.disabled = true;
    });

    nameInput.addEventListener('input', () => {
        deleteButton.disabled = deleting || nameInput.value !== currentName();
    });

    form.addEventListener('submit', async event => {
        event.preventDefault();
        if (deleting) return;
        errorDiv.classList.add('d-none');
        if (nameInput.value !== currentName()) {
            errorDiv.textContent = 'Namespace name does not match';
            errorDiv.classList.remove('d-none');
            nameInput.focus();
            return;
        }

        deleting = true;
        deleteButton.disabled = true;
        nameInput.disabled = true;
        const fallbackError = 'Failed to delete namespace. Please try again.';
        try {
            const response = await fetch(form.dataset.deleteUrl, {
                method: 'DELETE',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({name: nameInput.value})
            });
            if (!response.ok) {
                const data = await response.json().catch(() => ({}));
                errorDiv.textContent = data.error || fallbackError;
                errorDiv.classList.remove('d-none');
                return;
            }
            window.location.assign(form.dataset.redirectUrl);
        } catch (error) {
            errorDiv.textContent = fallbackError;
            errorDiv.classList.remove('d-none');
        } finally {
            deleting = false;
            nameInput.disabled = false;
            deleteButton.disabled = nameInput.value !== currentName();
        }
    });
})();
