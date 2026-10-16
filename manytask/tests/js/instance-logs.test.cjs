const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const script = fs.readFileSync(path.join(__dirname, '../../manytask/static/js/instance-logs.js'), 'utf8');

function setup(fetch) {
    const elements = Object.fromEntries(['instance-logs', 'log-source', 'log-lines', 'log-download', 'log-pause', 'log-follow', 'log-status', 'log-output'].map(id => [id, {
        textContent: '',
        value: 'general',
        checked: true,
        dataset: {url: '/instance_admin/logs/data', downloadUrl: '/instance_admin/logs/download'},
        scrollHeight: 300,
        scrollTop: 0,
        listeners: {},
        addEventListener(event, callback) { this.listeners[event] = callback; },
        setAttribute(name, value) { this[name] = value; },
    }]));
    elements['log-lines'].value = '200';
    const timers = new Map();
    let timerId = 0;
    const document = {hidden: false, getElementById: id => elements[id], addEventListener() {}};
    vm.runInNewContext(script, {
        document,
        window: {location: {origin: 'http://localhost'}, addEventListener() {}},
        fetch, URL, AbortController, Date,
        setTimeout(callback, delay) { timers.set(++timerId, {callback, delay}); return timerId; },
        clearTimeout(id) { timers.delete(id); },
    });
    return {elements, timers};
}

const settle = () => new Promise(resolve => setImmediate(resolve));
const response = content => ({ok: true, status: 200, json: async () => ({content})});

test('refreshes as text, follows, pauses, and resumes with the selected source', async () => {
    const requests = [];
    const {elements, timers} = setup(async url => {
        requests.push(url.toString());
        return response('<script>untrusted log</script>');
    });
    await settle();
    assert.equal(elements['log-output'].textContent, '<script>untrusted log</script>');
    assert.equal(elements['log-output'].scrollTop, 300);
    assert.equal([...timers.values()][0].delay, 3000);
    elements['log-pause'].listeners.click();
    assert.equal(timers.size, 0);
    elements['log-source'].value = 'access';
    elements['log-source'].listeners.change();
    await settle();
    assert.equal(requests.length, 1);
    elements['log-follow'].checked = false;
    elements['log-output'].scrollTop = 25;
    elements['log-pause'].listeners.click();
    await settle();
    assert.equal(requests.length, 2);
    assert.match(requests[1], /source=access&lines=200$/);
    assert.match(elements['log-download'].href, /\/logs\/download\?source=access$/);
    assert.equal(elements['log-output'].scrollTop, 25);
});

test('changing the line count refreshes without limiting the download', async () => {
    const requests = [];
    const {elements} = setup(async url => {
        requests.push(url.toString());
        return response('entries');
    });
    await settle();
    elements['log-lines'].value = '5000';
    elements['log-lines'].listeners.change();
    await settle();
    assert.match(requests[1], /source=general&lines=5000$/);
    assert.match(elements['log-download'].href, /download\?source=general$/);
});

test('discards a response from a previous log source', async () => {
    let release;
    let calls = 0;
    const {elements} = setup(async () => {
        calls++;
        if (calls === 1) return {ok: true, status: 200, json: () => new Promise(resolve => { release = resolve; })};
        return response('access log');
    });
    await settle();
    elements['log-source'].value = 'access';
    elements['log-source'].listeners.change();
    await settle();
    release({content: 'stale application log'});
    await settle();
    assert.equal(elements['log-output'].textContent, 'access log');
});

test('stops polling when permission is revoked or login redirects', async () => {
    for (const result of [{ok: false, status: 403}, {ok: true, redirected: true}]) {
        const {elements, timers} = setup(async () => result);
        await settle();
        assert.equal(timers.size, 0);
        assert.match(elements['log-status'].textContent, /session expired/);
        assert.equal(elements['log-pause']['aria-pressed'], 'true');
    }
});

test('retries transient failures', async () => {
    const {elements, timers} = setup(async () => { throw new Error('network down'); });
    await settle();
    assert.match(elements['log-status'].textContent, /Retrying/);
    assert.equal([...timers.values()][0].delay, 3000);
});
