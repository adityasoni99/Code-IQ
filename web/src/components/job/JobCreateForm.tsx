import { useState } from 'react'

export type JobCreateFormValues = {
  mode: 'url' | 'upload' | 'recursive'
  repo_url?: string
  project_name?: string
  language?: string
  file?: File
  parent_dirs?: string[]
  file_threshold?: number
  parallel?: number
  resume?: boolean
  output_dir?: string
}

export interface JobCreateFormProps {
  mode: 'url' | 'upload' | 'recursive'
  onSubmit: (values: JobCreateFormValues) => Promise<void>
}

export function JobCreateForm({ mode, onSubmit }: JobCreateFormProps) {
  const [repoUrl, setRepoUrl] = useState('')
  const [projectName, setProjectName] = useState('')
  const [language, setLanguage] = useState('english')
  const [file, setFile] = useState<File | null>(null)
  const [parentDirsText, setParentDirsText] = useState('')
  const [fileThreshold, setFileThreshold] = useState(100)
  const [parallel, setParallel] = useState(0)
  const [resume, setResume] = useState(true)
  const [outputDir, setOutputDir] = useState('output')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      if (mode === 'url') {
        if (!repoUrl?.trim()) {
          setError('Repository URL is required')
          return
        }
        await onSubmit({
          mode: 'url',
          repo_url: repoUrl.trim(),
          project_name: projectName.trim() || undefined,
          language,
        })
      } else if (mode === 'upload') {
        if (!file) {
          setError('Please select a zip file')
          return
        }
        await onSubmit({
          mode: 'upload',
          file,
          project_name: projectName.trim() || undefined,
          language,
        })
      } else {
        const dirs = parentDirsText.split('\n').map((d) => d.trim()).filter(Boolean)
        if (!dirs.length) {
          setError('Enter at least one parent directory path')
          return
        }
        await onSubmit({
          mode: 'recursive',
          parent_dirs: dirs,
          file_threshold: fileThreshold,
          parallel,
          resume,
          output_dir: outputDir,
          language,
        })
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Request failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {error && (
        <div className="p-3 rounded bg-red-50 text-red-700 text-sm">{error}</div>
      )}
      {mode === 'url' && (
        <>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Repository URL *</label>
            <input
              type="url"
              value={repoUrl}
              onChange={(e) => setRepoUrl(e.target.value)}
              className="w-full border border-slate-300 rounded px-3 py-2"
              placeholder="https://github.com/owner/repo"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Project name (optional)</label>
            <input
              type="text"
              value={projectName}
              onChange={(e) => setProjectName(e.target.value)}
              className="w-full border border-slate-300 rounded px-3 py-2"
            />
          </div>
        </>
      )}
      {mode === 'upload' && (
        <>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Zip file *</label>
            <input
              type="file"
              accept=".zip"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="w-full border border-slate-300 rounded px-3 py-2"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Project name (optional)</label>
            <input
              type="text"
              value={projectName}
              onChange={(e) => setProjectName(e.target.value)}
              className="w-full border border-slate-300 rounded px-3 py-2"
            />
          </div>
        </>
      )}
      {mode === 'recursive' && (
        <>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Parent directories (one per line) *</label>
            <textarea
              value={parentDirsText}
              onChange={(e) => setParentDirsText(e.target.value)}
              rows={4}
              className="w-full border border-slate-300 rounded px-3 py-2 font-mono text-sm"
              placeholder="/path/to/parent1&#10;/path/to/parent2"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">File threshold</label>
              <input
                type="number"
                value={fileThreshold}
                onChange={(e) => setFileThreshold(Number(e.target.value))}
                min={1}
                className="w-full border border-slate-300 rounded px-3 py-2"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Parallel workers (0 = sequential)</label>
              <input
                type="number"
                value={parallel}
                onChange={(e) => setParallel(Number(e.target.value))}
                min={0}
                className="w-full border border-slate-300 rounded px-3 py-2"
              />
            </div>
          </div>
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="resume"
              checked={resume}
              onChange={(e) => setResume(e.target.checked)}
              className="rounded"
            />
            <label htmlFor="resume" className="text-sm text-slate-700">Resume (skip completed folders)</label>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Output directory</label>
            <input
              type="text"
              value={outputDir}
              onChange={(e) => setOutputDir(e.target.value)}
              className="w-full border border-slate-300 rounded px-3 py-2"
            />
          </div>
        </>
      )}
      {(mode === 'url' || mode === 'upload') && (
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Language</label>
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            className="w-full border border-slate-300 rounded px-3 py-2"
          >
            <option value="english">English</option>
            <option value="spanish">Spanish</option>
            <option value="french">French</option>
          </select>
        </div>
      )}
      {mode === 'recursive' && (
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Language</label>
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            className="w-full border border-slate-300 rounded px-3 py-2"
          >
            <option value="english">English</option>
            <option value="spanish">Spanish</option>
            <option value="french">French</option>
          </select>
        </div>
      )}
      <button
        type="submit"
        disabled={loading}
        className="px-4 py-2 bg-slate-800 text-white rounded hover:bg-slate-700 disabled:opacity-50"
      >
        {loading ? 'Creating…' : 'Create job'}
      </button>
    </form>
  )
}
