import { describe, it, expect } from 'vitest';

import { buildFacetTree, FacetTreeNode } from '../utils/buildFacetTree';

describe('buildFacetTree', () => {
  it('returns empty array for empty input', () => {
    expect(buildFacetTree([])).toEqual([]);
  });

  it('builds a flat list for single-level paths', () => {
    const tree = buildFacetTree([
      { value: 'en', count: 10 },
      { value: 'es', count: 5 },
    ]);
    expect(tree).toHaveLength(2);
    expect(tree[0].label).toBe('en');
    expect(tree[0].fullPath).toBe('en');
    expect(tree[0].count).toBe(10);
    expect(tree[0].isLeaf).toBe(true);
    expect(tree[1].label).toBe('es');
  });

  it('builds a hierarchical tree from nested paths', () => {
    const tree = buildFacetTree([
      { value: 'en', count: 3 },
      { value: 'en/Science Fiction', count: 10 },
      { value: 'en/History', count: 5 },
    ]);
    expect(tree).toHaveLength(1);
    const en = tree[0];
    expect(en.label).toBe('en');
    expect(en.isLeaf).toBe(false);
    expect(en.children).toHaveLength(2);
  });

  it('propagates counts from children to parents', () => {
    const tree = buildFacetTree([
      { value: 'en', count: 3 },
      { value: 'en/Science Fiction', count: 10 },
      { value: 'en/History', count: 5 },
    ]);
    const en = tree[0];
    // parent count = own (3) + sum of children (10 + 5) = 18
    expect(en.count).toBe(18);
  });

  it('creates intermediate parent nodes when parent path is not in facets', () => {
    const tree = buildFacetTree([
      { value: 'en/Science Fiction', count: 10 },
      { value: 'en/History', count: 5 },
    ]);
    expect(tree).toHaveLength(1);
    const en = tree[0];
    expect(en.label).toBe('en');
    // Parent had no direct count — it's the sum of children
    expect(en.count).toBe(15);
    expect(en.isLeaf).toBe(false);
    expect(en.children).toHaveLength(2);
  });

  it('sorts children alphabetically at each level', () => {
    const tree = buildFacetTree([
      { value: 'en/History', count: 5 },
      { value: 'en/Biography', count: 3 },
      { value: 'en/Science Fiction', count: 10 },
    ]);
    const en = tree[0];
    expect(en.children.map((c: FacetTreeNode) => c.label)).toEqual([
      'Biography',
      'History',
      'Science Fiction',
    ]);
  });

  it('sorts root nodes alphabetically', () => {
    const tree = buildFacetTree([
      { value: 'es', count: 5 },
      { value: 'ca', count: 2 },
      { value: 'en', count: 10 },
    ]);
    expect(tree.map((n: FacetTreeNode) => n.label)).toEqual(['ca', 'en', 'es']);
  });

  it('handles deeply nested paths (3+ levels)', () => {
    const tree = buildFacetTree([
      { value: 'en/Fiction/Classics', count: 7 },
      { value: 'en/Fiction/Modern', count: 3 },
    ]);
    expect(tree).toHaveLength(1);
    const en = tree[0];
    expect(en.label).toBe('en');
    expect(en.children).toHaveLength(1);
    const fiction = en.children[0];
    expect(fiction.label).toBe('Fiction');
    expect(fiction.fullPath).toBe('en/Fiction');
    expect(fiction.children).toHaveLength(2);
    expect(fiction.count).toBe(10);
    expect(fiction.children[0].label).toBe('Classics');
    expect(fiction.children[0].fullPath).toBe('en/Fiction/Classics');
    expect(fiction.children[0].count).toBe(7);
    expect(fiction.children[0].isLeaf).toBe(true);
  });

  it('handles UTF-8 characters in folder names', () => {
    const tree = buildFacetTree([
      { value: 'es/Ciencia Ficción', count: 47 },
      { value: 'es/Historia', count: 30 },
    ]);
    const es = tree[0];
    expect(es.children[0].label).toBe('Ciencia Ficción');
    expect(es.children[0].fullPath).toBe('es/Ciencia Ficción');
    expect(es.children[0].count).toBe(47);
  });

  it('handles single path correctly', () => {
    const tree = buildFacetTree([{ value: 'en/Science Fiction', count: 10 }]);
    expect(tree).toHaveLength(1);
    const en = tree[0];
    expect(en.label).toBe('en');
    expect(en.count).toBe(10);
    expect(en.children).toHaveLength(1);
    expect(en.children[0].label).toBe('Science Fiction');
  });

  it('correctly marks leaf vs non-leaf nodes', () => {
    const tree = buildFacetTree([
      { value: 'en', count: 2 },
      { value: 'en/Science Fiction', count: 10 },
    ]);
    expect(tree[0].isLeaf).toBe(false);
    expect(tree[0].children[0].isLeaf).toBe(true);
  });

  it('handles mixed depth paths in a real-world example', () => {
    const tree = buildFacetTree([
      { value: 'en', count: 5 },
      { value: 'en/Science Fiction', count: 125 },
      { value: 'en/History', count: 89 },
      { value: 'en/Biography', count: 67 },
      { value: 'es', count: 10 },
      { value: 'es/Ciencia Ficción', count: 98 },
      { value: 'es/Literatura', count: 67 },
    ]);

    expect(tree).toHaveLength(2);
    const en = tree[0];
    const es = tree[1];

    expect(en.label).toBe('en');
    // 5 (own) + 125 + 89 + 67 = 286
    expect(en.count).toBe(286);
    expect(en.children).toHaveLength(3);
    expect(en.children[0].label).toBe('Biography');

    expect(es.label).toBe('es');
    // 10 (own) + 98 + 67 = 175
    expect(es.count).toBe(175);
    expect(es.children).toHaveLength(2);
  });
});
