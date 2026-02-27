import { useState } from 'react'
import type { TreeNode } from '../../types'

interface TreeNavProps {
  tree: TreeNode[]
  jobId: string
  currentSlug?: string
  onSelect: (slug: string) => void
}

function TreeNavItem({
  node,
  jobId,
  currentSlug,
  onSelect,
  depth = 0,
}: {
  node: TreeNode
  jobId: string
  currentSlug?: string
  onSelect: (slug: string) => void
  depth?: number
}) {
  const [open, setOpen] = useState(depth < 2)
  const hasChildren = node.children && node.children.length > 0
  const isActive = currentSlug === node.slug

  return (
    <div className="select-none" style={{ paddingLeft: depth * 12 }}>
      <div className="flex items-center gap-1 py-0.5">
        {hasChildren && (
          <button
            type="button"
            onClick={() => setOpen((o) => !o)}
            className="w-5 h-5 flex items-center justify-center text-slate-500 hover:bg-slate-100 rounded"
          >
            {open ? '−' : '+'}
          </button>
        )}
        {!hasChildren && <span className="w-5 inline-block" />}
        <button
          type="button"
          onClick={() => onSelect(node.slug)}
          className={`flex-1 text-left text-sm truncate rounded px-1 py-0.5 ${isActive ? 'bg-slate-200 font-medium' : 'hover:bg-slate-100'}`}
        >
          {node.name}
        </button>
      </div>
      {hasChildren && open && (
        <div className="mt-0.5">
          {node.children!.map((child) => (
            <TreeNavItem
              key={child.slug}
              node={child}
              jobId={jobId}
              currentSlug={currentSlug}
              onSelect={onSelect}
              depth={depth + 1}
            />
          ))}
        </div>
      )}
    </div>
  )
}

export function TreeNav({ tree, jobId, currentSlug, onSelect }: TreeNavProps) {
  return (
    <div className="py-2">
      {tree.map((node) => (
        <TreeNavItem
          key={node.slug}
          node={node}
          jobId={jobId}
          currentSlug={currentSlug}
          onSelect={onSelect}
        />
      ))}
    </div>
  )
}
