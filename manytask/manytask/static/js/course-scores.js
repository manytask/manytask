function applyCourseScores(container, snapshot) {
    const states = ['unsolved', 'solved_partially', 'solved', 'over_solved'];
    for (const group of container.children) {
        const cards = Array.from(group.querySelectorAll('[data-task-name]'));
        let total = 0;
        let maximum = 0;
        let solved = cards.length > 0;
        for (const card of cards) {
            const score = Object.hasOwn(snapshot.scores, card.dataset.taskName)
                ? snapshot.scores[card.dataset.taskName] : 0;
            const maxScore = Number(card.dataset.maxScore);
            const state = score === maxScore ? 'solved'
                : score > maxScore ? 'over_solved'
                : score > 0 ? 'solved_partially' : 'unsolved';
            for (const name of states) card.classList.toggle(name, name === state);
            card.querySelector('.score').textContent = `${score}/${maxScore}`;
            total += score;
            if (!card.classList.contains('bonus')) maximum += maxScore;
            if (score < maxScore) solved = false;
        }
        group.dataset.groupSolved = String(solved);
        group.querySelector('[data-group-score]').textContent = `Score: ${total}/${maximum}`;
    }

    const total = Object.values(snapshot.scores).reduce((sum, score) => sum + score, 0);
    const bonus = snapshot.bonus_score;
    const percent = snapshot.max_score === 0 ? '0.0' : (total / snapshot.max_score * 100).toFixed(1);
    document.querySelector('[data-score-percent]').textContent = `${percent}%`;
    document.querySelector('[data-score-total]').textContent =
        `${total - bonus}${bonus > 0 ? `+${bonus}` : ''}/${snapshot.max_score}`;
}

function initCourseScores(container, onUpdate) {
    const status = document.getElementById('scores-status');
    const url = container.dataset.scoresUrl;
    let source;
    let controller;
    let pending = false;
    let stopped = false;
    let timer;
    let delay = 2000;
    let lastSnapshot;

    function disconnect() {
        clearTimeout(timer);
        source?.close();
        source = undefined;
        controller?.abort();
        controller = undefined;
        pending = false;
    }

    function retry() {
        disconnect();
        timer = setTimeout(connect, delay);
        delay = Math.min(2 * delay, 30000);
    }

    async function refresh() {
        if (controller) {
            pending = true;
            return;
        }
        const request = new AbortController();
        controller = request;
        try {
            const response = await fetch(url, {
                credentials: 'same-origin',
                cache: 'no-store',
                redirect: 'manual',
                signal: AbortSignal.any([request.signal, AbortSignal.timeout(10000)]),
            });
            if (request.signal.aborted) return;
            if (response.type === 'opaqueredirect' || [301, 302, 303, 307, 308, 401, 403, 404].includes(response.status)) {
                stopped = true;
                disconnect();
                status.hidden = false;
                status.textContent = 'Unable to load scores. Reload the page to check your access.';
                container.setAttribute('aria-busy', 'false');
                return;
            }
            if (!response.ok) throw new Error('Score request failed');
            const snapshot = await response.json();
            if (request.signal.aborted) return;
            const serialized = JSON.stringify(snapshot);
            if (serialized !== lastSnapshot) {
                applyCourseScores(container, snapshot);
                onUpdate();
                lastSnapshot = serialized;
            }
            if (source) delay = 2000;
            status.hidden = true;
            container.setAttribute('aria-busy', 'false');
        } catch {
            if (request.signal.aborted) return;
            if (lastSnapshot === undefined) status.textContent = 'Unable to load scores. Retrying…';
            retry();
        } finally {
            if (controller === request) {
                controller = undefined;
                if (pending) {
                    pending = false;
                    refresh();
                }
            }
        }
    }

    function connect() {
        if (stopped || document.hidden || source) return;
        if (typeof EventSource === 'undefined') {
            refresh();
            return;
        }
        const stream = new EventSource(url);
        source = stream;
        stream.onmessage = () => {
            if (source !== stream) return;
            refresh();
        };
        stream.onerror = () => {
            if (source !== stream) return;
            if (stream.readyState === EventSource.CONNECTING && lastSnapshot !== undefined) return;
            retry();
            // A failed stream may mean expired access. The JSON endpoint also
            // supplies the initial scores if a proxy cannot serve the stream.
            refresh();
        };
    }

    document.addEventListener('visibilitychange', () => document.hidden ? disconnect() : connect());
    window.addEventListener('pagehide', disconnect);
    window.addEventListener('pageshow', connect);
    connect();
}
