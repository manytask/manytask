(() => {
    const form = document.getElementById('deleteCourseForm');
    const nameInput = document.getElementById('delete-course-name');
    const errorDiv = document.getElementById('deleteCourseError');
    const deleteButton = document.getElementById('delete-course-submit');
    let deleting = false;

    document.getElementById('deleteCourseModal').addEventListener('show.bs.modal', () => {
        if (deleting) return;
        nameInput.value = '';
        errorDiv.classList.add('d-none');
        deleteButton.disabled = true;
    });

    nameInput.addEventListener('input', () => {
        deleteButton.disabled = deleting || nameInput.value !== nameInput.dataset.courseName;
    });

    form.addEventListener('submit', async event => {
        event.preventDefault();
        if (deleting) return;
        errorDiv.classList.add('d-none');
        if (nameInput.value !== nameInput.dataset.courseName) {
            errorDiv.textContent = 'Course name does not match';
            errorDiv.classList.remove('d-none');
            nameInput.focus();
            return;
        }

        const body = new FormData(form);
        deleting = true;
        deleteButton.disabled = true;
        nameInput.disabled = true;
        const fallbackError = 'Failed to delete course. Please try again.';
        try {
            const response = await fetch(form.action, {
                method: 'POST',
                headers: {'Accept': 'application/json'},
                body,
            });
            const data = await response.json().catch(() => ({}));
            if (!response.ok || !data.redirect_url) {
                errorDiv.textContent = data.error || fallbackError;
                errorDiv.classList.remove('d-none');
                return;
            }
            window.location.assign(data.redirect_url);
        } catch (error) {
            errorDiv.textContent = fallbackError;
            errorDiv.classList.remove('d-none');
        } finally {
            deleting = false;
            nameInput.disabled = false;
            deleteButton.disabled = nameInput.value !== nameInput.dataset.courseName;
        }
    });
})();
