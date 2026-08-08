'use client'

import { useState, useRef, useEffect, KeyboardEvent } from 'react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Icons } from '@/components/ui/icons'

interface ChatInputProps {
  onSend: (message: string) => void
  disabled?: boolean
  placeholder?: string
}

export function ChatInput({ onSend, disabled, placeholder = 'Ask anything...' }: ChatInputProps) {
  const [value, setValue] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current
    if (textarea) {
      textarea.style.height = 'auto'
      textarea.style.height = `${Math.min(textarea.scrollHeight, 120)}px`
    }
  }, [value])

  // Focus input on mount
  useEffect(() => {
    if (textareaRef.current && !disabled) {
      textareaRef.current.focus()
    }
  }, [disabled])

  const handleSend = () => {
    const trimmed = value.trim()
    if (trimmed && !disabled) {
      onSend(trimmed)
      setValue('')
      // Reset height
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto'
      }
    }
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className={cn(
      'flex items-end gap-3 p-4 sm:p-5',
      'bg-gradient-to-t from-gray-50/80 to-transparent'
    )}>
      <div className={cn(
        'flex-1 flex items-end',
        'rounded-xl border border-border/50 bg-white',
        'shadow-sm',
        'transition-all duration-200',
        'focus-within:border-brand-cornflower/50 focus-within:ring-2 focus-within:ring-brand-cornflower/20',
        'focus-within:shadow-md'
      )}>
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={disabled}
          rows={1}
          className={cn(
            'flex-1 resize-none bg-transparent px-4 py-3',
            'text-sm text-foreground placeholder:text-muted-foreground',
            'focus:outline-none',
            'max-h-[120px]',
            disabled && 'opacity-50 cursor-not-allowed'
          )}
        />
        
        {/* Character indicator for long messages */}
        {value.length > 200 && (
          <span className="pr-3 pb-3 text-xs text-muted-foreground">
            {value.length}
          </span>
        )}
      </div>

      <Button
        onClick={handleSend}
        disabled={!value.trim() || disabled}
        size="icon"
        className={cn(
          'h-11 w-11 rounded-xl flex-shrink-0',
          'bg-gradient-to-br from-brand-navy to-brand-purple',
          'hover:from-brand-navy/90 hover:to-brand-purple/90',
          'shadow-md shadow-brand-navy/20',
          'transition-all duration-200',
          'disabled:opacity-50 disabled:cursor-not-allowed disabled:shadow-none'
        )}
      >
        {disabled ? (
          <Icons.loader className="h-5 w-5 animate-spin text-white" strokeWidth={1.5} />
        ) : (
          <Icons.send className="h-5 w-5 text-white" strokeWidth={1.5} />
        )}
      </Button>
    </div>
  )
}
