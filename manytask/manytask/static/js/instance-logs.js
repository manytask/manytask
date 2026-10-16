(() => {
    const root = document.getElementById('instance-logs');
    const source = document.getElementById('log-source');
    const lines = document.getElementById('log-lines');
    const download = document.getElementById('log-download');
    const pause = document.getElementById('log-pause');
    const follow = document.getElementById('log-follow');
    const status = document.getElementById('log-status');
    const output = document.getElementById('log-output');
    let paused = false;
    let timer;
    let controller;

    function updateDownload() {
        const url = new URL(root.dataset.downloadUrl, window.location.origin);
        url.searchParams.set('source', source.value);
        download.href = url.toString();
    }

    async function refresh() {
        clearTimeout(timer);
        controller?.abort();
        if (paused || document.hidden) return;
        const request = new AbortController();
        controller = request;
        const timeout = setTimeout(() => request.abort(), 10000);
        try {
            const url = new URL(root.dataset.url, window.location.origin);
            url.searchParams.set('source', source.value);
            url.searchParams.set('lines', lines.value);
            const response = await fetch(url, {cache: 'no-store', signal: request.signal});
            if (response.redirected || response.status === 401 || response.status === 403) {
                paused = true;
                pause.textContent = 'Resume updates';
                pause.setAttribute('aria-pressed', 'true');
                status.textContent = 'Access denied or session expired. Sign in again.';
                return;
            }
            if (!response.ok) throw new Error('Log unavailable. Retrying…');
            const data = await response.json();
            if (controller !== request || paused) return;
            const scroll = output.scrollTop;
            // Treat log messages as text, including HTML from request URLs.
            output.textContent = data.content || 'No log entries yet.';
            output.scrollTop = follow.checked ? output.scrollHeight : scroll;
            status.textContent = data.message || `Updated ${new Date().toLocaleTimeString()}`;
        } catch (error) {
            if (controller === request && !paused) {
                status.textContent = error.name === 'AbortError' ? 'Request timed out. Retrying…' : 'Unable to load logs. Retrying…';
            }
        } finally {
            clearTimeout(timeout);
            if (controller === request && !paused && !document.hidden) {
                timer = setTimeout(refresh, 3000);
            }
        }
    }

    source.addEventListener('change', () => {
        updateDownload();
        output.textContent = '';
        status.textContent = paused ? 'Updates paused.' : 'Loading…';
        refresh();
    });
    lines.addEventListener('change', () => {
        status.textContent = paused ? 'Updates paused.' : 'Loading…';
        refresh();
    });
    pause.addEventListener('click', () => {
        paused = !paused;
        pause.textContent = paused ? 'Resume updates' : 'Pause updates';
        pause.setAttribute('aria-pressed', String(paused));
        status.textContent = paused ? 'Updates paused.' : 'Loading…';
        refresh();
    });
    document.addEventListener('visibilitychange', refresh);
    window.addEventListener('pagehide', () => {
        clearTimeout(timer);
        controller?.abort();
    });
    updateDownload();
    refresh();
})();
