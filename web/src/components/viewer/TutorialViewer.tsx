import { useEffect, useState } from 'react'
import { getJobFile, jobResultZipUrl } from '../../api/client'
import { MarkdownRenderer } from './MarkdownRenderer'
import { ChapterSidebar } from './ChapterSidebar'
import type { ChapterItem } from './MarkdownRenderer'

interface TutorialViewerProps {
  jobId?: string
  projectName: string
  basePath?: string
  /** When provided, files are fetched via this instead of getJobFile (e.g. for output-dir browser). */
  getFile?: (path: string) => Promise<string>
}

export function TutorialViewer({ jobId, projectName, basePath, getFile }: TutorialViewerProps) {
  const base = basePath !== undefined ? basePath : projectName
  const prefix = base ? `${base}/` : ''
  const fetchFile = getFile ?? ((path: string) => getJobFile(jobId!, path))
  const [indexContent, setIndexContent] = useState<string | null>(null)
  const [chapterContent, setChapterContent] = useState<Record<string, string>>({})
  const [selectedFilename, setSelectedFilename] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchFile(`${prefix}index.md`)
      .then(setIndexContent)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load'))
      .finally(() => setLoading(false))
  }, [prefix])

  const chapterList: ChapterItem[] = (() => {
    if (!indexContent) return []
    const section = indexContent.match(/## Chapters?\s*\n([\s\S]*?)(?=\n\n---|\n## |$)/i)
    if (!section) return []
    const lines = section[1].trim().split('\n').filter(Boolean)
    const out: ChapterItem[] = []
    for (const line of lines) {
      const m = line.match(/^\d+\.\s*\[([^\]]*)\]\(([^)]+\.md)\)/)
      if (m) out.push({ num: String(out.length + 1), title: m[1], filename: m[2] })
    }
    return out
  })()

  const loadChapter = (filename: string | null) => {
    setSelectedFilename(filename)
    if (!filename) return
    if (chapterContent[filename]) return
    fetchFile(`${prefix}${filename}`)
      .then((content) => setChapterContent((c) => ({ ...c, [filename]: content })))
      .catch(() => {})
  }

  const mainContent =
    selectedFilename === null
      ? indexContent
      : chapterContent[selectedFilename] ?? null

  if (loading) return <div className="text-slate-600">Loading…</div>
  if (error) return <div className="text-red-600">{error}</div>
  if (!indexContent) return null

  return (
    <div className="flex gap-4 h-[calc(100vh-8rem)]">
      <ChapterSidebar
        projectName={projectName}
        chapterList={chapterList}
        selectedFilename={selectedFilename}
        onSelect={loadChapter}
      />
      <div className="flex-1 min-w-0 flex flex-col">
        <div className="flex justify-between items-center mb-4">
          <h1 className="text-2xl font-semibold text-slate-800">
            {selectedFilename
              ? chapterList.find((c) => c.filename === selectedFilename)?.title ?? selectedFilename
              : projectName}
          </h1>
          {jobId && (
            <a
              href={jobResultZipUrl(jobId)}
              download
              className="px-3 py-1.5 text-sm bg-slate-200 hover:bg-slate-300 rounded"
            >
              Download zip
            </a>
          )}
        </div>
        <div className="overflow-y-auto overflow-x-auto flex-1 pr-4">
          {mainContent ? (
            <MarkdownRenderer
              content={mainContent}
              jobId={jobId}
              basePath={base}
              onChapterClick={loadChapter}
              chapterList={chapterList}
            />
          ) : selectedFilename ? (
            <div className="text-slate-500">Loading chapter…</div>
          ) : null}
        </div>
      </div>
    </div>
  )
}
