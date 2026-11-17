const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const path = require('node:path');
const {test} = require('node:test');
const vm = require('node:vm');

const template = readFileSync(path.join(__dirname, '../../manytask/templates/database.html'), 'utf8');
const source = template.slice(template.indexOf('let currentEditCell'), template.indexOf('function editComment('))
    .replace('{{ readonly_fields|tojson }}', '["username", "total_score"]')
    .replace('{{ is_course_admin|tojson }}', 'true')
    .replace('{{ url_for("api.update_database", course_name=course_name) }}', '/database/update');

function load() {
    const elements = {scoreInput: {value: ''}, isSolvedInput: {checked: false}, editModalLabel: {textContent: ''}};
    const requests = [];
    const modal = {show() {}, hide() { this.hidden = true; }, _element: {addEventListener() {}}};
    const harness = vm.createContext({
        document: {getElementById: id => elements[id]},
        modal,
        fetch: async (url, options) => {
            const body = JSON.parse(options.body);
            requests.push({url, body});
            return {json: async () => ({
                success: true,
                row_data: JSON.stringify({
                    ...body.row_data,
                    scores: {...body.row_data.scores, ...body.new_scores},
                    solved: {...body.row_data.solved, ...body.new_solved},
                }),
            })};
        },
    });
    vm.runInContext(source + '\neditModal = modal;', harness);
    let data = {username: 'alice', scores: {task1: 0}, solved: {task1: true}};
    const cellElement = {style: {}};
    let reformatted = false;
    const row = {
        getData: () => data,
        async update(update) {
            assert.equal(typeof update, 'object');
            data = {...data, ...update};
        },
        reformat() { reformatted = true; harness.formatTaskScore(cell); },
    };
    const cell = {
        getField: () => 'scores.task1',
        getValue: () => data.scores.task1,
        getColumn: () => ({getDefinition: () => ({title: 'task1', formatterParams: {minScore: 50}})}),
        getRow: () => row,
        getElement: () => cellElement,
    };
    return {harness, elements, requests, modal, row, cell, cellElement, wasReformatted: () => reformatted};
}

test('opening the score editor reads the stored flag and resets the checkbox for each task', () => {
    const {harness, elements, row, cell} = load();
    harness.editCell(cell);
    assert.equal(elements.scoreInput.value, 0);
    assert.equal(elements.isSolvedInput.checked, true);
    row.getData().solved.task1 = false;
    harness.editCell(cell);
    assert.equal(elements.isSolvedInput.checked, false);
    elements.isSolvedInput.checked = true;
    delete row.getData().solved;
    harness.editCell(cell);
    assert.equal(elements.isSolvedInput.checked, false);
});

test('bold styling follows solved status even at zero points and is removed when cleared', () => {
    const {harness, row, cell, cellElement} = load();
    assert.equal(harness.formatTaskScore(cell), 0);
    assert.equal(cellElement.style.fontWeight, 'bold');
    row.getData().solved.task1 = false;
    row.getData().scores.task1 = 100;
    assert.equal(harness.formatTaskScore(cell), 100);
    assert.equal(cellElement.style.fontWeight, 'normal');
    delete row.getData().scores.task1;
    assert.equal(harness.formatTaskScore(cell), '');
});

test('editing points checks completion at min_score and clears it below the threshold', () => {
    const {harness, elements, cell} = load();
    harness.editCell(cell);
    for (const [score, expected] of [[49, false], [50, true], [100, true], [0, false]]) {
        elements.scoreInput.value = String(score);
        elements.scoreInput.oninput();
        assert.equal(elements.isSolvedInput.checked, expected);
    }
});

for (const isSolved of [true, false]) {
    test(`saving solved=${isSolved} sends the checkbox and refreshes styling without changing points`, async () => {
        const {harness, elements, requests, modal, row, cell, cellElement, wasReformatted} = load();
        row.getData().solved.task1 = !isSolved;
        harness.editCell(cell);
        elements.isSolvedInput.checked = isSolved;
        await harness.saveChanges();
        assert.equal(requests.length, 1);
        assert.deepEqual(requests[0].body.new_scores, {task1: 0});
        assert.deepEqual(requests[0].body.new_solved, {task1: isSolved});
        assert.equal(row.getData().solved.task1, isSolved);
        assert.equal(wasReformatted(), true);
        assert.equal(cellElement.style.fontWeight, isSolved ? 'bold' : 'normal');
        assert.equal(modal.hidden, true);
        harness.editCell(cell);
        assert.equal(elements.isSolvedInput.checked, isSolved);
    });
}
