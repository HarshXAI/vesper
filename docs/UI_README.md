# Vesper UI Documentation

This document covers the frontend applications for the Vesper platform.

## Overview

Vesper includes two web applications:

| Application    | Purpose                           | Port | Path                    |
| -------------- | --------------------------------- | ---- | ----------------------- |
| **Analyst UI** | Financial analyst chat interface  | 3000 | `/frontends/analyst-ui` |
| **Ops UI**     | Operations dashboard & monitoring | 3001 | `/frontends/ops-ui`     |

## Analyst UI

### Features

- **Streaming Chat**: Real-time SSE-based responses with token-by-token display
- **Citations**: Inline citation chips with hover preview and source linking
- **Trace View**: Expandable trace panel showing retrieval and generation steps
- **Markdown Rendering**: Rich text formatting with syntax highlighting
- **Copy with Citations**: Export responses with proper source attribution

### Technology Stack

- Next.js 15 (App Router)
- TypeScript
- Tailwind CSS
- Zustand (state management)
- NextAuth.js (authentication)

### Quick Start

```bash
cd frontends/analyst-ui
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

### Environment Variables

Create `.env.local`:

```env
# API Configuration
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_STREAMING_ENABLED=true

# Authentication (Cognito OIDC)
COGNITO_ISSUER=https://cognito-idp.us-east-1.amazonaws.com/us-east-1_XXXXX
COGNITO_CLIENT_ID=your-client-id
COGNITO_CLIENT_SECRET=your-client-secret
NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET=your-nextauth-secret
```

### Architecture

```
analyst-ui/
├── app/
│   ├── api/auth/[...nextauth]/  # NextAuth.js handler
│   ├── globals.css              # Tailwind styles
│   ├── layout.tsx               # Root layout
│   ├── page.tsx                 # Chat page
│   └── providers.tsx            # Context providers
├── components/
│   ├── ChatMessage.tsx          # Message rendering
│   ├── Citation.tsx             # Citation chip with preview
│   └── TraceView.tsx            # Expandable trace panel
├── lib/
│   ├── auth.ts                  # Auth configuration
│   ├── sse.ts                   # SSE client with backoff
│   ├── store.ts                 # Zustand state
│   └── types.ts                 # TypeScript definitions
└── tests/e2e/
    └── chat.spec.ts             # Playwright E2E tests
```

### SSE Streaming

The chat uses Server-Sent Events for real-time streaming:

```typescript
// lib/sse.ts - Reconnecting SSE client
const client = new ReconnectingSSEClient(
  "/v1/chat/stream",
  {
    maxRetries: 3,
    initialDelay: 1000,
    maxDelay: 30000,
  },
  {
    onToken: (token) => appendToken(token),
    onCitation: (citation) => addCitation(citation),
    onTrace: (trace) => setTrace(trace),
    onDone: () => setLoading(false),
    onError: (error) => setError(error),
  }
);
```

### Testing

```bash
# Run E2E tests
npm run test:e2e

# Run with headed browser
npm run test:e2e -- --headed

# Run specific test
npm run test:e2e -- -g "should stream"
```

---

## Ops UI

### Features

- **Dashboard**: Grafana panel embeds for latency, throughput, error rates
- **Eval Runs**: List and monitor evaluation runs with metrics
- **Actions**: Trigger DAGs and operational tasks
- **Navigation**: Sidebar with section links

### Technology Stack

- Next.js 15 (App Router)
- TypeScript
- Tailwind CSS
- NextAuth.js (authentication)

### Quick Start

```bash
cd frontends/ops-ui
npm install
npm run dev
```

Open [http://localhost:3001](http://localhost:3001)

### Environment Variables

Create `.env.local`:

```env
# API Configuration
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_GRAFANA_URL=http://localhost:3002

# Grafana Dashboard IDs
NEXT_PUBLIC_GRAFANA_DASHBOARD_LATENCY=vesper-latency
NEXT_PUBLIC_GRAFANA_DASHBOARD_THROUGHPUT=vesper-throughput
NEXT_PUBLIC_GRAFANA_DASHBOARD_ERRORS=vesper-errors
NEXT_PUBLIC_GRAFANA_DASHBOARD_EVALS=vesper-evals

# Authentication (Cognito OIDC)
COGNITO_ISSUER=https://cognito-idp.us-east-1.amazonaws.com/us-east-1_XXXXX
COGNITO_CLIENT_ID=your-ops-client-id
COGNITO_CLIENT_SECRET=your-ops-client-secret
NEXTAUTH_URL=http://localhost:3001
NEXTAUTH_SECRET=your-nextauth-secret
```

### Architecture

```
ops-ui/
├── app/
│   ├── api/
│   │   ├── auth/[...nextauth]/  # NextAuth.js handler
│   │   └── trigger-dag/         # DAG trigger endpoint
│   ├── actions/page.tsx         # Operational actions
│   ├── evals/page.tsx           # Evaluation runs
│   ├── globals.css              # Tailwind styles
│   ├── layout.tsx               # Root layout
│   ├── page.tsx                 # Dashboard
│   └── providers.tsx            # Context providers
├── components/
│   ├── GrafanaPanel.tsx         # Iframe embed wrapper
│   ├── MetricCard.tsx           # KPI display card
│   └── Sidebar.tsx              # Navigation sidebar
├── lib/
│   ├── auth.ts                  # Auth configuration
│   └── types.ts                 # TypeScript definitions
└── tests/e2e/
    └── ops.spec.ts              # Playwright E2E tests
```

### Dashboard Panels

The dashboard embeds Grafana panels for key metrics:

| Panel         | Metric          | Threshold |
| ------------- | --------------- | --------- |
| Latency (p95) | Response time   | < 2.5s    |
| Throughput    | Requests/second | -         |
| Error Rate    | 4xx/5xx %       | < 1%      |
| Faithfulness  | Eval score      | >= 0.9    |

### DAG Triggers

Available operational actions:

| DAG                      | Description                 |
| ------------------------ | --------------------------- |
| `nightly_evaluation_dag` | Run evaluation pipeline     |
| `sec_filing_ingestion`   | Ingest new SEC filings      |
| `embedding_backfill_dag` | Backfill embeddings         |
| `reembed_subset`         | Re-embed specific documents |

---

## Authentication

Both UIs use AWS Cognito via NextAuth.js OIDC provider.

### User Pools

| Pool             | Audience  | Permissions          |
| ---------------- | --------- | -------------------- |
| `vesper-analyst` | Analysts  | Chat, view citations |
| `vesper-ops`     | Operators | All + admin actions  |

### JWT Claims

```json
{
  "sub": "user-uuid",
  "email": "user@example.com",
  "cognito:groups": ["analysts"],
  "custom:tenant_id": "tenant-123"
}
```

The `tenant_id` claim is extracted and passed to the API via `X-Tenant-ID` header.

---

## Deployment

### Docker

```bash
# Build Analyst UI
docker build -t vesper-analyst-ui:latest ./frontends/analyst-ui

# Build Ops UI
docker build -t vesper-ops-ui:latest ./frontends/ops-ui
```

### Kubernetes / ECS

See `infrastructure/terraform/modules/compute/` for ECS task definitions.

### Vercel / Netlify

Both apps are compatible with edge deployment:

```bash
cd frontends/analyst-ui
npx vercel
```

---

## Development

### Local Setup

1. Start the API Gateway:

   ```bash
   docker compose up -d api-gateway
   ```

2. Start the Analyst UI:

   ```bash
   cd frontends/analyst-ui
   npm install
   npm run dev
   ```

3. Start the Ops UI:
   ```bash
   cd frontends/ops-ui
   npm install
   npm run dev
   ```

### Code Style

- ESLint + Prettier configured
- TypeScript strict mode
- Tailwind CSS for styling

```bash
npm run lint
npm run typecheck
npm run format
```

---

## Troubleshooting

### SSE Connection Issues

If streaming doesn't work:

1. Check CORS configuration in API Gateway
2. Verify `NEXT_PUBLIC_API_URL` is correct
3. Check browser console for connection errors
4. Ensure API is running and healthy

### Authentication Errors

1. Verify Cognito configuration in `.env.local`
2. Check `NEXTAUTH_SECRET` is set
3. Ensure callback URLs are registered in Cognito

### Grafana Panels Not Loading

1. Check `NEXT_PUBLIC_GRAFANA_URL` is accessible
2. Verify Grafana allows iframe embedding
3. Check dashboard IDs match actual dashboards
