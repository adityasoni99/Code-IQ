import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { createJob, createUploadJob, createRecursiveJob } from '../api/client'
import { JobCreateForm, type JobCreateFormProps } from '../components/job/JobCreateForm'

export function HomePage() {
  const [activeTab, setActiveTab] = useState<'url' | 'upload' | 'recursive'>('url')
  const navigate = useNavigate()

  const handleSubmit: JobCreateFormProps['onSubmit'] = async (values) => {
    if (values.mode === 'url') {
      const { job_id } = await createJob({
        repo_url: values.repo_url!,
        project_name: values.project_name || undefined,
        language: values.language || 'english',
      })
      navigate(`/jobs/${job_id}`)
    } else if (values.mode === 'upload') {
      const formData = new FormData()
      formData.append('file', values.file!)
      if (values.project_name) formData.append('project_name', values.project_name)
      formData.append('language', values.language || 'english')
      const { job_id } = await createUploadJob(formData)
      navigate(`/jobs/${job_id}`)
    } else {
      const { job_id } = await createRecursiveJob({
        parent_dirs: values.parent_dirs || [],
        file_threshold: values.file_threshold ?? 100,
        parallel: values.parallel ?? 0,
        resume: values.resume ?? true,
        output_dir: values.output_dir || 'output',
        language: values.language || 'english',
      })
      navigate(`/jobs/${job_id}`)
    }
  }

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-semibold text-slate-800 mb-4">Create tutorial job</h1>
      <div className="flex gap-2 border-b mb-4">
        {(['url', 'upload', 'recursive'] as const).map((tab) => (
          <button
            key={tab}
            type="button"
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 text-sm font-medium rounded-t ${activeTab === tab ? 'bg-white border border-b-0 border-slate-200 -mb-px' : 'text-slate-600 hover:text-slate-900'}`}
          >
            {tab === 'url' ? 'GitHub URL' : tab === 'upload' ? 'Upload Zip' : 'Recursive'}
          </button>
        ))}
      </div>
      <JobCreateForm mode={activeTab} onSubmit={handleSubmit} />
    </div>
  )
}
