import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import mermaid from 'mermaid'

/** Minimal preprocessing: strip code fences only. No syntax changes so GitHub-compatible diagrams work as-is. */
function minimalPreprocess(source: string): string {
  return source
    .replace(/^```\s*mermaid\s*\n?/i, '')
    .replace(/\n?```\s*$/g, '')
    .trim()
}

/** Escape for use inside HTML text content (e.g. in iframe srcdoc). */
function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

/** Build iframe srcdoc: Mermaid 10 from CDN, diagram as content, postMessage size. */
function buildMermaidIframeSrcdoc(diagramSource: string): string {
  const escaped = escapeHtml(diagramSource)
  const endScript = '</script>'
  return `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <script src="https://cdn.jsdelivr.net/npm/mermaid@10.9.0/dist/mermaid.min.js"><${endScript}>
</head>
<body style="margin:0;padding:8px;">
  <div class="mermaid">${escaped}</div>
  <script>
    mermaid.initialize({ startOnLoad: true, securityLevel: 'loose' });
    function sendSize() {
      var el = document.querySelector('.mermaid svg, .mermaid');
      if (el) {
        var w = Math.ceil(el.scrollWidth || el.getBoundingClientRect().width) + 24;
        var h = Math.ceil(el.scrollHeight || el.getBoundingClientRect().height) + 24;
        window.parent.postMessage({ type: 'mermaid-iframe-size', width: w, height: h }, '*');
      }
    }
    window.addEventListener('load', function() {
      setTimeout(sendSize, 100);
      setTimeout(sendSize, 500);
    });
  <${endScript}>
</body>
</html>`
}

/** Optional aggressive fixes for known LLM typos / invalid syntax (used only if run() fails). */
function aggressivePreprocess(source: string): string {
  let out = source
    .split('\n')
    .map((line) => line.trimEnd())
    .join('\n')
    .trim()
  out = out.replace(/\bOutnut\b/gi, 'Output')
  out = out.replace(/\bOutut\b/gi, 'Output')
  if (/sequenceDiagram/i.test(out) && /\bR->>/m.test(out) && !/participant\s+R\s/m.test(out)) {
    const match = out.match(/(\s*participant\s+\w+[^\n]*\n)+/)
    if (match) {
      out = out.slice(0, match.index! + match[0].length) + '    participant R as Result\n' + out.slice(match.index! + match[0].length)
    } else {
      out = 'participant R as Result\n    ' + out
    }
  }
  out = out.replace(/(-->|--)\s*"\s*([^"]+)"\s*\|\s*/g, '$1|"$2"| ')
  out = out.replace(/(-->|--)\s*"\s*([^"]+)"\s+([^\n]+)/g, (_, arrow, label, rest) => `${arrow}|"${label}"| ${rest.trim()}`)
  out = out.replace(/\|\s*"([^"]*)"\s*\|/g, '|"$1"|')
  return out
}

interface MermaidDiagramProps {
  source: string
  jobId?: string
  /** When provided, node clicks call this with the node label instead of navigating by hash */
  onNodeClick?: (nodeLabel: string) => void
}

let mermaidInitialized = false
function ensureMermaidConfig() {
  if (mermaidInitialized) return
  mermaidInitialized = true
  mermaid.initialize({ startOnLoad: false, securityLevel: 'loose' })
}

export function MermaidDiagram({ source, jobId, onNodeClick }: MermaidDiagramProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [svg, setSvg] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [useIframeFallback, setUseIframeFallback] = useState(false)
  const [iframeSize, setIframeSize] = useState<{ width: number; height: number } | null>(null)
  const [showRaw, setShowRaw] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    ensureMermaidConfig()
  }, [])

  useEffect(() => {
    if (!useIframeFallback) return
    const onMessage = (e: MessageEvent) => {
      if (e.data?.type === 'mermaid-iframe-size' && typeof e.data.width === 'number' && typeof e.data.height === 'number') {
        setIframeSize({ width: e.data.width, height: e.data.height })
      }
    }
    window.addEventListener('message', onMessage)
    return () => window.removeEventListener('message', onMessage)
  }, [useIframeFallback])

  useEffect(() => {
    if (!source.trim()) return
    let cancelled = false
    setUseIframeFallback(false)
    setIframeSize(null)
    const preprocessed = minimalPreprocess(source)

    // Use mermaid.run() on a .mermaid node — same path as GitHub/VSCode markdown preview.
    const runNode = document.createElement('div')
    runNode.className = 'mermaid'
    runNode.textContent = preprocessed
    document.body.appendChild(runNode)

    mermaid
      .run({ nodes: [runNode], suppressErrors: false })
      .then(() => {
        if (cancelled) return
        const html = runNode.innerHTML
        runNode.remove()
        const isErrorSvg =
          html.includes('aria-roledescription="error"') ||
          (html.includes('role="graphics-document document"') && html.includes('error'))
        if (isErrorSvg) {
          if (!cancelled) {
            setUseIframeFallback(true)
            setIframeSize(null)
          }
        } else {
          setSvg(html)
          setError(null)
        }
      })
        .catch(() => {
        runNode.remove()
        if (cancelled) return
        setIframeSize(null)
        // Fallback: render() with aggressive preprocessing.
        const id = `mermaid-${Math.random().toString(36).slice(2)}`
        const processed = aggressivePreprocess(minimalPreprocess(source))
        mermaid
          .render(id, processed)
          .then(({ svg: s }) => {
            if (cancelled) return
            const isErrorSvg =
              s.includes('aria-roledescription="error"') ||
              (s.includes('role="graphics-document document"') && s.includes('error'))
            if (isErrorSvg) {
              setUseIframeFallback(true)
              setIframeSize(null)
              setError(null)
              setSvg(null)
            } else {
              setSvg(s)
              setError(null)
            }
          })
          .catch(() => {
            if (!cancelled) {
              setUseIframeFallback(true)
              setIframeSize(null)
              setError(null)
              setSvg(null)
            }
          })
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
      const id = (node.getAttribute('data-id') ?? (node as HTMLElement).id) ?? ''
      const labelEl = node.querySelector('.nodeLabel') ?? node.querySelector('text')
      const label = (labelEl?.textContent ?? id ?? '').trim() || id
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

  if (useIframeFallback) {
    const preprocessed = minimalPreprocess(source)
    return (
      <div className="my-4 w-fit overflow-visible rounded border border-slate-200 bg-white p-4">
        <iframe
          title="Mermaid diagram"
          srcDoc={buildMermaidIframeSrcdoc(preprocessed)}
          className="border-0 align-top block overflow-visible"
          style={{
            width: iframeSize ? `${iframeSize.width}px` : 900,
            height: iframeSize ? `${iframeSize.height}px` : 600,
          }}
          sandbox="allow-scripts"
        />
      </div>
    )
  }

  if (error) {
    return (
      <div className="my-4 rounded border border-red-200 bg-red-50 p-3">
        <p className="text-sm font-medium text-red-800">Diagram could not be rendered.</p>
        <p className="mt-1 text-xs text-red-700">{error}</p>
        <p className="mt-1 text-xs text-slate-600">
          The same diagram may render in GitHub or VSCode markdown preview. You can copy the source and paste it there to debug.
        </p>
        <button
          type="button"
          onClick={() => setShowRaw((s) => !s)}
          className="mt-2 text-sm text-red-600 hover:underline"
        >
          {showRaw ? 'Hide' : 'Show'} raw source
        </button>
        {showRaw && (
          <pre className="mt-2 max-h-48 overflow-auto rounded bg-white p-2 text-xs text-slate-600">{source}</pre>
        )}
      </div>
    )
  }

  if (svg) {
    return (
      <div
        ref={containerRef}
        className="mermaid-diagram my-4 w-fit overflow-visible rounded border border-slate-200 bg-white p-4 [&_svg]:max-w-none"
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
