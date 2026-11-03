const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const path = require('node:path');
const {test} = require('node:test');
const vm = require('node:vm');

const scriptPath = path.join(__dirname, '../../manytask/static/js/namespace-settings.js');
const source = readFileSync(scriptPath, 'utf8');

function element(value = '') {
    const classes = new Set(['d-none']);
    return {
        value,
        textContent: '',
        hidden: false,
        focused: false,
        classList: {
            add: name => classes.add(name),
            remove: name => classes.delete(name),
            contains: name => classes.has(name),
        },
        focus() { this.focused = true; },
    };
}

function load(fetchResponse) {
    const saveButton = {disabled: false};
    const elements = {
        namespaceName: element('Original name'),
        namespaceDescription: element('Original description'),
        namespaceSettingsError: element(),
        namespaceSettingsSuccess: element(),
        namespaceDisplayName: element(),
        namespaceDisplayDescription: element(),
    };
    elements.namespaceDisplayName.textContent = 'Original name';
    elements.namespaceDisplayDescription.textContent = 'Original description';
    let submitHandler;
    elements.namespaceSettingsForm = {
        dataset: {updateUrl: '/api/namespaces/42'},
        addEventListener(event, handler) {
            assert.equal(event, 'submit');
            submitHandler = handler;
        },
        querySelector(selector) {
            assert.equal(selector, '[type="submit"]');
            return saveButton;
        },
    };
    const document = {
        title: 'Original name - Namespace Panel',
        getElementById: id => {
            assert.ok(Object.hasOwn(elements, id), `Unexpected element: ${id}`);
            return elements[id];
        },
    };
    const requests = [];
    vm.runInContext(source, vm.createContext({
        document,
        fetch: async (url, options) => {
            requests.push({url, options});
            return fetchResponse();
        },
    }));
    return {
        elements,
        document,
        requests,
        saveButton,
        async submit() {
            let prevented = false;
            await submitHandler({
                currentTarget: elements.namespaceSettingsForm,
                preventDefault() { prevented = true; },
            });
            assert.ok(prevented);
        },
    };
}

function response(data, ok = true) {
    return {ok, json: async () => data};
}

test('saves the trimmed name and current description, then updates namespace details and title', async () => {
    let finishRequest;
    const harness = load(() => new Promise(resolve => { finishRequest = resolve; }));
    const {elements, saveButton} = harness;
    elements.namespaceName.value = '  New namespace  ';
    elements.namespaceDescription.value = '  Current description\nwith details  ';
    elements.namespaceSettingsError.classList.remove('d-none');
    elements.namespaceSettingsSuccess.classList.remove('d-none');

    const submission = harness.submit();
    assert.equal(saveButton.disabled, true);
    assert.equal(elements.namespaceSettingsError.classList.contains('d-none'), true);
    assert.equal(elements.namespaceSettingsSuccess.classList.contains('d-none'), true);
    assert.equal(harness.requests.length, 1);
    const {url, options} = harness.requests[0];
    assert.equal(url, '/api/namespaces/42');
    assert.equal(options.method, 'PUT');
    assert.equal(options.headers['Content-Type'], 'application/json');
    assert.deepEqual(JSON.parse(options.body), {
        name: 'New namespace',
        description: '  Current description\nwith details  ',
    });

    finishRequest(response({name: 'Saved namespace', description: 'Saved description'}));
    await submission;
    assert.equal(elements.namespaceName.value, 'Saved namespace');
    assert.equal(elements.namespaceDescription.value, 'Saved description');
    assert.equal(elements.namespaceDisplayName.textContent, 'Saved namespace');
    assert.equal(elements.namespaceDisplayDescription.textContent, 'Saved description');
    assert.equal(elements.namespaceDisplayDescription.hidden, false);
    assert.equal(harness.document.title, 'Saved namespace - Namespace Panel');
    assert.equal(elements.namespaceSettingsSuccess.textContent, 'Namespace settings saved successfully');
    assert.equal(elements.namespaceSettingsSuccess.classList.contains('d-none'), false);
    assert.equal(elements.namespaceSettingsError.classList.contains('d-none'), true);
    assert.equal(saveButton.disabled, false);
});

test('clearing the description sends null and hides the previous description', async () => {
    const harness = load(() => response({name: 'Original name', description: null}));
    harness.elements.namespaceDescription.value = '';

    await harness.submit();

    assert.deepEqual(JSON.parse(harness.requests[0].options.body), {name: 'Original name', description: null});
    assert.equal(harness.elements.namespaceDescription.value, '');
    assert.equal(harness.elements.namespaceDisplayDescription.textContent, '');
    assert.equal(harness.elements.namespaceDisplayDescription.hidden, true);
    assert.equal(harness.elements.namespaceSettingsSuccess.classList.contains('d-none'), false);
    assert.equal(harness.saveButton.disabled, false);
});

for (const [kind, fetchResponse, message] of [
    ['server rejection', () => response({error: 'Name is already in use'}, false), 'Name is already in use'],
    ['network error', () => { throw new Error('Network unavailable'); }, 'Network unavailable'],
]) {
    test(`${kind} shows an error and preserves unsaved details for retry`, async () => {
        const harness = load(fetchResponse);
        const {elements} = harness;
        elements.namespaceName.value = '  Unsaved name  ';
        elements.namespaceDescription.value = 'Unsaved description';

        await harness.submit();

        assert.equal(elements.namespaceSettingsError.textContent, message);
        assert.equal(elements.namespaceSettingsError.classList.contains('d-none'), false);
        assert.equal(elements.namespaceSettingsSuccess.classList.contains('d-none'), true);
        assert.equal(harness.saveButton.disabled, false);
        assert.equal(elements.namespaceName.value, '  Unsaved name  ');
        assert.equal(elements.namespaceDescription.value, 'Unsaved description');
        assert.equal(elements.namespaceDisplayName.textContent, 'Original name');
        assert.equal(elements.namespaceDisplayDescription.textContent, 'Original description');
        assert.equal(harness.document.title, 'Original name - Namespace Panel');
    });
}

test('a whitespace-only name shows validation feedback without sending a request', async () => {
    const harness = load(() => { throw new Error('Unexpected request'); });
    harness.elements.namespaceName.value = ' \t\n ';
    harness.elements.namespaceSettingsSuccess.classList.remove('d-none');

    await harness.submit();

    assert.equal(harness.requests.length, 0);
    assert.equal(harness.elements.namespaceSettingsError.textContent, 'Namespace name is required');
    assert.equal(harness.elements.namespaceSettingsError.classList.contains('d-none'), false);
    assert.equal(harness.elements.namespaceSettingsSuccess.classList.contains('d-none'), true);
    assert.equal(harness.elements.namespaceName.focused, true);
    assert.equal(harness.saveButton.disabled, false);
});
