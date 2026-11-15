import { parseOfficeList } from './parseOfficeList';

describe('parseOfficeList', () => {
  it('reads tab-separated code and name with indentation depth', () => {
    const text = 'SVC1\tService One\n\tDIV1\tDivision One\n\t\tU1\tUnit\n\nSVC2\tService Two';
    expect(parseOfficeList(text)).toEqual([
      { line: 1, code: 'SVC1', name: 'Service One', depth: 0 },
      { line: 2, code: 'DIV1', name: 'Division One', depth: 1 },
      { line: 3, code: 'U1', name: 'Unit', depth: 2 },
      { line: 5, code: 'SVC2', name: 'Service Two', depth: 0 },
    ]);
  });

  it('uses two spaces per level and other separators', () => {
    expect(parseOfficeList('A - Alpha\n  B, Beta')).toEqual([
      { line: 1, code: 'A', name: 'Alpha', depth: 0 },
      { line: 2, code: 'B', name: 'Beta', depth: 1 },
    ]);
  });

  it('takes a parent-code column', () => {
    expect(parseOfficeList('PC1\tCenter\tSVC2\r\nPC2\tCenter 2\t\t')).toEqual([
      { line: 1, code: 'PC1', name: 'Center', depth: 0, parent_code: 'SVC2' },
      { line: 2, code: 'PC2', name: 'Center 2', depth: 0 },
    ]);
  });

  it('keeps incomplete lines so the server can report them', () => {
    expect(parseOfficeList('ONLYCODE')).toEqual([
      { line: 1, code: 'ONLYCODE', name: '', depth: 0 },
    ]);
  });
});
