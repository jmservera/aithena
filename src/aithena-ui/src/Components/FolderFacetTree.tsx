import { memo, useCallback, useMemo, useState } from 'react';
import { useIntl } from 'react-intl';

import type { FacetTreeNode } from '../utils/buildFacetTree';

interface FolderFacetTreeProps {
  roots: FacetTreeNode[];
  selectedPaths: Set<string>;
  onTogglePath: (fullPath: string) => void;
}

interface TreeNodeProps {
  node: FacetTreeNode;
  level: number;
  selectedPaths: Set<string>;
  expandedPaths: Set<string>;
  onTogglePath: (fullPath: string) => void;
  onToggleExpand: (fullPath: string) => void;
}

const TreeNode = memo(function TreeNode({
  node,
  level,
  selectedPaths,
  expandedPaths,
  onTogglePath,
  onToggleExpand,
}: TreeNodeProps) {
  const isExpanded = expandedPaths.has(node.fullPath);
  const isSelected = selectedPaths.has(node.fullPath);
  const hasChildren = node.children.length > 0;

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      switch (e.key) {
        case 'ArrowRight':
          if (hasChildren && !isExpanded) {
            e.preventDefault();
            onToggleExpand(node.fullPath);
          }
          break;
        case 'ArrowLeft':
          if (hasChildren && isExpanded) {
            e.preventDefault();
            onToggleExpand(node.fullPath);
          }
          break;
        case 'Enter':
        case ' ':
          e.preventDefault();
          onTogglePath(node.fullPath);
          break;
      }
    },
    [hasChildren, isExpanded, node.fullPath, onToggleExpand, onTogglePath]
  );

  const handleExpandClick = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      onToggleExpand(node.fullPath);
    },
    [node.fullPath, onToggleExpand]
  );

  const handleSelect = useCallback(() => {
    onTogglePath(node.fullPath);
  }, [node.fullPath, onTogglePath]);

  return (
    <li
      role="treeitem"
      aria-expanded={hasChildren ? isExpanded : undefined}
      aria-selected={isSelected}
      aria-level={level}
      className="folder-tree-item"
    >
      <div
        role="button"
        className={`folder-tree-row${isSelected ? ' folder-tree-row--selected' : ''}`}
        style={{ paddingLeft: `${(level - 1) * 16}px` }}
        tabIndex={0}
        onKeyDown={handleKeyDown}
        onClick={handleSelect}
      >
        {hasChildren ? (
          <button
            type="button"
            className="folder-tree-toggle"
            onClick={handleExpandClick}
            aria-hidden="true"
            tabIndex={-1}
          >
            <span className={`folder-tree-arrow${isExpanded ? ' folder-tree-arrow--open' : ''}`}>
              ▶
            </span>
          </button>
        ) : (
          <span className="folder-tree-toggle-spacer" />
        )}
        <span className="folder-tree-icon" aria-hidden="true">
          📁
        </span>
        <span className="folder-tree-label">{node.label === '' ? '(root)' : node.label}</span>
        <span className="folder-tree-count">({node.count})</span>
      </div>
      {hasChildren && isExpanded && (
        <ul role="group" className="folder-tree-children">
          {node.children.map((child) => (
            <TreeNode
              key={child.fullPath}
              node={child}
              level={level + 1}
              selectedPaths={selectedPaths}
              expandedPaths={expandedPaths}
              onTogglePath={onTogglePath}
              onToggleExpand={onToggleExpand}
            />
          ))}
        </ul>
      )}
    </li>
  );
});

const FolderFacetTree = memo(function FolderFacetTree({
  roots,
  selectedPaths,
  onTogglePath,
}: FolderFacetTreeProps) {
  const intl = useIntl();
  const [expandedPaths, setExpandedPaths] = useState<Set<string>>(() => new Set());

  const handleToggleExpand = useCallback((fullPath: string) => {
    setExpandedPaths((prev) => {
      const next = new Set(prev);
      if (next.has(fullPath)) {
        next.delete(fullPath);
      } else {
        next.add(fullPath);
      }
      return next;
    });
  }, []);

  const treeLabel = useMemo(() => intl.formatMessage({ id: 'filters.folder' }), [intl]);

  if (roots.length === 0) return null;

  return (
    <div className="facet-group folder-facet-group">
      <h3 className="facet-group-title">
        <span aria-hidden="true">📁</span> {treeLabel}
      </h3>
      <ul role="tree" aria-label={treeLabel} className="folder-tree">
        {roots.map((root) => (
          <TreeNode
            key={root.fullPath}
            node={root}
            level={1}
            selectedPaths={selectedPaths}
            expandedPaths={expandedPaths}
            onTogglePath={onTogglePath}
            onToggleExpand={handleToggleExpand}
          />
        ))}
      </ul>
    </div>
  );
});

export default FolderFacetTree;
