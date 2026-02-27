import { useState, useEffect } from 'react'
import { getJobTree, getJobFile } from '../../api/client'
import { TreeNav } from './TreeNav'
import { Breadcrumb, type BreadcrumbItem } from './Breadcrumb'
import { MarkdownRenderer } from './MarkdownRenderer'
import { jobResultZipUrl } from '../../api/client'
import type { TreeNode } from '../../types'

function flattenTree(nodes: TreeNode[], path: { slug: string; name: string }[] = []): { slug: string; path: BreadcrumbItem[] }[] {
  const out: { slug: string; path: BreadcrumbItem[] }[] = []
  for (const n of nodes) {
    const p = [...path, { slug: n.slug, name: n.name }]
    out.push({ slug: n.slug, path: p })
    if (n.children?.length) out.push(...flattenTree(n.children, p))
  }
  return out
}

interface HierarchicalViewerProps {
  jobId: string
  initialSlug?: string
}

export function HierarchicalViewer({ jobId, initialSlug }: HierarchicalViewerProps) {
  const [tree, setTree] = useState<TreeNode[]>([])
  const [content, setContent] = useState<string | null>(null)
  const [currentSlug, setCurrentSlug] = useState<string | undefined>(initialSlug)
  const [breadcrumb, setBreadcrumb] = useState<BreadcrumbItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const onHash = () => setCurrentSlug((s) => window.location.hash.slice(1) || s)
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  useEffect(() => {
    getJobTree(jobId)
      .then((t) => {
        setTree(Array.isArray(t) ? t : [])
        const flat = flattenTree(Array.isArray(t) ? t : [])
        const slug = initialSlug || (t?.[0] as TreeNode)?.slug
        if (slug) {
          const item = flat.find((f) => f.slug === slug)
          if (item) setBreadcrumb(item.path)
          setCurrentSlug(slug)
        }
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load tree'))
      .finally(() => setLoading(false))
  }, [jobId, initialSlug])

  useEffect(() => {
    if (!currentSlug) return
    const path = `${currentSlug}/index.md`
    getJobFile(jobId, path)
      .then(setContent)
      .catch(() => setContent(null))
    const flat = flattenTree(tree)
    const item = flat.find((f) => f.slug === currentSlug)
    setBreadcrumb(item?.path ?? [])
  }, [jobId, currentSlug, tree])

  if (loading) return <div className="text-slate-600">Loading tree…</div>
  if (error) return <div className="text-red-600">{error}</div>

  return (
    <div className="flex gap-4 h-[calc(100vh-8rem)]">
      <aside className="w-64 shrink-0 border-r border-slate-200 overflow-y-auto">
        <div className="p-2 font-medium text-slate-700">Folders</div>
        <TreeNav
          tree={tree}
          jobId={jobId}
          currentSlug={currentSlug}
          onSelect={(slug) => {
            setCurrentSlug(slug)
            window.location.hash = slug
          }}
        />
      </aside>
      <div className="flex-1 min-w-0 flex flex-col">
        <div className="flex justify-between items-center mb-2">
          <Breadcrumb items={breadcrumb} jobId={jobId} />
          <a href={jobResultZipUrl(jobId)} download className="text-sm text-slate-600 hover:underline">
            Download zip
          </a>
        </div>
        <div className="overflow-y-auto flex-1 pr-4">
          {content ? (
            <MarkdownRenderer content={content} jobId={jobId} basePath={currentSlug} />
          ) : (
            <p className="text-slate-500">Select a folder or no content for this path.</p>
          )}
        </div>
      </div>
    </div>
  )
}
