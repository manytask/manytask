import {expect, it} from 'vitest';

import {matchesSearch, matchesSearchVariants, normalizeForSearch, searchTermVariants} from './search';

it.each([['Иван', 'Ivan'], ['Иван', 'bdfy'], ['Ivan', 'шмфт']])('finds %s with %s',
  (value, query) => expect(matchesSearch(value, query)).toBe(true));

it('does not invent an unrelated match', () => expect(matchesSearch('Пётр', 'Ivan')).toBe(false));

it('keeps transliteration, blank, and one-letter layout rules', () => {
  expect(normalizeForSearch('Ёж ІЇ')).toBe('ezh ii');
  expect(searchTermVariants('  ')).toEqual([]);
  expect(searchTermVariants('i')).toEqual(['i']);
  expect(matchesSearchVariants('anything', [])).toBe(true);
});
