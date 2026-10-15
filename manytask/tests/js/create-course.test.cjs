const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const path = require('node:path');
const {test} = require('node:test');
const vm = require('node:vm');

const template = readFileSync(path.join(__dirname, '../../manytask/templates/create_course.html'), 'utf8');
const source = template.match(/<script>([\s\S]*?)<\/script>/)[1];

function element(value = '') {
    const target = new EventTarget();
    const classes = new Set();
    Object.assign(target, {
        value,
        style: {},
        classList: {
            add: name => classes.add(name),
            remove: name => classes.delete(name),
            contains: name => classes.has(name),
        },
        appendChild(child) {
            child.parentElement = this;
            if (child.selected) this.value = String(child.value);
        },
        parentElement: {appendChild() {}},
    });
    let selected = false;
    Object.defineProperty(target, 'selected', {
        get: () => selected,
        set(value) {
            selected = value;
            if (value && 'value' in target.parentElement) target.parentElement.value = String(target.value);
        },
    });
    return target;
}

async function load({rms = 'gitlab', namespaces = [{id: 1, name: 'HSE', slug: 'hse', gitlab_group_path: 'hse'}]} = {}) {
    const ids = [
        'course_group', 'course_public_repo', 'course_students_group', 'namespace_id',
        'namespace-error', 'public-repo-feedback', 'students-group-feedback',
    ];
    const fields = Object.fromEntries(ids.map(id => [id, element()]));
    const form = element();
    form.checkValidity = () => true;
    form.querySelectorAll = () => Object.values(fields).filter(field => field.classList.contains('is-invalid'));
    const document = new EventTarget();
    Object.assign(document, {
        getElementById: id => fields[id],
        querySelector: () => form,
        querySelectorAll: () => [form],
        createElement: () => element(),
    });
    const context = vm.createContext({
        document,
        window: {location: {search: ''}},
        URLSearchParams,
        console: {log() {}, error() {}},
        fetch: async () => ({status: 200, ok: true, json: async () => ({namespaces})}),
    });
    vm.runInContext(source.replace("{{ 'true' if rms == 'sourcecraft' else 'false' }}", String(rms === 'sourcecraft')), context);
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(resolve => setImmediate(resolve));
    return {
        fields,
        input(id, value, event = 'input') {
            fields[id].value = value;
            fields[id].dispatchEvent(new Event(event));
        },
        submit() {
            const event = new Event('submit', {cancelable: true});
            form.dispatchEvent(event);
            return !event.defaultPrevented;
        },
    };
}

for (const group of ['os', 'hse/os']) {
    test(`accepts repository paths under the GitLab course group ${group}`, async () => {
        const page = await load();
        page.input('course_group', group);
        page.input('course_public_repo', 'hse/os/public-2026-2027');
        page.input('course_students_group', 'hse/os/students-2026-2027');
        assert.equal(page.submit(), true);
        assert.equal(page.fields.course_public_repo.classList.contains('is-invalid'), false);
        assert.equal(page.fields.course_students_group.classList.contains('is-invalid'), false);
    });
}

test('generated GitLab paths pass validation for nested namespaces and no namespace', async () => {
    for (const [namespacePath, group, expected] of [
        ['hse', 'os', 'hse/os'],
        ['hse', 'hse/os', 'hse/os'],
        ['university/hse', 'os', 'university/hse/os'],
        [null, 'os', 'os'],
        [null, 'hse/os', 'hse/os'],
    ]) {
        const page = await load({namespaces: namespacePath ? [{id: 1, gitlab_group_path: namespacePath}] : []});
        page.input('course_group', group);
        assert.ok(page.fields.course_public_repo.value.startsWith(`${expected}/public-`));
        assert.ok(page.fields.course_students_group.value.startsWith(`${expected}/students-`));
        assert.equal(page.submit(), true, `${namespacePath}: ${group}`);
    }
});

test('rejects paths outside the course group and paths with only a matching name prefix', async () => {
    const page = await load();
    page.input('course_group', 'hse/os');
    for (const prefix of ['hse', 'other/os', 'hse/os-extra']) {
        page.input('course_public_repo', `${prefix}/public`);
        page.input('course_students_group', `${prefix}/students`);
        assert.equal(page.submit(), false, prefix);
    }
});

test('changing the group revalidates edited paths and clears stale errors', async () => {
    const page = await load();
    page.input('course_group', 'os');
    page.input('course_public_repo', 'hse/math/public');
    page.input('course_students_group', 'hse/math/students');
    assert.equal(page.submit(), false);
    page.input('course_group', 'math');
    assert.equal(page.fields.course_public_repo.classList.contains('is-invalid'), false);
    assert.equal(page.fields.course_students_group.classList.contains('is-invalid'), false);
    assert.equal(page.submit(), true);
});

test('changing namespace revalidates edited paths without overwriting them', async () => {
    const page = await load({namespaces: [
        {id: 1, gitlab_group_path: 'hse'},
        {id: 2, gitlab_group_path: 'other'},
    ]});
    page.input('course_group', 'os');
    page.input('course_public_repo', 'hse/os/public');
    page.input('course_students_group', 'hse/os/students');
    assert.equal(page.submit(), true);
    page.input('namespace_id', '2', 'change');
    assert.equal(page.fields.course_public_repo.classList.contains('is-invalid'), true);
    assert.equal(page.fields.course_students_group.classList.contains('is-invalid'), true);
    assert.equal(page.fields.course_public_repo.value, 'hse/os/public');
    page.input('namespace_id', '1', 'change');
    assert.equal(page.submit(), true);
});

test('SourceCraft continues to use course prefixes instead of namespace paths', async () => {
    const page = await load({rms: 'sourcecraft'});
    page.input('course_group', 'os');
    assert.ok(page.fields.course_public_repo.value.startsWith('os-public-'));
    assert.ok(page.fields.course_students_group.value.startsWith('os-st-'));
    assert.equal(page.submit(), true);
    page.input('course_public_repo', 'other-public');
    assert.equal(page.submit(), false);
});
