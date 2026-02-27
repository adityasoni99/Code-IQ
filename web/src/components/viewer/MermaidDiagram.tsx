import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import mermaid from 'mermaid'

interface MermaidDiagramProps {
  source: string
  jobId?: string
  basePath?: string
  /** When provided, node clicks call this with the node label instead of navigating by hash */
  onNodeClick?: (nodeLabel: string) => void
}

export function MermaidDiagram({ source, jobId, onNodeClick }: MermaidDiagramProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [svg, setSvg] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()

  useEffect(() => {
    if (!source.trim()) return
    let cancelled = false
    const id = `mermaid-${Math.random().toString(36).slice(2)}`
    mermaid
      .render(id, source)
      .then(({ svg: s }) => {
        if (!cancelled) {
          setSvg(s)
          setError(null)
        }
      })
      .catch((err) => {
        if (!cancelled) setError(String(err))
      })
    return () => {
      cancelled = true
    }
  }, [source])

  useEffect(() => {
    if (!svg || !containerRef.current) return
    const container = containerRef.current
    const nodes = container.querySelectorAll('.node')
    nodes.forEach((node) => {
      const id = node.getAttribute('data-id') || (node as HTMLElement).id
      const label = (node.querySelector('text')?.textContent ?? id ?? '').trim() || id
      if (!id && !label) return
      const slug = (id || label).replace(/\s+/g, '-').toLowerCase()
      ;(node as HTMLElement).style.cursor = 'pointer'
      node.addEventListener('click', () => {
        if (onNodeClick) {
          onNodeClick(label || slug)
        } else if (jobId) {
          navigate(`/jobs/${jobId}/view#${slug}`)
        }
      })
    })
  }, [svg, jobId, navigate, onNodeClick])

  if (error) {
    return <pre className="text-sm text-red-600 overflow-auto p-2 bg-red-50 rounded">{error}</pre>
  }

  if (svg) {
    return (
      <div
        ref={containerRef}
        className="mermaid-diagram my-4 overflow-auto rounded border border-slate-200 bg-white p-4"
        dangerouslySetInnerHTML={{ __html: svg }}
      />
    )
  }

  return (
    <div className="my-4 p-4 border border-slate-200 rounded bg-slate-50">
      <pre className="text-sm text-slate-500">{source}</pre>
    </div>
  )
}
