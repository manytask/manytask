(function () {
    const panel = document.getElementById('studentTokenPanel');
    if (!panel) {
        return;
    }

    const input = document.getElementById('studentTokenValue');
    const status = document.getElementById('studentTokenStatus');
    const revealBtn = document.getElementById('studentTokenReveal');
    const copyBtn = document.getElementById('studentTokenCopy');
    const publishBtn = document.getElementById('studentTokenPublish');
    const rotateBtn = document.getElementById('studentTokenRotate');
    const variableName = document.getElementById('studentTokenVariable');

    const actionButtons = [publishBtn, rotateBtn];
    let loaded = false;

    function setStatus(message, isError) {
        status.textContent = message;
        status.className = 'small mt-2 ' + (isError ? 'text-danger' : 'text-muted');
    }

    function setBusy(busy) {
        actionButtons.forEach((button) => {
            button.disabled = busy;
        });
    }

    async function request(url, method) {
        setBusy(true);
        try {
            const response = await fetch(url, {
                method: method,
                credentials: 'same-origin',
                headers: window.csrfHeaders(),
            });
            if (!response.ok) {
                throw new Error('HTTP ' + response.status);
            }
            const data = await response.json();
            input.value = data.token;
            if (data.ci_variable) {
                variableName.textContent = data.ci_variable;
            }
            return data;
        } finally {
            setBusy(false);
        }
    }

    async function load() {
        if (loaded) {
            return;
        }
        try {
            await request(panel.dataset.tokenUrl, 'GET');
            loaded = true;
            setStatus('', false);
        } catch (error) {
            setStatus('Could not load your token: ' + error.message, true);
        }
    }

    panel.addEventListener('show.bs.collapse', load);

    revealBtn.addEventListener('click', function () {
        const hidden = input.type === 'password';
        input.type = hidden ? 'text' : 'password';
        revealBtn.innerHTML = hidden ? '<i class="fas fa-eye-slash"></i>' : '<i class="fas fa-eye"></i>';
    });

    copyBtn.addEventListener('click', async function () {
        if (!input.value) {
            return;
        }
        try {
            await navigator.clipboard.writeText(input.value);
            setStatus('Token copied to the clipboard.', false);
        } catch (error) {
            input.type = 'text';
            input.select();
            setStatus('Copying is blocked by the browser, select the token and copy it by hand.', true);
        }
    });

    publishBtn.addEventListener('click', async function () {
        try {
            const data = await request(panel.dataset.publishUrl, 'POST');
            loaded = true;
            setStatus(
                data.published_to_repo
                    ? 'Saved as the ' + data.ci_variable + ' CI/CD variable of your repository.'
                    : 'Your repository does not accept CI/CD variables, add ' + data.ci_variable + ' manually.',
                !data.published_to_repo
            );
        } catch (error) {
            setStatus('Could not write the variable: ' + error.message, true);
        }
    });

    rotateBtn.addEventListener('click', async function () {
        if (!window.confirm('The old token stops working immediately. Regenerate it?')) {
            return;
        }
        try {
            const data = await request(panel.dataset.rotateUrl, 'POST');
            loaded = true;
            setStatus(
                data.published_to_repo
                    ? 'New token issued and written to your repository.'
                    : 'New token issued, set ' + data.ci_variable + ' in your repository by hand.',
                !data.published_to_repo
            );
        } catch (error) {
            setStatus('Could not regenerate the token: ' + error.message, true);
        }
    });
})();
