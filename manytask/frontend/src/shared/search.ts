/** Search rules ported from static/js/search-normalize.js. */
const CYRILLIC_TO_LATIN: Record<string, string> = {
  'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'e','ж':'zh',
  'з':'z','и':'i','й':'i','к':'k','л':'l','м':'m','н':'n','о':'o',
  'п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f','х':'h','ц':'c',
  'ч':'ch','ш':'sh','щ':'sch','ъ':'','ы':'y','ь':'','э':'e','ю':'yu',
  'я':'ya',
  'ї':'i','і':'i','є':'e','ґ':'g','ў':'u',
};

const QWERTY_TO_YTSUKEN = new Map<string, string>([
  ['q','й'],['w','ц'],['e','у'],['r','к'],['t','е'],['y','н'],['u','г'],['i','ш'],
  ['o','щ'],['p','з'],['[','х'],[']','ъ'],
  ['a','ф'],['s','ы'],['d','в'],['f','а'],['g','п'],['h','р'],['j','о'],['k','л'],
  ['l','д'],[';','ж'],["'",'э'],
  ['z','я'],['x','ч'],['c','с'],['v','м'],['b','и'],['n','т'],['m','ь'],
  [',','б'],['.','ю'],['/','.'],['`','ё'],
]);

const YTSUKEN_TO_QWERTY = new Map<string, string>(
  Array.from(QWERTY_TO_YTSUKEN, ([latin, cyrillic]) => [cyrillic, latin]),
);
const MIN_LAYOUT_SWAP_LENGTH = 2;

function remapLayout(str: string, keyMap: Map<string, string>): string {
  let out = '';
  for (const ch of str) {
    out += keyMap.has(ch) ? keyMap.get(ch) : ch;
  }
  return out;
}

export function normalizeForSearch(str: string | null | undefined): string {
  if (!str) return '';
  const lower = str.toLowerCase();
  let out = '';
  for (let i = 0; i < lower.length; i++) {
    const ch = lower[i];
    out += Object.prototype.hasOwnProperty.call(CYRILLIC_TO_LATIN, ch)
      ? CYRILLIC_TO_LATIN[ch] : ch;
  }
  return out;
}

export function searchTermVariants(term: string): string[] {
  if (!term) return [];
  const lower = term.toLowerCase().trim();
  if (!lower) return [];
  const candidates = [lower];
  if (lower.length >= MIN_LAYOUT_SWAP_LENGTH) {
    candidates.push(remapLayout(lower, QWERTY_TO_YTSUKEN));
    candidates.push(remapLayout(lower, YTSUKEN_TO_QWERTY));
  }
  const variants: string[] = [];
  for (const candidate of candidates) {
    const normalized = normalizeForSearch(candidate);
    if (normalized && !variants.includes(normalized)) variants.push(normalized);
  }
  return variants;
}

export function matchesSearchVariants(value: string, variants: string[]): boolean {
  if (!variants || variants.length === 0) return true;
  const normalizedValue = normalizeForSearch(value);
  if (!normalizedValue) return false;
  return variants.some((variant) => normalizedValue.includes(variant));
}

export function matchesSearch(value: string, term: string): boolean {
  return matchesSearchVariants(value, searchTermVariants(term));
}
