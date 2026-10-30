const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const path = require('node:path');
const {test} = require('node:test');
const vm = require('node:vm');

const source = readFileSync(path.join(__dirname, '../../manytask/static/js/database-student-removal.js'), 'utf8');

function load() {
    const elements = {};
    for (const id of ['Modal', 'Form', 'Username', 'Confirmation', 'Submit', 'Name']) {
        elements[`removeStudent${id}`] = {
            value: '',
            textContent: '',
            disabled: true,
            listeners: {},
            addEventListener(name, callback) { this.listeners[name] = callback; },
            focus() { this.focused = true; },
        };
    }
    const context = vm.createContext({
        document: {getElementById: id => elements[id]},
        bootstrap: {Modal: class { show() {} }},
    });
    vm.runInContext(source, context);
    const open = context.initStudentRemoval();
    return {
        elements,
        open,
        input(value) {
            elements.removeStudentConfirmation.value = value;
            elements.removeStudentConfirmation.listeners.input();
        },
        submit() {
            let prevented = false;
            elements.removeStudentForm.listeners.submit({preventDefault() { prevented = true; }});
            return !prevented;
        },
    };
}

test('removal requires an exact, case-sensitive username, including when submitted via Enter', () => {
    const ui = load();
    ui.open('Student');
    for (const value of ['', 'student', 'Student ', 'Other']) {
        ui.input(value);
        assert.equal(ui.elements.removeStudentSubmit.disabled, true);
        assert.equal(ui.submit(), false);
    }
    ui.input('Student');
    assert.equal(ui.elements.removeStudentSubmit.disabled, false);
    assert.equal(ui.submit(), true);
    assert.equal(ui.elements.removeStudentSubmit.disabled, true);
    assert.equal(ui.submit(), false);
});

test('changing students or cancelling clears confirmation and safely displays the username', () => {
    const ui = load();
    ui.open('first');
    ui.input('first');
    ui.open('<student>');
    assert.equal(ui.elements.removeStudentUsername.value, '<student>');
    assert.equal(ui.elements.removeStudentName.textContent, '<student>');
    assert.equal(ui.elements.removeStudentConfirmation.value, '');
    assert.equal(ui.submit(), false);
    ui.input('<student>');
    ui.elements.removeStudentModal.listeners['hidden.bs.modal']();
    assert.equal(ui.submit(), false);
    assert.equal(ui.elements.removeStudentSubmit.disabled, true);
    ui.elements.removeStudentModal.listeners['shown.bs.modal']();
    assert.equal(ui.elements.removeStudentConfirmation.focused, true);
});
