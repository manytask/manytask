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

async function initCourseScores(container, onUpdate) {
    const status = document.getElementById('scores-status');
    try {
        const response = await fetch(container.dataset.scoresUrl, {
            credentials: 'same-origin',
            cache: 'no-store',
            redirect: 'manual',
            signal: AbortSignal.timeout(10000),
        });
        if (!response.ok) throw new Error('Score request failed');
        applyCourseScores(container, await response.json());
        onUpdate();
        status.hidden = true;
    } catch {
        status.textContent = 'Unable to load scores. Reload the page to try again.';
    } finally {
        container.setAttribute('aria-busy', 'false');
    }
}
