const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const path = require('node:path');
const {test} = require('node:test');
const vm = require('node:vm');

const source = readFileSync(path.join(__dirname, '../../manytask/static/js/namespace-delete.js'), 'utf8');

function element() {
    const classes = new Set(['d-none']);
    return {
        value: '', textContent: '', disabled: false, focused: false, handlers: {},
        classList: {
            add: name => classes.add(name),
            remove: name => classes.delete(name),
            contains: name => classes.has(name),
        },
        addEventListener(event, handler) { this.handlers[event] = handler; },
        focus() { this.focused = true; },
    };
}

function load(fetchResponse) {
    const elements = Object.fromEntries([
        'deleteNamespaceForm', 'deleteNamespaceName', 'deleteNamespaceError',
        'deleteNamespaceModal', 'deleteNamespaceExpectedName', 'namespaceDisplayName',
    ].map(id => [id, element()]));
    elements.namespaceDisplayName.textContent = 'Current namespace';
    const button = {disabled: true};
    elements.deleteNamespaceForm.dataset = {deleteUrl: '/api/namespaces/42', redirectUrl: '/'};
    elements.deleteNamespaceForm.querySelector = selector => {
        assert.equal(selector, '[type="submit"]');
        return button;
    };
    const requests = [];
    const redirects = [];
    vm.runInContext(source, vm.createContext({
        document: {getElementById: id => {
            assert.ok(Object.hasOwn(elements, id), `Unexpected element: ${id}`);
            return elements[id];
        }},
        window: {location: {assign: url => redirects.push(url)}},
        fetch: async (url, options) => {
            requests.push({url, options});
            return fetchResponse();
        },
    }));
    return {
        elements, button, requests, redirects,
        open() { elements.deleteNamespaceModal.handlers['show.bs.modal'](); },
        type(name) {
            elements.deleteNamespaceName.value = name;
            elements.deleteNamespaceName.handlers.input();
        },
        async submit() {
            let prevented = false;
            await elements.deleteNamespaceForm.handlers.submit({preventDefault() { prevented = true; }});
            assert.ok(prevented);
        },
    };
}

test('requires the exact saved namespace name and resets confirmation when reopened', async () => {
    const harness = load(() => { throw new Error('Unexpected request'); });
    harness.open();
    assert.equal(harness.elements.deleteNamespaceExpectedName.textContent, 'Current namespace');
    for (const name of ['', 'current namespace', ' Current namespace ', 'Unsaved name']) {
        harness.type(name);
        assert.equal(harness.button.disabled, true);
    }
    await harness.submit();
    assert.equal(harness.requests.length, 0);
    assert.equal(harness.elements.deleteNamespaceError.textContent, 'Namespace name does not match');
    assert.equal(harness.elements.deleteNamespaceName.focused, true);

    harness.type('Current namespace');
    assert.equal(harness.button.disabled, false);
    // Settings saves update this display; unsaved input does not change the confirmation.
    harness.elements.namespaceDisplayName.textContent = 'Renamed namespace';
    harness.open();
    assert.equal(harness.elements.deleteNamespaceExpectedName.textContent, 'Renamed namespace');
    assert.equal(harness.elements.deleteNamespaceName.value, '');
    assert.equal(harness.button.disabled, true);
    assert.equal(harness.elements.deleteNamespaceError.classList.contains('d-none'), true);
});

test('sends DELETE with the confirmed name, prevents duplicate requests and redirects after success', async () => {
    let finish;
    const harness = load(() => new Promise(resolve => { finish = resolve; }));
    harness.open();
    harness.type('Current namespace');
    const submission = harness.submit();
    assert.equal(harness.button.disabled, true);
    assert.equal(harness.elements.deleteNamespaceName.disabled, true);
    assert.equal(harness.redirects.length, 0);
    await harness.submit();
    assert.equal(harness.requests.length, 1);
    const {url, options} = harness.requests[0];
    assert.equal(url, '/api/namespaces/42');
    assert.equal(options.method, 'DELETE');
    assert.equal(options.headers['Content-Type'], 'application/json');
    assert.deepEqual(JSON.parse(options.body), {name: 'Current namespace'});
    finish({ok: true}); // 204 has no JSON body.
    await submission;
    assert.deepEqual(harness.redirects, ['/']);
});

for (const [kind, fetchResponse, expected] of [
    ['nonempty namespace', async () => ({
        ok: false, json: async () => ({error: 'Cannot delete namespace: it still contains courses'}),
    }), 'Cannot delete namespace: it still contains courses'],
    ['server failure', async () => ({
        ok: false, json: async () => ({error: 'Failed to delete namespace. Please try again.'}),
    }), 'Failed to delete namespace. Please try again.'],
    ['non-JSON server failure', async () => ({
        ok: false, json: async () => { throw new Error('Not JSON'); },
    }), 'Failed to delete namespace. Please try again.'],
    ['network failure', async () => { throw new Error('Disconnected'); },
        'Failed to delete namespace. Please try again.'],
]) {
    test(`${kind} displays an error, stays on the page and allows retry`, async () => {
        const harness = load(fetchResponse);
        harness.open();
        harness.type('Current namespace');
        await harness.submit();
        assert.equal(harness.elements.deleteNamespaceError.textContent, expected);
        assert.equal(harness.elements.deleteNamespaceError.classList.contains('d-none'), false);
        assert.equal(harness.button.disabled, false);
        assert.equal(harness.elements.deleteNamespaceName.disabled, false);
        assert.equal(harness.elements.deleteNamespaceName.value, 'Current namespace');
        assert.equal(harness.redirects.length, 0);
    });
}
