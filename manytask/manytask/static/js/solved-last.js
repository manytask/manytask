function initSolvedLast(button, applyOrder) {
    button.value = 'false';
    button.addEventListener('click', () => {
        button.value = button.value === 'true' ? 'false' : 'true';
        button.textContent = button.value === 'true' ? 'Show solved' : 'Hide solved';
        button.setAttribute('aria-pressed', button.value);
        applyOrder();
    });
}

function moveSolvedGroupsLast(groups) {
    return groups.filter(group => !group.solved).concat(groups.filter(group => group.solved));
}
