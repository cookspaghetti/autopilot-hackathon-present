# Frontend Design System

## 1. Implementation Guide
This project uses **Tailwind CSS** with a custom configuration to match the AutoPilot design system.

### Fonts
*   **Headings:** Use `font-display` (Funnel Display).
*   **Body:** Use `font-sans` (Geologica).

```tsx
<h1 className="font-display text-4xl font-bold">Heading</h1>
<p className="font-sans text-base">Body text</p>
```

### Colors
Do not use hex codes directly in components. Use semantic variables:
*   `bg-background` (Deep Black `#04060A`)
*   `bg-primary` (Navy `#141A42`)
*   `text-foreground` (Light Grey `#E7E7E7`)
*   `bg-card` (Glassmorphic Navy)
*   `text-muted-foreground` (Muted Blue `#848EAA`)

For brand-specific colors when semantic tokens don't fit:
*   `bg-brand-black` (`#04060A`)
*   `bg-brand-navy` (`#141A42`)
*   `bg-brand-cornflower` (`#8AA2DF`)
*   `bg-brand-purple` (`#535EA4`)
*   `bg-brand-light` (`#E7E7E7`)

## 2. Common Patterns

### The "Glass" Card
Used for all content containers.
```tsx
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'

<Card>
  <CardHeader>
    <CardTitle>Heading (Funnel Display)</CardTitle>
  </CardHeader>
  <CardContent>
    Body content (Geologica)...
  </CardContent>
</Card>
```

### The "Gradient" Button
Used for the primary call-to-action on a page.
```tsx
import { Button } from '@/components/ui/button'

<Button variant="gradient" size="lg">
  Launch Action
</Button>
```

### Button Variants
```tsx
// Primary action - gradient background
<Button variant="gradient">Primary</Button>

// Default - solid primary color
<Button variant="default">Default</Button>

// Outline - bordered, transparent
<Button variant="outline">Outline</Button>

// Ghost - no background until hover
<Button variant="ghost">Ghost</Button>

// Glass - glassmorphism effect
<Button variant="glass">Glass</Button>

// Destructive - for dangerous actions
<Button variant="destructive">Delete</Button>
```

### The "Visual Pattern"
To add the brand's mesh blobs behind a page:

```tsx
const VisualPattern = () => (
  <div className="absolute inset-0 -z-10 overflow-hidden pointer-events-none">
    {/* Top Right Blob - Blue/Purple */}
    <div className="absolute -top-[20%] -right-[10%] h-[500px] w-[500px] rounded-full bg-primary/20 blur-3xl filter" />
    {/* Bottom Left Blob - Cornflower */}
    <div className="absolute top-[20%] -left-[10%] h-[400px] w-[400px] rounded-full bg-[#8AA2DF]/20 blur-3xl filter" />
  </div>
)

// Usage in a page
export default function MyPage() {
  return (
    <>
      <VisualPattern />
      <div className="relative">
        {/* Page content */}
      </div>
    </>
  )
}
```

### Logo Components
```tsx
import { Logomark, Logo } from '@/components/brand'

// Icon mark - use variant="light" on dark backgrounds
<Logomark variant="light" size={40} />

// Full wordmark
<Logo variant="dark" width={150} />
```

## 3. Iconography
*   **Library:** Lucide React
*   **Style:** Thin strokes (`strokeWidth={1.5}`).
*   **Size:** Default `h-5 w-5` for navigation, `h-6 w-6` for cards.
*   **Active State:** When a navigation item is active, the icon turns `#8AA2DF` (Cornflower Blue).

```tsx
import { Settings, Home, Users } from 'lucide-react'

// Standard icon
<Settings className="h-5 w-5" strokeWidth={1.5} />

// Active navigation icon
<Home className="h-5 w-5 text-[#8AA2DF]" strokeWidth={1.5} />

// Inactive navigation icon
<Users className="h-5 w-5 text-gray-500" strokeWidth={1.5} />
```

## 4. Spacing & Layout
*   **Grid:** The system uses a spacious 12-column grid.
*   **Radius:** `0.75rem` (12px) for cards, `9999px` (Full) for buttons.
*   **Sidebar:** Fixed width (`260px`), Dark Navy background (`#04060A`).
*   **Header:** Sticky, glassmorphism (`bg-background/80 backdrop-blur-md`).

### Page Layout Template
```tsx
// Main content area spacing
<main className="flex flex-1 flex-col gap-4 bg-background p-4 lg:gap-6 lg:p-8">
  {children}
</main>

// Card grid
<div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
  {/* Cards */}
</div>
```

## 5. Form Elements

### Input Fields
```tsx
<input 
  type="text" 
  placeholder="Search..." 
  className="h-9 w-full rounded-full border border-border bg-muted/20 pl-9 pr-4 text-sm outline-none focus:border-primary/50"
/>
```

### Switch/Toggle
```tsx
import { Switch } from '@/components/ui/switch'

<Switch />
<Switch defaultChecked />
```

## 6. Shadow System
Custom shadow utilities for depth:
*   `shadow-soft` - Subtle elevation for cards
*   `shadow-medium` - Hover state elevation

```tsx
// Card with hover elevation
<Card className="shadow-soft hover:shadow-medium transition-shadow">
  ...
</Card>
```

## 7. File Structure
```
frontend/
├── public/
│   └── logos/
│       ├── logomark-dark.svg
│       ├── logomark-light.svg
│       ├── logo-full-dark.svg
│       └── logo-full-light.svg
├── src/
│   ├── app/
│   │   ├── globals.css      # CSS variables & base styles
│   │   └── layout.tsx       # Font configuration
│   ├── components/
│   │   ├── brand/
│   │   │   ├── Logo.tsx
│   │   │   ├── Logomark.tsx
│   │   │   └── index.ts
│   │   ├── layout/
│   │   │   ├── Header.tsx
│   │   │   └── Sidebar.tsx
│   │   └── ui/
│   │       ├── button.tsx
│   │       ├── card.tsx
│   │       └── switch.tsx
│   └── lib/
│       └── utils.ts
└── tailwind.config.js       # Theme configuration
```
