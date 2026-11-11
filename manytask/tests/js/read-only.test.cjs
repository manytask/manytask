const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const path = require('node:path');
const {test} = require('node:test');
const vm = require('node:vm');

const script = readFileSync(path.join(__dirname, '../../manytask/static/js/read-only.js'), 'utf8');

function load() {
    const message = 'Read-only mode';
    const listeners = {};
    const field = {};
    const button = {matches: () => false, setAttribute(name, value) { this[name] = value; }};
    const link = {
        ...button,
        matches: selector => selector === 'a',
        classList: new Set(),
    };
    const form = {
        matches: selector => selector === 'form',
        querySelectorAll: () => [field],
    };
    vm.runInNewContext(script, {
        document: {
            getElementById: () => ({textContent: message}),
            querySelectorAll: () => [form, button, link],
            addEventListener(name, handler, capture) {
                assert.equal(capture, true);
                listeners[name] = handler;
            },
        },
    });
    function dispatch(name, mutation) {
        const event = {
            target: {closest: () => mutation ? button : null},
            preventDefault() { this.prevented = true; },
            stopImmediatePropagation() { this.stopped = true; },
        };
        listeners[name](event);
        return event;
    }
    return {field, button, link, form, message, dispatch};
}

test('disables mutation forms, standalone actions and links with an explanation', () => {
    const {field, button, link, form, message} = load();
    assert.equal(field.disabled, true);
    assert.equal(button.disabled, true);
    assert.equal(link['aria-disabled'], 'true');
    assert.equal(link.classList.has('disabled'), true);
    for (const element of [field, button, link, form]) {
        assert.equal(element.title, message);
    }
});

test('blocks mutation handlers even if another script re-enables their controls', () => {
    const {button, dispatch} = load();
    button.disabled = false;
    for (const name of ['click', 'change', 'submit']) {
        const event = dispatch(name, true);
        assert.equal(event.prevented, true);
        assert.equal(event.stopped, true);
    }
});

test('leaves viewing controls, filters and exports interactive', () => {
    const {dispatch} = load();
    for (const name of ['click', 'change', 'submit']) {
        const event = dispatch(name, false);
        assert.equal(event.prevented, undefined);
        assert.equal(event.stopped, undefined);
    }
});
