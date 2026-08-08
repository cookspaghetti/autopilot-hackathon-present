import type { EvidenceReference } from '@/types/command-center'

interface EvidenceListProps {
  evidence: EvidenceReference[]
}

export function EvidenceList({ evidence }: EvidenceListProps) {
  if (evidence.length === 0) {
    return <p className='text-sm text-muted-foreground'>No evidence attached.</p>
  }

  return (
    <ul className='space-y-2'>
      {evidence.map((reference) => (
        <li
          key={`${reference.system}:${reference.entity_type}:${reference.entity_id}`}
          className='rounded-lg border border-border/60 bg-muted/20 p-3'
        >
          <div className='flex flex-wrap items-center justify-between gap-2'>
            <p className='font-mono text-xs font-semibold text-brand-navy'>
              {reference.entity_id}
            </p>
            <p className='text-xs text-muted-foreground'>{reference.system}</p>
          </div>
          <p className='mt-1 text-xs text-muted-foreground'>
            {reference.entity_type}
            {reference.fields.length > 0 && ` · ${reference.fields.join(', ')}`}
          </p>
        </li>
      ))}
    </ul>
  )
}
