function initStudentRemoval() {
    const modalElement = document.getElementById('removeStudentModal');
    const modal = new bootstrap.Modal(modalElement);
    const form = document.getElementById('removeStudentForm');
    const username = document.getElementById('removeStudentUsername');
    const confirmation = document.getElementById('removeStudentConfirmation');
    const submit = document.getElementById('removeStudentSubmit');
    let submitting = false;

    function matchesUsername() {
        return username.value !== '' && confirmation.value === username.value;
    }

    confirmation.addEventListener('input', function() {
        submit.disabled = submitting || !matchesUsername();
    });
    form.addEventListener('submit', function(event) {
        if (submitting || !matchesUsername()) {
            event.preventDefault();
            return;
        }
        submitting = true;
        submit.disabled = true;
    });
    modalElement.addEventListener('shown.bs.modal', function() {
        confirmation.focus();
    });
    modalElement.addEventListener('hidden.bs.modal', function() {
        username.value = '';
        confirmation.value = '';
        submit.disabled = true;
    });

    return function(studentUsername) {
        if (submitting) return;
        username.value = studentUsername;
        document.getElementById('removeStudentName').textContent = studentUsername;
        confirmation.value = '';
        submit.disabled = true;
        modal.show();
    };
}
