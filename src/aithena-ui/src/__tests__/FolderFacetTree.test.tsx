import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';

import FolderFacetTree from '../Components/FolderFacetTree';
import { FacetTreeNode } from '../utils/buildFacetTree';
import { IntlWrapper } from './test-intl-wrapper';

function makeTree(): FacetTreeNode[] {
  return [
    {
      label: 'en',
      fullPath: 'en',
      count: 286,
      isLeaf: false,
      children: [
        {
          label: 'Biography',
          fullPath: 'en/Biography',
          count: 67,
          isLeaf: true,
          children: [],
        },
        {
          label: 'History',
          fullPath: 'en/History',
          count: 89,
          isLeaf: true,
          children: [],
        },
        {
          label: 'Science Fiction',
          fullPath: 'en/Science Fiction',
          count: 125,
          isLeaf: true,
          children: [],
        },
      ],
    },
    {
      label: 'es',
      fullPath: 'es',
      count: 175,
      isLeaf: false,
      children: [
        {
          label: 'Ciencia Ficción',
          fullPath: 'es/Ciencia Ficción',
          count: 98,
          isLeaf: true,
          children: [],
        },
        {
          label: 'Literatura',
          fullPath: 'es/Literatura',
          count: 67,
          isLeaf: true,
          children: [],
        },
      ],
    },
  ];
}

describe('FolderFacetTree', () => {
  it('renders root nodes with counts', () => {
    render(
      <IntlWrapper>
        <FolderFacetTree roots={makeTree()} selectedPaths={new Set()} onTogglePath={vi.fn()} />
      </IntlWrapper>
    );

    expect(screen.getByText('en')).toBeInTheDocument();
    expect(screen.getByText('(286)')).toBeInTheDocument();
    expect(screen.getByText('es')).toBeInTheDocument();
    expect(screen.getByText('(175)')).toBeInTheDocument();
  });

  it('renders the folder group title', () => {
    render(
      <IntlWrapper>
        <FolderFacetTree roots={makeTree()} selectedPaths={new Set()} onTogglePath={vi.fn()} />
      </IntlWrapper>
    );

    expect(screen.getByText('Folder')).toBeInTheDocument();
  });

  it('does not render children until expanded', () => {
    render(
      <IntlWrapper>
        <FolderFacetTree roots={makeTree()} selectedPaths={new Set()} onTogglePath={vi.fn()} />
      </IntlWrapper>
    );

    expect(screen.queryByText('Science Fiction')).not.toBeInTheDocument();
    expect(screen.queryByText('History')).not.toBeInTheDocument();
  });

  it('expands a node on toggle click and shows children', async () => {
    const user = userEvent.setup();
    render(
      <IntlWrapper>
        <FolderFacetTree roots={makeTree()} selectedPaths={new Set()} onTogglePath={vi.fn()} />
      </IntlWrapper>
    );

    // Click the expand toggle on the "en" node
    const enItem = screen.getByText('en').closest('.folder-tree-row')!;
    const toggle = enItem.querySelector('.folder-tree-toggle') as HTMLElement;
    await user.click(toggle);

    expect(screen.getByText('Science Fiction')).toBeInTheDocument();
    expect(screen.getByText('History')).toBeInTheDocument();
    expect(screen.getByText('Biography')).toBeInTheDocument();
    expect(screen.getByText('(125)')).toBeInTheDocument();
  });

  it('collapses an expanded node on second toggle click', async () => {
    const user = userEvent.setup();
    render(
      <IntlWrapper>
        <FolderFacetTree roots={makeTree()} selectedPaths={new Set()} onTogglePath={vi.fn()} />
      </IntlWrapper>
    );

    const enItem = screen.getByText('en').closest('.folder-tree-row')!;
    const toggle = enItem.querySelector('.folder-tree-toggle') as HTMLElement;
    await user.click(toggle);
    expect(screen.getByText('Science Fiction')).toBeInTheDocument();

    await user.click(toggle);
    expect(screen.queryByText('Science Fiction')).not.toBeInTheDocument();
  });

  it('calls onTogglePath when a row is clicked', async () => {
    const onTogglePath = vi.fn();
    const user = userEvent.setup();
    render(
      <IntlWrapper>
        <FolderFacetTree roots={makeTree()} selectedPaths={new Set()} onTogglePath={onTogglePath} />
      </IntlWrapper>
    );

    await user.click(screen.getByText('en'));
    expect(onTogglePath).toHaveBeenCalledWith('en');
  });

  it('calls onTogglePath when a child row is clicked', async () => {
    const onTogglePath = vi.fn();
    const user = userEvent.setup();
    render(
      <IntlWrapper>
        <FolderFacetTree roots={makeTree()} selectedPaths={new Set()} onTogglePath={onTogglePath} />
      </IntlWrapper>
    );

    // Expand en first
    const enItem = screen.getByText('en').closest('.folder-tree-row')!;
    const toggle = enItem.querySelector('.folder-tree-toggle') as HTMLElement;
    await user.click(toggle);

    await user.click(screen.getByText('Science Fiction'));
    expect(onTogglePath).toHaveBeenCalledWith('en/Science Fiction');
  });

  it('highlights selected paths', () => {
    render(
      <IntlWrapper>
        <FolderFacetTree
          roots={makeTree()}
          selectedPaths={new Set(['en'])}
          onTogglePath={vi.fn()}
        />
      </IntlWrapper>
    );

    const enRow = screen.getByText('en').closest('.folder-tree-row')!;
    expect(enRow.classList.contains('folder-tree-row--selected')).toBe(true);

    const esRow = screen.getByText('es').closest('.folder-tree-row')!;
    expect(esRow.classList.contains('folder-tree-row--selected')).toBe(false);
  });

  it('returns null when roots is empty', () => {
    const { container } = render(
      <IntlWrapper>
        <FolderFacetTree roots={[]} selectedPaths={new Set()} onTogglePath={vi.fn()} />
      </IntlWrapper>
    );

    expect(container.querySelector('.folder-facet-group')).toBeNull();
  });

  it('has correct aria attributes on tree items', () => {
    render(
      <IntlWrapper>
        <FolderFacetTree
          roots={makeTree()}
          selectedPaths={new Set(['en'])}
          onTogglePath={vi.fn()}
        />
      </IntlWrapper>
    );

    const tree = screen.getByRole('tree');
    expect(tree).toBeInTheDocument();

    const treeItems = screen.getAllByRole('treeitem');
    expect(treeItems.length).toBeGreaterThan(0);

    // "en" has children and is collapsed by default
    const enTreeItem = treeItems.find((item) => within(item).queryByText('en'))!;
    expect(enTreeItem).toHaveAttribute('aria-expanded', 'false');
    expect(enTreeItem).toHaveAttribute('aria-selected', 'true');
    expect(enTreeItem).toHaveAttribute('aria-level', '1');
  });

  it('supports keyboard expand/collapse with ArrowRight/ArrowLeft', async () => {
    const user = userEvent.setup();
    render(
      <IntlWrapper>
        <FolderFacetTree roots={makeTree()} selectedPaths={new Set()} onTogglePath={vi.fn()} />
      </IntlWrapper>
    );

    const enRow = screen.getByText('en').closest('.folder-tree-row') as HTMLElement;
    enRow.focus();

    // ArrowRight expands
    await user.keyboard('{ArrowRight}');
    expect(screen.getByText('Science Fiction')).toBeInTheDocument();

    // ArrowLeft collapses
    await user.keyboard('{ArrowLeft}');
    expect(screen.queryByText('Science Fiction')).not.toBeInTheDocument();
  });

  it('supports keyboard selection with Enter', async () => {
    const onTogglePath = vi.fn();
    const user = userEvent.setup();
    render(
      <IntlWrapper>
        <FolderFacetTree roots={makeTree()} selectedPaths={new Set()} onTogglePath={onTogglePath} />
      </IntlWrapper>
    );

    const enRow = screen.getByText('en').closest('.folder-tree-row') as HTMLElement;
    enRow.focus();

    await user.keyboard('{Enter}');
    expect(onTogglePath).toHaveBeenCalledWith('en');
  });

  it('supports keyboard selection with Space', async () => {
    const onTogglePath = vi.fn();
    const user = userEvent.setup();
    render(
      <IntlWrapper>
        <FolderFacetTree roots={makeTree()} selectedPaths={new Set()} onTogglePath={onTogglePath} />
      </IntlWrapper>
    );

    const esRow = screen.getByText('es').closest('.folder-tree-row') as HTMLElement;
    esRow.focus();

    await user.keyboard(' ');
    expect(onTogglePath).toHaveBeenCalledWith('es');
  });

  it('renders UTF-8 folder names correctly after expansion', async () => {
    const user = userEvent.setup();
    render(
      <IntlWrapper>
        <FolderFacetTree roots={makeTree()} selectedPaths={new Set()} onTogglePath={vi.fn()} />
      </IntlWrapper>
    );

    // Expand es
    const esItem = screen.getByText('es').closest('.folder-tree-row')!;
    const toggle = esItem.querySelector('.folder-tree-toggle') as HTMLElement;
    await user.click(toggle);

    expect(screen.getByText('Ciencia Ficción')).toBeInTheDocument();
    expect(screen.getByText('(98)')).toBeInTheDocument();
  });
});
