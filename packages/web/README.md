# Copio Web

Next.js 16 frontend for the Copio multi-marketplace ERP.

## Tech Stack

- **Framework**: Next.js 16 (App Router)
- **React**: 19.x with Server & Client Components
- **Styling**: Tailwind CSS 4
- **UI Components**: Radix UI primitives
- **Forms**: React Hook Form + Zod validation
- **Data Fetching**: TanStack React Query + Axios
- **Notifications**: Sonner toasts

## Setup

### Prerequisites

- Node.js 20+
- pnpm 9+
- Running API backend (see `packages/api`)

### Installation

```bash
cd packages/web
pnpm install
```

### Development

```bash
# Start dev server
pnpm dev

# Open http://localhost:3000
```

### Build

```bash
pnpm build
pnpm start
```

## Project Structure

```
src/
├── app/                    # Next.js App Router
│   ├── page.tsx            # Dashboard (home)
│   ├── layout.tsx          # Root layout
│   ├── error.tsx           # Error boundary
│   ├── not-found.tsx       # 404 page
│   ├── products/
│   │   ├── page.tsx        # Product list
│   │   └── [id]/
│   │       ├── page.tsx    # Product detail
│   │       └── product-editor.tsx  # 6-tab editor
│   ├── categories/
│   │   └── page.tsx        # Category management
│   ├── locations/
│   │   └── page.tsx        # Warehouse locations
│   ├── inventory/
│   │   └── page.tsx        # Stock levels
│   ├── vendors/
│   │   ├── page.tsx        # Vendor list
│   │   └── [id]/page.tsx   # Vendor detail
│   └── purchase-orders/
│       ├── page.tsx        # PO list
│       └── [id]/page.tsx   # PO detail + PDF
├── components/
│   ├── ui/                 # Radix UI primitives
│   │   ├── button.tsx
│   │   ├── dialog.tsx
│   │   ├── table.tsx
│   │   ├── form.tsx
│   │   ├── select.tsx
│   │   ├── tabs.tsx
│   │   └── ...
│   ├── sidebar.tsx         # Navigation
│   ├── providers.tsx       # React Query + Theme
│   ├── pagination.tsx      # Table pagination
│   └── ...
├── hooks/                  # Custom React hooks
│   ├── use-products.ts
│   ├── use-locations.ts
│   ├── use-stock-items.ts
│   └── use-dashboard.ts
└── lib/
    ├── api.ts              # Axios client + helpers
    └── utils.ts            # Utility functions
```

## Pages

| Route | Description |
|-------|-------------|
| `/` | Dashboard with KPIs and quick actions |
| `/products` | Product catalog with filters |
| `/products/[id]` | Product editor (6 tabs) |
| `/categories` | Category tree management |
| `/locations` | Warehouse/location CRUD |
| `/inventory` | Stock levels and movements |
| `/vendors` | Vendor management |
| `/vendors/[id]` | Vendor detail + contacts, addresses, documents |
| `/purchase-orders` | PO list with status filters |
| `/purchase-orders/[id]` | PO detail + line items + PDF export |

## Product Editor Tabs

The product detail page at `/products/[id]` has 6 tabs:

1. **Basic Info** - Name, brand, manufacturer, pricing
2. **Content** - Descriptions, bullet points, SEO metadata
3. **Physical** - Weight, dimensions, package dimensions
4. **Identifiers** - UPC, EAN, GTIN, ASIN, MPN
5. **Compliance** - Country of origin, certifications, hazmat flags
6. **Media** - Images, custom attributes

## API Proxy

The frontend proxies `/api/*` requests to the Python backend. This is configured in `next.config.ts`:

```typescript
// Requests to /api/* are forwarded to the Python API
rewrites: async () => [
  {
    source: '/api/:path*',
    destination: `${API_URL}/:path*`,
  },
]
```

Default API URL: `http://localhost:8001/api/v1`

## Environment Variables

```bash
# API backend URL
API_URL=http://localhost:8001/api/v1
```

## UI Components

Uses Radix UI primitives with Tailwind CSS styling:

- `<Button>` - Primary, secondary, ghost, outline variants
- `<Dialog>` - Modal dialogs
- `<Table>` - Data tables with sorting
- `<Form>` - Form fields with validation
- `<Select>` - Dropdown selects
- `<Tabs>` - Tab navigation
- `<AlertDialog>` - Confirmation dialogs
- `<DropdownMenu>` - Context menus
