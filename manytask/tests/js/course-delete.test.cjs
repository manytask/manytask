const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const path = require('node:path');
const {test} = require('node:test');
const vm = require('node:vm');

const source = readFileSync(path.join(__dirname, '../../manytask/static/js/course-delete.js'), 'utf8');

function load(fetchResponse) {
    const elements = Object.fromEntries([
        'deleteCourseForm', 'delete-course-name', 'deleteCourseError',
        'delete-course-submit', 'deleteCourseModal',
    ].map(id => {
        const classes = new Set(['d-none']);
        return [id, {
            value: '', disabled: false, textContent: '', handlers: {},
            classList: {
                add: name => classes.add(name),
                remove: name => classes.delete(name),
                contains: name => classes.has(name),
            },
            addEventListener(event, handler) { this.handlers[event] = handler; },
            focus() {},
        }];
    }));
    const form = elements.deleteCourseForm;
    const nameInput = elements['delete-course-name'];
    nameInput.dataset = {courseName: 'Test course'};
    form.action = '/instance_admin/courses/Test%20course/delete';
    const requests = [];
    const redirects = [];
    vm.runInNewContext(source, {
        document: {getElementById: id => elements[id]},
        FormData: class {
            constructor(submittedForm) {
                assert.equal(submittedForm, form);
                assert.equal(nameInput.disabled, false);
                this.confirmation_name = nameInput.value;
                this.csrf_token = 'test-csrf-token';
            }
        },
        fetch: async (url, options) => {
            requests.push({url, options});
            return fetchResponse();
        },
        window: {location: {assign: url => redirects.push(url)}},
    });
    return {
        elements, requests, redirects,
        open() { elements.deleteCourseModal.handlers['show.bs.modal'](); },
        type(name) { nameInput.value = name; nameInput.handlers.input(); },
        submit() { return form.handlers.submit({preventDefault() {}}); },
    };
}

test('course deletion submits confirmation and CSRF once, then redirects on success', async () => {
    let finish;
    const harness = load(() => new Promise(resolve => { finish = resolve; }));
    harness.open();
    harness.type('Test course');
    const submission = harness.submit();
    await harness.submit();
    assert.equal(harness.requests.length, 1);
    assert.equal(harness.elements['delete-course-submit'].disabled, true);
    assert.equal(harness.elements['delete-course-name'].disabled, true);
    const {url, options} = harness.requests[0];
    assert.equal(url, '/instance_admin/courses/Test%20course/delete');
    assert.equal(options.method, 'POST');
    assert.equal(options.body.confirmation_name, 'Test course');
    assert.equal(options.body.csrf_token, 'test-csrf-token');
    assert.deepEqual(harness.redirects, []);
    finish({ok: true, json: async () => ({redirect_url: '/'})});
    await submission;
    assert.deepEqual(harness.redirects, ['/']);
});

for (const [label, response, message] of [
    ['registered users', () => ({ok: false, json: async () => ({
        error: 'Cannot delete this course because users are already registered.',
    })}), 'Cannot delete this course because users are already registered.'],
    ['HTML error response', () => ({ok: false, json: async () => { throw new Error('Not JSON'); }}),
        'Failed to delete course. Please try again.'],
    ['expired login redirect', () => ({ok: true, json: async () => { throw new Error('Login page'); }}),
        'Failed to delete course. Please try again.'],
    ['network failure', () => { throw new Error('Disconnected'); },
        'Failed to delete course. Please try again.'],
]) {
    test(`${label} stays in the modal and allows retry`, async () => {
        const harness = load(response);
        harness.open();
        harness.type('Test course');
        await harness.submit();
        assert.equal(harness.elements.deleteCourseError.textContent, message);
        assert.equal(harness.elements.deleteCourseError.classList.contains('d-none'), false);
        assert.equal(harness.elements['delete-course-submit'].disabled, false);
        assert.equal(harness.elements['delete-course-name'].value, 'Test course');
        assert.equal(harness.elements['delete-course-name'].disabled, false);
        assert.deepEqual(harness.redirects, []);
        harness.open();
        assert.equal(harness.elements.deleteCourseError.classList.contains('d-none'), true);
        assert.equal(harness.elements['delete-course-name'].value, '');
        assert.equal(harness.elements['delete-course-submit'].disabled, true);
    });
}
