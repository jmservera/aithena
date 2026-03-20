export interface FacetTreeNode {
  label: string;
  fullPath: string;
  count: number;
  children: FacetTreeNode[];
  isLeaf: boolean;
}

interface FacetInput {
  value: string;
  count: number;
}

/**
 * Build a hierarchical tree from flat folder facet values.
 *
 * Paths like ["en", "en/Science Fiction", "en/History", "es"] are parsed
 * by splitting on "/" and grouped into a tree.  Parent counts are the sum
 * of their own direct count (if the path itself appeared as a facet value)
 * plus the counts of all descendants.
 */
export function buildFacetTree(facets: FacetInput[]): FacetTreeNode[] {
  const nodeMap = new Map<string, FacetTreeNode>();

  // First pass: register every path segment so intermediate nodes exist
  for (const { value, count } of facets) {
    const parts = value.split('/');
    let current = '';
    for (let i = 0; i < parts.length; i++) {
      current = i === 0 ? parts[i] : `${current}/${parts[i]}`;
      if (!nodeMap.has(current)) {
        nodeMap.set(current, {
          label: parts[i],
          fullPath: current,
          count: 0,
          children: [],
          isLeaf: true,
        });
      }
    }
    // Assign the direct count from the facet value
    const node = nodeMap.get(value)!;
    node.count = count;
  }

  // Second pass: wire parent → child relationships
  for (const node of nodeMap.values()) {
    const slashIdx = node.fullPath.lastIndexOf('/');
    if (slashIdx !== -1) {
      const parentPath = node.fullPath.substring(0, slashIdx);
      const parent = nodeMap.get(parentPath);
      if (parent) {
        parent.children.push(node);
        parent.isLeaf = false;
      }
    }
  }

  // Third pass: propagate counts bottom-up (parent = sum of children if parent has no own facet count or always sum)
  function sumCounts(node: FacetTreeNode): number {
    if (node.children.length === 0) return node.count;
    const childSum = node.children.reduce((acc, child) => acc + sumCounts(child), 0);
    // If the parent appeared as its own facet value, its count already includes
    // documents directly in that folder.  Add children counts on top.
    // But per PRD: "parent = sum of children", so we override.
    node.count = node.count + childSum;
    return node.count;
  }

  // Collect root nodes (those without a parent in the map)
  const roots: FacetTreeNode[] = [];
  for (const node of nodeMap.values()) {
    const slashIdx = node.fullPath.lastIndexOf('/');
    if (slashIdx === -1) {
      roots.push(node);
    }
  }

  // Sort children alphabetically at every level, then propagate counts
  function sortTree(nodes: FacetTreeNode[]): void {
    nodes.sort((a, b) => a.label.localeCompare(b.label));
    for (const node of nodes) {
      sortTree(node.children);
    }
  }

  sortTree(roots);

  for (const root of roots) {
    sumCounts(root);
  }

  return roots;
}
