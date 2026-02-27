import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { JobCreateForm } from './JobCreateForm'

describe('JobCreateForm', () => {
  it('renders URL tab fields', () => {
    const onSubmit = vi.fn()
    render(<JobCreateForm mode="url" onSubmit={onSubmit} />)
    expect(screen.getByPlaceholderText(/github.com\/owner\/repo/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /create job/i })).toBeInTheDocument()
  })

  it('shows error when submitting URL tab without repo URL', async () => {
    const onSubmit = vi.fn()
    render(<JobCreateForm mode="url" onSubmit={onSubmit} />)
    fireEvent.click(screen.getByRole('button', { name: /create job/i }))
    expect(await screen.findByText(/repository url is required/i)).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('renders recursive tab fields', () => {
    const onSubmit = vi.fn()
    render(<JobCreateForm mode="recursive" onSubmit={onSubmit} />)
    expect(screen.getByPlaceholderText(/path\/to\/parent/i)).toBeInTheDocument()
    expect(screen.getByDisplayValue('100')).toBeInTheDocument()
  })
})
