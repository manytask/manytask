const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const path = require('node:path');
const {test} = require('node:test');
const vm = require('node:vm');

const source = readFileSync(path.join(__dirname, '../../manytask/static/js/course-scores.js'), 'utf8');

function card(name, maximum, classes = []) {
    const names = new Set(classes);
    const score = {textContent: ''};
    return {
        dataset: {taskName: name, maxScore: String(maximum)},
        classList: {
            contains: name => names.has(name),
            toggle: (name, enabled) => enabled ? names.add(name) : names.delete(name),
        },
        querySelector: () => score,
        score,
    };
}

function setup(cards = []) {
    const groupScore = {textContent: ''};
    const group = {
        dataset: {},
        querySelectorAll: () => cards,
        querySelector: () => groupScore,
    };
    const container = {
        children: [group], dataset: {scoresUrl: '/python/scores'},
        attributes: {'aria-busy': 'true'},
        setAttribute(name, value) { this.attributes[name] = value; },
    };
    const status = {textContent: 'Loading scores…', hidden: false};
    const percent = {textContent: ''};
    const total = {textContent: ''};
    const document = new EventTarget();
    document.hidden = false;
    document.getElementById = id => {
        assert.equal(id, 'scores-status');
        return status;
    };
    document.querySelector = selector => selector === '[data-score-percent]' ? percent : total;
    const timers = new Map();
    let nextTimer = 0;
    const window = new EventTarget();
    const context = vm.createContext({
        document, window, AbortSignal,
        setTimeout: (callback, delay) => {
            const id = ++nextTimer;
            timers.set(id, {callback, delay});
            return id;
        },
        clearTimeout: id => timers.delete(id),
    });
    vm.runInContext(source, context);
    return {context, container, group, groupScore, percent, total, status, document, window, timers};
}

function snapshot(scores, bonus = 0, max = 200) {
    return {scores, bonus_score: bonus, max_score: max};
}

function response(scores = {}) {
    return {ok: true, status: 200, json: async () => snapshot(scores)};
}

async function settle() {
    await new Promise(resolve => setImmediate(resolve));
}

async function tick(timers) {
    assert.equal(timers.size, 1);
    const [id, timer] = timers.entries().next().value;
    timers.delete(id);
    await timer.callback();
}

test('updates every tile state and score, preserving bonus and special styles', () => {
    const cards = [
        card('full', 100, ['unsolved', 'special']),
        card('partial', 100, ['solved', 'bonus']),
        card('extra', 100, ['solved_partially']),
        card('missing', 100, ['over_solved']),
        card('negative', 100, ['solved']),
    ];
    const {context, container, group, groupScore, percent, total} = setup(cards);
    context.applyCourseScores(container, snapshot({full: 100, partial: 50, extra: 120, negative: -10}, 50, 400));
    for (const [index, state] of ['solved', 'solved_partially', 'over_solved', 'unsolved', 'unsolved'].entries()) {
        for (const name of ['solved', 'solved_partially', 'over_solved', 'unsolved']) {
            assert.equal(cards[index].classList.contains(name), name === state);
        }
    }
    assert.equal(cards[0].classList.contains('special'), true);
    assert.equal(cards[1].classList.contains('bonus'), true);
    assert.equal(cards[0].score.textContent, '100/100');
    assert.equal(cards[1].score.textContent, '50/100');
    assert.equal(cards[3].score.textContent, '0/100');
    assert.equal(groupScore.textContent, 'Score: 260/400');
    assert.equal(group.dataset.groupSolved, 'false');
    assert.equal(percent.textContent, '65.0%');
    assert.equal(total.textContent, '210+50/400');
});

test('recomputes group completion after increases, reductions and missing scores', () => {
    const {context, container, group} = setup([card('one', 100), card('bonus', 100, ['bonus'])]);
    for (const [scores, solved] of [
        [{one: 100, bonus: 120}, 'true'],
        [{one: 200, bonus: 90}, 'false'],
        [{one: 100}, 'false'],
        [{one: 100, bonus: 100}, 'true'],
        [{}, 'false'],
    ]) {
        context.applyCourseScores(container, snapshot(scores));
        assert.equal(group.dataset.groupSolved, solved);
    }
});

test('handles zero maxima and empty groups after scores load', () => {
    for (const [cards, solved] of [[[], 'false'], [[card('zero', 0)], 'true']]) {
        const {context, container, group, percent, total} = setup(cards);
        context.applyCourseScores(container, snapshot({}, 0, 0));
        assert.equal(group.dataset.groupSolved, solved);
        assert.equal(percent.textContent, '0.0%');
        assert.equal(total.textContent, '0/0');
    }
});

test('missing task names that match object properties still get zero points', () => {
    const cards = [card('toString', 100), card('__proto__', 100)];
    const {context, container} = setup(cards);
    context.applyCourseScores(container, snapshot({}));
    for (const item of cards) assert.equal(item.score.textContent, '0/100');
});

test('leaves unchanged scores and ordering alone between polls', async () => {
    const {context, container, timers} = setup();
    let updates = 0;
    context.fetch = async () => response();
    context.initCourseScores(container, () => { updates++; });
    await settle();
    await tick(timers);
    assert.equal(updates, 1);
});

test('loads initial scores through the polling endpoint and clears loading placeholders', async () => {
    const item = card('task', 100, ['unsolved']);
    item.score.textContent = '…/100';
    const {context, container, group, groupScore, percent, total, status, timers} = setup([item]);
    let resolve;
    let updates = 0;
    context.fetch = () => new Promise(done => { resolve = done; });
    context.initCourseScores(container, () => { updates++; });
    assert.equal(item.score.textContent, '…/100');
    assert.equal(container.attributes['aria-busy'], 'true');
    assert.equal(status.hidden, false);
    assert.equal(timers.size, 0);

    resolve({ok: true, status: 200, json: async () => snapshot({task: 120}, 20, 100)});
    await settle();
    assert.equal(item.score.textContent, '120/100');
    assert.equal(item.classList.contains('over_solved'), true);
    assert.equal(group.dataset.groupSolved, 'true');
    assert.equal(groupScore.textContent, 'Score: 120/100');
    assert.equal(percent.textContent, '120.0%');
    assert.equal(total.textContent, '100+20/100');
    assert.equal(container.attributes['aria-busy'], 'false');
    assert.equal(status.hidden, true);
    assert.equal(updates, 1);
    assert.equal([...timers.values()][0].delay, 10000);
});

test('polls current scores and notifies the ordering callback after applying them', async () => {
    const item = card('task', 100);
    const {context, container, timers, group} = setup([item]);
    const scores = [0, 50, 100, 120, 0];
    let updates = 0;
    context.fetch = async (url, options) => {
        assert.equal(url, '/python/scores');
        assert.equal(options.credentials, 'same-origin');
        assert.equal(options.cache, 'no-store');
        assert.equal(options.redirect, 'manual');
        assert.ok(options.signal instanceof AbortSignal);
        return response({task: scores.shift()});
    };
    context.initCourseScores(container, () => {
        updates++;
        assert.equal(group.dataset.groupSolved, String(updates === 3 || updates === 4));
    });
    await settle();
    for (const score of [50, 100, 120, 0]) {
        assert.equal([...timers.values()][0].delay, 10000);
        await tick(timers);
        assert.equal(item.score.textContent, `${score}/100`);
    }
    assert.equal(updates, 5);
});

test('pauses in a hidden tab and immediately refreshes when visible', async () => {
    const {context, container, document, timers} = setup();
    let requests = 0;
    context.fetch = async () => { requests++; return response(); };
    document.hidden = true;
    context.initCourseScores(container, () => {});
    await settle();
    assert.equal(requests, 0);
    document.hidden = false;
    document.dispatchEvent(new Event('visibilitychange'));
    await settle();
    assert.equal(requests, 1);
    assert.equal(timers.size, 1);
    document.hidden = true;
    document.dispatchEvent(new Event('visibilitychange'));
    assert.equal(timers.size, 0);
    document.hidden = false;
    document.dispatchEvent(new Event('visibilitychange'));
    await settle();
    assert.equal(requests, 2);
});

test('does not overlap requests or apply responses received while hidden', async () => {
    const {context, container, document, window, timers} = setup();
    let resolve;
    let requests = 0;
    let updates = 0;
    context.fetch = () => { requests++; return new Promise(done => { resolve = done; }); };
    context.initCourseScores(container, () => { updates++; });
    window.dispatchEvent(new Event('pageshow'));
    document.dispatchEvent(new Event('visibilitychange'));
    assert.equal(requests, 1);
    assert.equal(timers.size, 0);
    document.hidden = true;
    resolve(response());
    await settle();
    assert.equal(updates, 0);
    assert.equal(timers.size, 0);
});

test('retries outages with capped backoff and returns to ten seconds after recovery', async () => {
    const {context, container, timers, status} = setup();
    let failing = true;
    let updates = 0;
    context.fetch = async () => {
        if (failing) throw new Error('Offline');
        return response();
    };
    context.initCourseScores(container, () => { updates++; });
    await settle();
    assert.equal(status.textContent, 'Unable to load scores. Retrying…');
    assert.equal(status.hidden, false);
    for (const delay of [20000, 30000, 30000]) {
        assert.equal([...timers.values()][0].delay, delay);
        await tick(timers);
    }
    assert.equal(updates, 0);
    failing = false;
    await tick(timers);
    assert.equal(updates, 1);
    assert.equal(status.hidden, true);
    assert.equal([...timers.values()][0].delay, 10000);
});

test('stops on login redirects and denied access', async () => {
    for (const status of [0, 302, 401, 403, 404]) {
        const {context, container, timers, status: loadingStatus} = setup();
        context.fetch = async () => ({status, type: status === 0 ? 'opaqueredirect' : 'basic'});
        context.initCourseScores(container, () => assert.fail('Must keep the last scores'));
        await settle();
        assert.equal(timers.size, 0);
        assert.equal(container.attributes['aria-busy'], 'false');
        assert.equal(loadingStatus.hidden, false);
        assert.match(loadingStatus.textContent, /Reload the page/);
    }
});

test('keeps the last scores and retries server errors and malformed responses', async () => {
    for (const result of [
        {ok: false, status: 500},
        {ok: true, status: 200, json: async () => { throw new Error('Invalid JSON'); }},
    ]) {
        const item = card('task', 100);
        const {context, container, timers} = setup([item]);
        item.score.textContent = '50/100';
        context.fetch = async () => result;
        context.initCourseScores(container, () => assert.fail('Must keep the last scores'));
        await settle();
        assert.equal(item.score.textContent, '50/100');
        assert.equal([...timers.values()][0].delay, 20000);
    }
});
