import { useEffect, useState } from 'react'
import { getJobFile } from '../../api/client'
import { MarkdownRenderer } from './MarkdownRenderer'
import { jobResultZipUrl } from '../../api/client'

interface TutorialViewerProps {
  jobId: string
  projectName: string
  basePath?: string
}

export function TutorialViewer({ jobId, projectName, basePath }: TutorialViewerProps) {
  const base = basePath !== undefined ? basePath : projectName
  const prefix = base ? `${base}/` : ''
  const [indexContent, setIndexContent] = useState<string | null>(null)
  const [chapters, setChapters] = useState<Record<string, string>>({})
  const [openChapters, setOpenChapters] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getJobFile(jobId, `${prefix}index.md`)
      .then(setIndexContent)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load'))
      .finally(() => setLoading(false))
  }, [jobId, base])

  if (loading) return <div className="text-slate-600">Loading…</div>
  if (error) return <div className="text-red-600">{error}</div>
  if (!indexContent) return null

  // Parse "## Chapters" section: lines like "1. [Title](filename.md)"
  const chapterList = (() => {
    const section = indexContent.match(/## Chapters?\s*\n([\s\S]*?)(?=\n\n---|\n## |$)/i)
    if (!section) return []
    const lines = section[1].trim().split('\n').filter(Boolean)
    const out: { num: string; title: string; filename: string }[] = []
    for (const line of lines) {
      const m = line.match(/^\d+\.\s*\[([^\]]*)\]\(([^)]+\.md)\)/)
      if (m) out.push({ num: String(out.length + 1), title: m[1], filename: m[2] })
    }
    return out
  })()

  const loadChapterByFilename = (filename: string) => {
    setOpenChapters((s) => new Set(s).add(filename))
    const chapterId = `chapter-${filename.replace(/\.md$/, '')}`
    setTimeout(() => document.getElementById(chapterId)?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }), 100)
    if (chapters[filename]) return
    getJobFile(jobId, `${prefix}${filename}`)
      .then((content) => setChapters((c) => ({ ...c, [filename]: content })))
      .catch(() => {})
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-semibold text-slate-800">{projectName}</h1>
        <a
          href={jobResultZipUrl(jobId)}
          download
          className="px-3 py-1.5 text-sm bg-slate-200 hover:bg-slate-300 rounded"
        >
          Download zip
        </a>
      </div>
      <MarkdownRenderer
        content={indexContent}
        jobId={jobId}
        basePath={base}
        onChapterClick={loadChapterByFilename}
        chapterList={chapterList}
      />
      {chapterList.length > 0 && (
        <div className="border-t pt-4">
          <h2 className="text-lg font-medium text-slate-800 mb-2">Chapters</h2>
          {chapterList.map((ch) => (
            <div key={ch.filename} id={`chapter-${ch.filename.replace(/\.md$/, '')}`} className="border border-slate-200 rounded mb-2">
              <button
                type="button"
                onClick={() => loadChapterByFilename(ch.filename)}
                className="w-full px-4 py-2 text-left text-sm font-medium text-slate-700 hover:bg-slate-50 flex justify-between"
              >
                <span>{ch.title}</span>
                <span>{openChapters.has(ch.filename) || chapters[ch.filename] ? '▼' : '▶'}</span>
              </button>
              {(openChapters.has(ch.filename) || chapters[ch.filename]) && chapters[ch.filename] && (
                <div className="px-4 pb-4 border-t border-slate-100">
                  <MarkdownRenderer content={chapters[ch.filename]} jobId={jobId} basePath={base} />
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
