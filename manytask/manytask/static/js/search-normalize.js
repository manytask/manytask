/**
 * Shared transliteration-aware search normalization.
 *
 * Normalizes a string to a common Latin, lower-case form so that substring
 * matching works across scripts: typing "Ivan" matches "Иван" and typing
 * "Иван" also matches "Ivan". Used by the table search boxes on the course
 * database page and the courses list page.
 *
 * Usage:
 *   if (normalizeForSearch(value).includes(normalizeForSearch(term))) { ... }
 */
const CYRILLIC_TO_LATIN = {
    'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'e','ж':'zh',
    'з':'z','и':'i','й':'i','к':'k','л':'l','м':'m','н':'n','о':'o',
    'п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f','х':'h','ц':'c',
    'ч':'ch','ш':'sh','щ':'sch','ъ':'','ы':'y','ь':'','э':'e','ю':'yu',
    'я':'ya',
    // Ukrainian / Belarusian extras
    'ї':'i','і':'i','є':'e','ґ':'g','ў':'u'
};

/**
 * Normalize a string for transliteration-aware substring search.
 *
 * @param {string} str The raw string (may be null/undefined/empty).
 * @returns {string} Lower-cased, transliterated form (empty string for falsy input).
 */
function normalizeForSearch(str) {
    if (!str) return "";
    const lower = str.toLowerCase();
    let out = "";
    for (let i = 0; i < lower.length; i++) {
        const ch = lower[i];
        out += Object.prototype.hasOwnProperty.call(CYRILLIC_TO_LATIN, ch)
            ? CYRILLIC_TO_LATIN[ch]
            : ch;
    }
    return out;
}
