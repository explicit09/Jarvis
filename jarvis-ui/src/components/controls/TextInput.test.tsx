import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { TextInput } from './TextInput'

describe('TextInput', () => {
  const mockOnSend = vi.fn()

  beforeEach(() => {
    mockOnSend.mockClear()
  })

  it('renders input and send button', () => {
    render(<TextInput onSend={mockOnSend} />)

    expect(screen.getByPlaceholderText('Type a command...')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /send/i })).toBeInTheDocument()
  })

  it('allows typing in input', async () => {
    render(<TextInput onSend={mockOnSend} />)
    const user = userEvent.setup()

    const input = screen.getByPlaceholderText('Type a command...')
    await user.type(input, 'Hello JARVIS')

    expect(input).toHaveValue('Hello JARVIS')
  })

  it('calls onSend when clicking send button with text', async () => {
    render(<TextInput onSend={mockOnSend} />)
    const user = userEvent.setup()

    const input = screen.getByPlaceholderText('Type a command...')
    await user.type(input, 'Hello')

    const sendButton = screen.getByRole('button', { name: /send/i })
    await user.click(sendButton)

    expect(mockOnSend).toHaveBeenCalledWith('Hello')
  })

  it('clears input after sending', async () => {
    render(<TextInput onSend={mockOnSend} />)
    const user = userEvent.setup()

    const input = screen.getByPlaceholderText('Type a command...')
    await user.type(input, 'Test message')
    await user.click(screen.getByRole('button', { name: /send/i }))

    expect(input).toHaveValue('')
  })

  it('sends message on Enter key', async () => {
    render(<TextInput onSend={mockOnSend} />)
    const user = userEvent.setup()

    const input = screen.getByPlaceholderText('Type a command...')
    await user.type(input, 'Enter test{Enter}')

    expect(mockOnSend).toHaveBeenCalledWith('Enter test')
  })

  it('does not send empty message', async () => {
    render(<TextInput onSend={mockOnSend} />)
    const user = userEvent.setup()

    const sendButton = screen.getByRole('button', { name: /send/i })
    await user.click(sendButton)

    expect(mockOnSend).not.toHaveBeenCalled()
  })

  it('does not send whitespace-only message', async () => {
    render(<TextInput onSend={mockOnSend} />)
    const user = userEvent.setup()

    const input = screen.getByPlaceholderText('Type a command...')
    await user.type(input, '   ')
    await user.click(screen.getByRole('button', { name: /send/i }))

    expect(mockOnSend).not.toHaveBeenCalled()
  })

  it('trims whitespace from message', async () => {
    render(<TextInput onSend={mockOnSend} />)
    const user = userEvent.setup()

    const input = screen.getByPlaceholderText('Type a command...')
    await user.type(input, '  Hello world  ')
    await user.click(screen.getByRole('button', { name: /send/i }))

    expect(mockOnSend).toHaveBeenCalledWith('Hello world')
  })

  it('disables input when disabled prop is true', () => {
    render(<TextInput onSend={mockOnSend} disabled />)

    const input = screen.getByPlaceholderText('Type a command...')
    expect(input).toBeDisabled()
  })

  it('disables send button when disabled prop is true', () => {
    render(<TextInput onSend={mockOnSend} disabled />)

    const sendButton = screen.getByRole('button', { name: /send/i })
    expect(sendButton).toBeDisabled()
  })

  it('disables send button when input is empty', () => {
    render(<TextInput onSend={mockOnSend} />)

    const sendButton = screen.getByRole('button', { name: /send/i })
    expect(sendButton).toBeDisabled()
  })

  it('does not send when disabled', async () => {
    render(<TextInput onSend={mockOnSend} disabled />)

    const input = screen.getByPlaceholderText('Type a command...')
    // Using fireEvent since userEvent respects disabled state
    fireEvent.change(input, { target: { value: 'Test' } })
    fireEvent.click(screen.getByRole('button', { name: /send/i }))

    expect(mockOnSend).not.toHaveBeenCalled()
  })
})
