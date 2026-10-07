const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const path = require('node:path');
const {test} = require('node:test');
const vm = require('node:vm');

const scriptPath = path.join(__dirname, '../../manytask/static/js/future-tasks.js');

function load(storage = new Map()) {
    const context = vm.createContext({
        localStorage: {
            getItem: key => storage.get(key),
            setItem: (key, value) => storage.set(key, value),
        },
    });
    vm.runInContext(readFileSync(scriptPath, 'utf8'), context);
    return context;
}

function control(username = 'alice', courseName = 'python') {
    const button = new EventTarget();
    button.dataset = {username, courseName};
    button.attributes = new Map();
    button.setAttribute = (name, value) => button.attributes.set(name, value);
    button.getAttribute = name => button.attributes.get(name);
    return button;
}

test('future groups start hidden and toggle together with an accessible button state', () => {
    const button = control();
    const groups = [{hidden: true}, {hidden: true}];
    load().initFutureTasks(button, groups);
    assert.equal(button.getAttribute('aria-pressed'), 'false');
    assert.equal(button.textContent, 'Show future tasks');
    assert.ok(groups.every(group => group.hidden));

    button.dispatchEvent(new Event('click'));
    assert.ok(groups.every(group => !group.hidden));
    assert.equal(button.getAttribute('aria-pressed'), 'true');
    assert.equal(button.textContent, 'Hide future tasks');

    button.dispatchEvent(new Event('click'));
    assert.ok(groups.every(group => group.hidden));
    assert.equal(button.getAttribute('aria-pressed'), 'false');
    assert.equal(button.textContent, 'Show future tasks');
});

test('the preference survives reloads and is isolated by user and course', () => {
    const storage = new Map();
    const button = control();
    load(storage).initFutureTasks(button, []);
    button.dispatchEvent(new Event('click'));

    const reopened = control();
    const groups = [{hidden: true}];
    load(storage).initFutureTasks(reopened, groups);
    assert.equal(groups[0].hidden, false);
    assert.equal(reopened.getAttribute('aria-pressed'), 'true');
    for (const other of [control('bob'), control('alice', 'cpp')]) {
        const otherGroups = [{hidden: true}];
        load(storage).initFutureTasks(other, otherGroups);
        assert.equal(otherGroups[0].hidden, true);
    }

    reopened.dispatchEvent(new Event('click'));
    const reloaded = control();
    load(storage).initFutureTasks(reloaded, groups);
    assert.equal(groups[0].hidden, true);
    assert.equal(reloaded.getAttribute('aria-pressed'), 'false');
});

test('invalid saved values leave future tasks hidden', () => {
    const context = load();
    context.localStorage.getItem = () => 'invalid';
    const groups = [{hidden: true}];
    context.initFutureTasks(control(), groups);
    assert.equal(groups[0].hidden, true);
});

test('the button still works when browser storage is blocked', () => {
    const context = load();
    Object.defineProperty(context, 'localStorage', {get() { throw new Error('Storage blocked'); }});
    const button = control();
    const groups = [{hidden: true}];
    context.initFutureTasks(button, groups);
    button.dispatchEvent(new Event('click'));
    assert.equal(groups[0].hidden, false);
    button.dispatchEvent(new Event('click'));
    assert.equal(groups[0].hidden, true);
});
