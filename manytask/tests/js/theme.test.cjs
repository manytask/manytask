const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const path = require('node:path');
const {test} = require('node:test');
const vm = require('node:vm');

const template = readFileSync(path.join(__dirname, '../../manytask/templates/base.html'), 'utf8');
const script = template.match(/<script>([\s\S]*?)<\/script>/);

function load({storedTheme = null, dark = false, blockedStorage = false} = {}) {
    const root = {style: {}, setAttribute(name, value) { this[name] = value; }};
    const documentReady = new EventTarget();
    const systemTheme = new EventTarget();
    systemTheme.matches = dark;
    const toggles = ['light', 'dark', 'auto'].map(theme => {
        const toggle = new EventTarget();
        toggle.getAttribute = () => theme;
        return toggle;
    });
    vm.runInNewContext(script[1], {
        document: {
            documentElement: root,
            querySelector: () => null,
            querySelectorAll: () => toggles,
        },
        window: {
            matchMedia: () => systemTheme,
            addEventListener: documentReady.addEventListener.bind(documentReady),
        },
        localStorage: {
            getItem() {
                if (blockedStorage) throw new Error('Storage blocked');
                return storedTheme;
            },
            setItem(key, value) {
                if (blockedStorage) throw new Error('Storage blocked');
                storedTheme = value;
            },
        },
    });
    return {root, documentReady, systemTheme, toggles};
}

test('applies the theme in the head before any stylesheet or page content', () => {
    assert.ok(script.index > template.indexOf('<head>'));
    assert.ok(script.index < template.indexOf('<link'));
    assert.ok(script.index < template.indexOf('<body>'));
    const {root} = load({storedTheme: 'dark'});
    assert.equal(root['data-bs-theme'], 'dark');
    assert.equal(root.style.colorScheme, 'dark');
});

test('saved light and dark choices override the system preference', () => {
    for (const storedTheme of ['light', 'dark']) {
        const {root, systemTheme} = load({storedTheme, dark: storedTheme === 'light'});
        assert.equal(root['data-bs-theme'], storedTheme);
        systemTheme.dispatchEvent(new Event('change'));
        assert.equal(root['data-bs-theme'], storedTheme);
    }
});

test('automatic, missing, and invalid preferences follow system changes', () => {
    for (const storedTheme of ['auto', null, 'invalid']) {
        const {root, systemTheme} = load({storedTheme, dark: true});
        assert.equal(root['data-bs-theme'], 'dark');
        systemTheme.matches = false;
        systemTheme.dispatchEvent(new Event('change'));
        assert.equal(root['data-bs-theme'], 'light');
        assert.equal(root.style.colorScheme, 'light');
    }
});

test('theme controls work after the DOM loads and persist the choice', () => {
    const {root, documentReady, toggles, systemTheme} = load();
    documentReady.dispatchEvent(new Event('DOMContentLoaded'));
    toggles[1].dispatchEvent(new Event('click'));
    assert.equal(root['data-bs-theme'], 'dark');
    systemTheme.dispatchEvent(new Event('change'));
    assert.equal(root['data-bs-theme'], 'dark');
    toggles[0].dispatchEvent(new Event('click'));
    assert.equal(root['data-bs-theme'], 'light');
});

test('blocked storage still allows initial dark mode and manual switching', () => {
    const {root, documentReady, toggles} = load({dark: true, blockedStorage: true});
    assert.equal(root['data-bs-theme'], 'dark');
    documentReady.dispatchEvent(new Event('DOMContentLoaded'));
    toggles[0].dispatchEvent(new Event('click'));
    assert.equal(root['data-bs-theme'], 'light');
});
