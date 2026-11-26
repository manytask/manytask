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
    const streams = [];
    class EventSource {
        static CONNECTING = 0;
        constructor(url) {
            assert.equal(url, container.dataset.scoresUrl);
            streams.push(this);
        }
        close() { this.closed = true; }
    }
    const context = vm.createContext({
        document, window: new EventTarget(), EventSource, AbortController, AbortSignal, setTimeout, clearTimeout,
    });
    vm.runInContext(source, context);
    return {context, container, group, groupScore, percent, total, status, streams};
}

const settle = () => new Promise(resolve => setImmediate(resolve));

function snapshot(scores, bonus = 0, max = 200) {
    return {scores, bonus_score: bonus, max_score: max};
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

test('loads initial scores through the course scores endpoint and clears loading placeholders', async () => {
    const item = card('task', 100, ['unsolved']);
    item.score.textContent = '…/100';
    const {context, container, group, groupScore, percent, total, status, streams} = setup([item]);
    let resolve;
    let updates = 0;
    let requests = 0;
    context.fetch = (url, options) => {
        requests++;
        assert.equal(url, '/python/scores');
        assert.equal(options.cache, 'no-store');
        return new Promise(done => { resolve = done; });
    };
    context.initCourseScores(container, () => { updates++; });
    streams[0].onmessage();
    assert.equal(item.score.textContent, '…/100');
    assert.equal(container.attributes['aria-busy'], 'true');
    assert.equal(status.hidden, false);

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
    assert.equal(requests, 1);
});

test('shows a reload message when the initial request fails', async () => {
    const {context, container, status, streams} = setup();
    context.fetch = async () => ({ok: false, status: 403});
    let updates = 0;
    context.initCourseScores(container, () => { updates++; });
    streams[0].onerror();
    await settle();
    assert.ok(streams[0].closed);
    assert.equal(updates, 0);
    assert.equal(container.attributes['aria-busy'], 'false');
    assert.equal(status.hidden, false);
    assert.match(status.textContent, /Reload the page/);
});

test('coalesces invalidations during a read and stays idle between events', async () => {
    const {context, container, streams, total} = setup();
    const requests = [];
    context.fetch = () => new Promise(resolve => requests.push(resolve));
    context.setTimeout = () => assert.fail('scheduled a poll');
    let updates = 0;
    context.initCourseScores(container, () => updates++);
    context.window.dispatchEvent(new Event('pageshow'));
    assert.equal(streams.length, 1);
    for (let i = 0; i < 5; i++) streams[0].onmessage();
    assert.equal(requests.length, 1);
    requests[0]({ok: true, json: async () => snapshot({x: 2})});
    await settle();
    assert.equal(requests.length, 2);
    requests[1]({ok: true, json: async () => snapshot({x: 7})});
    await settle();
    assert.equal(total.textContent, '7/200');
    streams[0].onmessage();
    requests[2]({ok: true, json: async () => snapshot({x: 7})});
    await settle();
    assert.equal(updates, 2);
});

test('closes hidden streams and ignores stale responses after resuming', async () => {
    const {context, container, streams, total} = setup();
    const requests = [];
    context.fetch = () => new Promise(resolve => requests.push(resolve));
    context.initCourseScores(container, () => {});
    streams[0].onmessage();
    context.document.hidden = true;
    context.document.dispatchEvent(new Event('visibilitychange'));
    assert.ok(streams[0].closed);
    context.document.hidden = false;
    context.document.dispatchEvent(new Event('visibilitychange'));
    streams[0].onmessage();
    streams[1].onmessage();
    assert.equal(requests.length, 2);
    requests[1]({ok: true, json: async () => snapshot({x: 10})});
    await settle();
    requests[0]({ok: true, json: async () => snapshot({x: 1})});
    await settle();
    assert.equal(total.textContent, '10/200');
    context.window.dispatchEvent(new Event('pagehide'));
    assert.ok(streams[1].closed);
});

test('recovers from a failed snapshot and stops reconnecting after access is revoked', async () => {
    const {context, container, status, streams} = setup();
    let reconnect;
    context.setTimeout = callback => { reconnect = callback; return 1; };
    context.clearTimeout = () => { reconnect = undefined; };
    context.fetch = async () => ({ok: false, status: 503});
    context.initCourseScores(container, () => {});
    streams[0].onmessage();
    await settle();
    assert.ok(streams[0].closed);
    assert.match(status.textContent, /Retrying/);
    reconnect();
    context.fetch = async () => ({ok: true, json: async () => snapshot({x: 3})});
    streams[1].onmessage();
    await settle();
    assert.equal(status.hidden, true);

    context.fetch = async () => ({ok: false, status: 403});
    streams[1].onmessage();
    await settle();
    assert.ok(streams[1].closed);
    assert.equal(reconnect, undefined);
    context.window.dispatchEvent(new Event('pageshow'));
    assert.equal(streams.length, 2);
    assert.equal(status.hidden, false);
    assert.match(status.textContent, /check your access/);
});
