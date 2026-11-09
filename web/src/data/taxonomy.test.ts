import { describe, expect, it } from 'vitest';
import { classification } from '../test-utils';
import { buildTaxonomy } from './taxonomy';

describe('buildTaxonomy', () => {
  const taxonomy = buildTaxonomy(classification([]));

  it('路径从一级写到该节点', () => {
    expect(taxonomy.path(0)).toEqual(['开发']);
    expect(taxonomy.path(2)).toEqual(['开发', '工具', '命令行']);
    expect(taxonomy.path(5)).toEqual(['人工智能', '智能体']);
  });

  it('越界的下标不抛错', () => {
    expect(taxonomy.path(99)).toEqual([]);
    expect(taxonomy.label(99)).toBe('');
    expect(taxonomy.formLabel(99)).toBe('');
  });

  it('形态与节点名称', () => {
    expect(taxonomy.formLabel(1)).toBe('库');
    expect(taxonomy.label(3)).toBe('编辑器');
  });
});
