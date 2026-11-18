const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const path = require('node:path');
const {test} = require('node:test');
const vm = require('node:vm');

function load() {
    const context = vm.createContext({});
    for (const file of ['task-group-order.js', 'solved-last.js']) {
        vm.runInContext(readFileSync(path.join(__dirname, '../../manytask/static/js', file), 'utf8'), context);
    }
    return context;
}

function control() {
    const button = new EventTarget();
    button.textContent = 'Hide solved';
    button.attributes = {'aria-pressed': 'false'};
    button.setAttribute = (name, value) => { button.attributes[name] = value; };
    return button;
}

test('moves solved groups last while preserving the selected order and ties, then restores order', () => {
    const context = load();
    const groups = [
        {name: 'new solved', start: '2026-09-20T00:00:00Z', solved: true},
        {name: 'old unsolved', start: '2026-09-01T00:00:00Z', solved: false},
        {name: 'old solved', start: '2026-09-01T00:00:00Z', solved: true},
        {name: 'new unsolved', start: '2026-09-20T00:00:00Z', solved: false},
        {name: 'same instant', start: '2026-09-20T03:00:00+03:00', solved: false},
    ];
    const original = groups.slice();
    const button = control();
    let order = 'desc';
    let displayed;
    const applyOrder = () => {
        displayed = context.sortTaskGroups(groups, order);
        if (button.value === 'true') displayed = context.moveSolvedGroupsLast(displayed);
    };
    const names = () => Array.from(displayed, group => group.name);
    context.initSolvedLast(button, applyOrder);
    applyOrder();
    assert.deepEqual(names(), ['new solved', 'new unsolved', 'same instant', 'old unsolved', 'old solved']);

    button.dispatchEvent(new Event('click'));
    assert.deepEqual(names(), ['new unsolved', 'same instant', 'old unsolved', 'new solved', 'old solved']);
    assert.equal(button.textContent, 'Show solved');
    assert.equal(button.attributes['aria-pressed'], 'true');

    order = 'asc';
    applyOrder();
    assert.deepEqual(names(), ['old unsolved', 'new unsolved', 'same instant', 'old solved', 'new solved']);
    button.dispatchEvent(new Event('click'));
    assert.deepEqual(names(), ['old unsolved', 'old solved', 'new solved', 'new unsolved', 'same instant']);
    assert.equal(button.textContent, 'Hide solved');
    assert.equal(button.attributes['aria-pressed'], 'false');
    assert.deepEqual(groups, original);
});

test('handles empty courses and courses with only solved or only unsolved groups', () => {
    const context = load();
    for (const groups of [[], [true, true], [false, false]]) {
        const tasks = groups.map((solved, index) => ({
            solved, start: `2026-09-0${index + 1}T00:00:00Z`,
        }));
        assert.deepEqual(
            Array.from(context.moveSolvedGroupsLast(context.sortTaskGroups(tasks, 'desc'))),
            [...tasks].reverse(),
        );
    }
    const button = control();
    context.initSolvedLast(button, () => context.moveSolvedGroupsLast(context.sortTaskGroups([], 'desc')));
    button.dispatchEvent(new Event('click'));
    button.dispatchEvent(new Event('click'));
    assert.equal(button.textContent, 'Hide solved');
});

test('the page moves actual group elements even with the previously cached date sorter', () => {
    const context = load();
    // Browsers can retain the original two-argument sorter for 24 hours.
    context.sortTaskGroups = (groups, order) => [...groups].sort((a, b) =>
        (order === 'asc' ? 1 : -1) * (Date.parse(a.start) - Date.parse(b.start)));
    context.localStorage = {getItem: () => null, setItem() {}};
    const solved = {dataset: {groupStart: '2026-09-20T00:00:00Z', groupSolved: 'true'}};
    const unsolved = {dataset: {groupStart: '2026-09-01T00:00:00Z', groupSolved: 'false'}};
    const container = {
        children: [solved, unsolved],
        appendChild(element) {
            this.children.splice(this.children.indexOf(element), 1);
            this.children.push(element);
        },
    };
    const solvedButton = control();
    const orderButton = control();
    orderButton.dataset = {username: 'alice', courseName: 'python'};
    const elements = {'solved-last': solvedButton, 'task-group-order': orderButton, 'task-groups': container};
    context.document = {getElementById: id => elements[id]};
    const template = readFileSync(path.join(__dirname, '../../manytask/templates/tasks.html'), 'utf8');
    const inlineScript = template.match(/<script>\s*(const orderButton[\s\S]*?)<\/script>/)[1];
    vm.runInContext(inlineScript, context);

    solvedButton.dispatchEvent(new Event('click'));
    assert.deepEqual(container.children, [unsolved, solved]);
    assert.equal(solvedButton.textContent, 'Show solved');
    assert.ok(container.children.every(group => !group.hidden));
    orderButton.dispatchEvent(new Event('click'));
    assert.deepEqual(container.children, [unsolved, solved]);
    solvedButton.dispatchEvent(new Event('click'));
    assert.equal(solvedButton.textContent, 'Hide solved');
    orderButton.dispatchEvent(new Event('click'));
    assert.deepEqual(container.children, [solved, unsolved]);
});
