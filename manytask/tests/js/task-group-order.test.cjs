const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const path = require('node:path');
const {test} = require('node:test');
const vm = require('node:vm');

const scriptPath = path.join(__dirname, '../../manytask/static/js/task-group-order.js');
const source = readFileSync(scriptPath, 'utf8');

function load(storage = new Map()) {
    const context = vm.createContext({
        localStorage: {
            getItem: key => storage.get(key),
            setItem: (key, value) => storage.set(key, value),
        },
    });
    vm.runInContext(source, context);
    return context;
}

function control(username = 'alice', courseName = 'python') {
    const button = new EventTarget();
    button.dataset = {username, courseName};
    button.value = 'desc';
    return button;
}

test('sorts by opening date in either direction, preserving ties and input order', () => {
    const context = load();
    const groups = [
        {name: 'new', start: '2026-09-20T00:00:00Z'},
        {name: 'old', start: '2026-09-01T00:00:00Z'},
        {name: 'same instant', start: '2026-09-20T03:00:00+03:00'},
        {name: 'middle', start: '2026-09-10T00:00:00Z'},
    ];
    const names = items => Array.from(items, group => group.name);
    assert.deepEqual(names(context.sortTaskGroups(groups, 'asc')), ['old', 'middle', 'new', 'same instant']);
    assert.deepEqual(names(context.sortTaskGroups(groups, 'desc')), ['new', 'same instant', 'middle', 'old']);
    assert.deepEqual(names(groups), ['new', 'old', 'same instant', 'middle']);
});

test('toggles with one click and persists both choices separately for each user and course', () => {
    const storage = new Map();
    const assignments = control();
    load(storage).initTaskGroupOrder(assignments);
    assert.equal(assignments.value, 'desc');
    assert.equal(assignments.textContent, 'Show oldest first');
    assignments.dispatchEvent(new Event('click'));
    assert.equal(assignments.value, 'asc');
    assert.equal(assignments.textContent, 'Show newest first');

    const scores = control();
    load(storage).initTaskGroupOrder(scores);
    assert.equal(scores.value, 'asc');
    assert.equal(scores.textContent, 'Show newest first');
    for (const other of [control('bob'), control('alice', 'cpp')]) {
        load(storage).initTaskGroupOrder(other);
        assert.equal(other.value, 'desc');
    }

    scores.dispatchEvent(new Event('click'));
    assert.equal(scores.value, 'desc');
    assert.equal(scores.textContent, 'Show oldest first');
    const reloaded = control();
    load(storage).initTaskGroupOrder(reloaded);
    assert.equal(reloaded.value, 'desc');
});

test('invalid saved values fall back to newest first', () => {
    const context = load();
    context.localStorage.getItem = () => 'invalid';
    const button = control();
    context.initTaskGroupOrder(button);
    assert.equal(button.value, 'desc');
});

test('the control still works when browser storage is unavailable', () => {
    const context = load();
    Object.defineProperty(context, 'localStorage', {get() { throw new Error('Storage blocked'); }});
    const button = control();
    context.initTaskGroupOrder(button);
    assert.equal(button.value, 'desc');
    const groups = [
        {name: 'new', start: '2026-09-20T00:00:00Z'},
        {name: 'old', start: '2026-09-01T00:00:00Z'},
    ];
    let sorted;
    button.addEventListener('click', () => {
        sorted = context.sortTaskGroups(groups, button.value);
    });
    button.dispatchEvent(new Event('click'));
    assert.deepEqual(Array.from(sorted, group => group.name), ['old', 'new']);
});
