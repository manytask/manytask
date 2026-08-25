/**
 * Shared transliteration- and keyboard-layout-aware search normalization.
 *
 * Two problems are solved here:
 *
 * 1. Script mismatch. Values are normalized to a common Latin, lower-case form
 *    so that substring matching works across scripts: typing "Ivan" matches
 *    "Иван" and typing "Иван" also matches "Ivan".
 *
 * 2. Wrong keyboard layout. A user with the Russian ЙЦУКЕН layout active who
 *    types the letters of "Ivan" actually produces "шмфт"; a user with the
 *    English QWERTY layout active who types "Иван" produces "bdfy". Both are
 *    re-interpreted by mapping the typed characters back through the physical
 *    key positions of the other layout. Only these two layouts are supported.
 *
 * Usage (single field):
 *   if (matchesSearch(value, term)) { ... }
 *
 * Usage (several fields against the same term — compute variants once):
 *   const variants = searchTermVariants(term);
 *   if (matchesSearchVariants(a, variants) || matchesSearchVariants(b, variants)) { ... }
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
 * Physical key positions: QWERTY character -> Russian ЙЦУКЕН character
 * produced by the same key. Lower-case/unshifted keys only, which is all the
 * search needs since everything is lower-cased before matching.
 */
const QWERTY_TO_YTSUKEN = {
    'q':'й','w':'ц','e':'у','r':'к','t':'е','y':'н','u':'г','i':'ш',
    'o':'щ','p':'з','[':'х',']':'ъ',
    'a':'ф','s':'ы','d':'в','f':'а','g':'п','h':'р','j':'о','k':'л',
    'l':'д',';':'ж','\'':'э',
    'z':'я','x':'ч','c':'с','v':'м','b':'и','n':'т','m':'ь',
    ',':'б','.':'ю','/':'.','`':'ё'
};

/** Inverse of QWERTY_TO_YTSUKEN: ЙЦУКЕН character -> QWERTY character. */
const YTSUKEN_TO_QWERTY = (() => {
    const inverse = {};
    for (const [latin, cyrillic] of Object.entries(QWERTY_TO_YTSUKEN)) {
        inverse[cyrillic] = latin;
    }
    return inverse;
})();

/**
 * Terms shorter than this are not expanded into wrong-layout variants: a
 * one-character term maps to some other single letter in the other layout and
 * would match almost anything, drowning the real results in noise.
 */
const MIN_LAYOUT_SWAP_LENGTH = 2;

/**
 * Re-type a string through the given physical key map.
 *
 * Characters absent from the map (digits, spaces, punctuation shared by both
 * layouts) are kept as-is.
 *
 * @param {string} str Lower-cased input.
 * @param {Object<string, string>} keyMap Character-to-character key mapping.
 * @returns {string} The string as it would have been typed on the other layout.
 */
function remapLayout(str, keyMap) {
    let out = "";
    for (const ch of str) {
        out += Object.prototype.hasOwnProperty.call(keyMap, ch) ? keyMap[ch] : ch;
    }
    return out;
}

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

/**
 * Build the list of normalized forms a search term may take.
 *
 * Returns the normalized term itself plus, when the term is long enough, the
 * normalized forms of the term re-typed through the other keyboard layout in
 * both directions. Duplicates and empty strings are dropped, so a plain ASCII
 * term usually yields a single variant.
 *
 * @param {string} term The raw search term (may be null/undefined/empty).
 * @returns {string[]} Normalized variants; empty array when the term is blank.
 */
function searchTermVariants(term) {
    if (!term) return [];
    const lower = term.toLowerCase().trim();
    if (!lower) return [];

    const candidates = [lower];
    if (lower.length >= MIN_LAYOUT_SWAP_LENGTH) {
        candidates.push(remapLayout(lower, QWERTY_TO_YTSUKEN));
        candidates.push(remapLayout(lower, YTSUKEN_TO_QWERTY));
    }

    const variants = [];
    for (const candidate of candidates) {
        const normalized = normalizeForSearch(candidate);
        if (normalized && !variants.includes(normalized)) {
            variants.push(normalized);
        }
    }
    return variants;
}

/**
 * Test a value against pre-computed term variants from searchTermVariants().
 *
 * Use this when matching several fields against one term to avoid rebuilding
 * the variants for every field.
 *
 * @param {string} value The value to search in (may be null/undefined/empty).
 * @param {string[]} variants Normalized variants of the search term.
 * @returns {boolean} True if any variant is a substring of the value.
 */
function matchesSearchVariants(value, variants) {
    if (!variants || variants.length === 0) return true;
    const normalizedValue = normalizeForSearch(value);
    if (!normalizedValue) return false;
    return variants.some((variant) => normalizedValue.includes(variant));
}

/**
 * Transliteration- and layout-aware substring match.
 *
 * @param {string} value The value to search in (may be null/undefined/empty).
 * @param {string} term The raw search term; a blank term matches everything.
 * @returns {boolean} True if the term matches the value.
 */
function matchesSearch(value, term) {
    return matchesSearchVariants(value, searchTermVariants(term));
}
