async function createNamespace() {
    const form = document.getElementById('createNamespaceForm');
    const errorDiv = document.getElementById('createNamespaceError');
    const successDiv = document.getElementById('createNamespaceSuccess');

    errorDiv.classList.add('d-none');
    successDiv.classList.add('d-none');

    const formData = {
        name: form.querySelector('[name="name"]').value,
        slug: form.querySelector('[name="slug"]').value,
        description: form.querySelector('[name="description"]').value || null
    };

    try {
        const response = await fetch('/api/namespaces', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(formData)
        });

        const data = await response.json();

        if (response.ok) {
            successDiv.textContent = `Namespace "${formData.name}" created successfully!`;
            successDiv.classList.remove('d-none');
            form.reset();

            setTimeout(() => {
                location.reload();
            }, 1500);
        } else {
            errorDiv.textContent = data.error || 'Failed to create namespace';
            errorDiv.classList.remove('d-none');
        }
    } catch (error) {
        errorDiv.textContent = 'Network error: ' + error.message;
        errorDiv.classList.remove('d-none');
    }
}
