const API_BASE = ''

async function fetchApi<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options?.headers },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error((err as { detail?: string }).detail || res.statusText)
  }
  return res.json() as Promise<T>
}

export async function createJob(body: { repo_url: string; project_name?: string; language?: string; output_dir?: string }) {
  return fetchApi<{ job_id: string; status: string }>('/v1/jobs', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export async function createUploadJob(formData: FormData) {
  const res = await fetch(`${API_BASE}/v1/jobs/upload`, {
    method: 'POST',
    body: formData,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error((err as { detail?: string }).detail || res.statusText)
  }
  return res.json() as Promise<{ job_id: string; status: string }>
}

export async function createRecursiveJob(body: {
  parent_dirs: string[]
  file_threshold?: number
  parallel?: number
  resume?: boolean
  output_dir?: string
  language?: string
}) {
  return fetchApi<{ job_id: string; status: string }>('/v1/jobs/recursive', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export async function getJob(jobId: string) {
  return fetchApi<import('../types').Job>(`/v1/jobs/${jobId}`)
}

export async function getJobTree(jobId: string) {
  return fetchApi<import('../types').TreeNode[]>(`/v1/jobs/${jobId}/tree`)
}

export async function getJobFile(jobId: string, path: string): Promise<string> {
  const res = await fetch(`${API_BASE}/v1/jobs/${jobId}/files/${encodeURIComponent(path)}`)
  if (!res.ok) throw new Error(await res.text() || res.statusText)
  return res.text()
}

export function jobResultZipUrl(jobId: string): string {
  return `${API_BASE}/v1/jobs/${jobId}/result`
}

export interface TutorialListItem {
  name: string
  slug: string
  hasIndex: boolean
}

export interface TutorialsConfig {
  output_dir: string
}

export async function getTutorialsConfig(): Promise<TutorialsConfig> {
  return fetchApi<TutorialsConfig>('/v1/tutorials/config')
}

export async function listTutorials(): Promise<TutorialListItem[]> {
  return fetchApi<TutorialListItem[]>('/v1/tutorials')
}

export async function getTutorialFile(tutorialPath: string): Promise<string> {
  const encoded = tutorialPath.split('/').map(encodeURIComponent).join('/')
  const res = await fetch(`${API_BASE}/v1/tutorials/${encoded}`)
  if (!res.ok) throw new Error(await res.text() || res.statusText)
  return res.text()
}
