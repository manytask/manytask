document.getElementById('namespaceSettingsForm').addEventListener('submit', async event => {
    event.preventDefault();

    const form = event.currentTarget;
    const nameInput = document.getElementById('namespaceName');
    const descriptionInput = document.getElementById('namespaceDescription');
    const errorDiv = document.getElementById('namespaceSettingsError');
    const successDiv = document.getElementById('namespaceSettingsSuccess');
    const saveButton = form.querySelector('[type="submit"]');

    errorDiv.classList.add('d-none');
    successDiv.classList.add('d-none');

    const name = nameInput.value.trim();
    if (!name) {
        errorDiv.textContent = 'Namespace name is required';
        errorDiv.classList.remove('d-none');
        nameInput.focus();
        return;
    }

    saveButton.disabled = true;
    try {
        const response = await fetch(form.dataset.updateUrl, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name, description: descriptionInput.value || null})
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || 'Failed to update namespace');
        }

        nameInput.value = data.name;
        descriptionInput.value = data.description || '';
        document.getElementById('namespaceDisplayName').textContent = data.name;
        const description = document.getElementById('namespaceDisplayDescription');
        description.textContent = data.description || '';
        description.hidden = !data.description;
        document.title = `${data.name} - Namespace Panel`;
        successDiv.textContent = 'Namespace settings saved successfully';
        successDiv.classList.remove('d-none');
    } catch (error) {
        errorDiv.textContent = error.message;
        errorDiv.classList.remove('d-none');
    } finally {
        saveButton.disabled = false;
    }
});
