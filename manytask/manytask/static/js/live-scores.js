function applyLiveScores(container, snapshot) {
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

function initLiveScores(container, onUpdate) {
    const interval = 2000;
    let delay = interval;
    let timer;
    let inFlight = false;
    let stopped = false;
    let lastSnapshot;

    async function refresh() {
        clearTimeout(timer);
        if (stopped || document.hidden || inFlight) return;
        inFlight = true;
        try {
            const response = await fetch(container.dataset.scoresUrl, {
                credentials: 'same-origin',
                cache: 'no-store',
                redirect: 'manual',
                signal: AbortSignal.timeout(10000),
            });
            // Session expiry and revoked course access need a fresh page/login.
            if (response.type === 'opaqueredirect' || [301, 302, 303, 307, 308, 401, 403, 404].includes(response.status)) {
                stopped = true;
                return;
            }
            if (!response.ok) throw new Error('Score refresh failed');
            const snapshot = await response.json();
            const serialized = JSON.stringify(snapshot);
            if (!document.hidden && !stopped && serialized !== lastSnapshot) {
                applyLiveScores(container, snapshot);
                onUpdate();
                lastSnapshot = serialized;
            }
            delay = interval;
        } catch {
            // Keep the last scores during an outage and retry with a capped backoff.
            delay = Math.min(delay * 2, 30000);
        } finally {
            inFlight = false;
            if (!stopped && !document.hidden) timer = setTimeout(refresh, delay);
        }
    }

    document.addEventListener('visibilitychange', refresh);
    window.addEventListener('pageshow', refresh);
    refresh();
}
