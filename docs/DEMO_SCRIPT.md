# VESPER Demo Script

Step-by-step demo script with exact prompts and expected citations.

## Prerequisites

Before running the demo:

```bash
# 1. Start the local environment
docker-compose up -d

# 2. Seed demo data
python scripts/demo_seed.py

# 3. Warm the cache
python scripts/cache_warmers.py --persist

# 4. Verify data is loaded
curl http://localhost:8000/health
```

## Demo Flow Overview

| Step                   | Duration | Focus Area              |
| ---------------------- | -------- | ----------------------- |
| 1. Introduction        | 2 min    | Platform overview       |
| 2. Basic Queries       | 5 min    | Single-company analysis |
| 3. Cross-Company       | 5 min    | Comparative analysis    |
| 4. Citations Deep-Dive | 5 min    | Evidence tracking       |
| 5. Conflict Detection  | 5 min    | Self-healing features   |
| 6. Ops Dashboard       | 3 min    | Monitoring capabilities |
| 7. Wrap-up             | 2 min    | Q&A                     |

---

## Step 1: Introduction (2 min)

### Opening Statement

> "Welcome to VESPER - the Verifiable Evidence-grounded Semantic Processing and Extraction Runtime. Today I'll show you how VESPER provides production-grade AI analysis with full citation tracking and self-healing capabilities."

### Key Points to Mention

- [ ] Evidence-grounded answers with citations
- [ ] Multi-tenant architecture
- [ ] Self-healing observability
- [ ] Production-ready security

---

## Step 2: Basic Queries (5 min)

### Query 2.1: Financial Performance

**Prompt:**

```
What was Apple's total revenue for fiscal year 2024?
```

**Expected Response:**

> Apple Inc. reported total revenue of $394.3 billion for fiscal year 2024, representing an 8% increase year-over-year.

**Expected Citations:**

| Citation ID        | Filing         | Section               | Confidence |
| ------------------ | -------------- | --------------------- | ---------- |
| `cit_aapl_fin_001` | AAPL-10-K-2024 | Financial Performance | 0.95+      |

**Talking Points:**

- Point out the citation badge
- Click to expand citation source
- Show the exact text span highlighted

---

### Query 2.2: Risk Factors

**Prompt:**

```
What are the main risk factors for Amazon?
```

**Expected Response:**

> Amazon faces several key risks including: (1) Intense competition in the Internet Retail market, (2) Regulatory changes affecting data privacy and international trade, (3) Supply chain disruptions, (4) Cybersecurity threats, and (5) Economic uncertainty affecting consumer spending.

**Expected Citations:**

| Citation ID         | Filing         | Section      | Confidence |
| ------------------- | -------------- | ------------ | ---------- |
| `cit_amzn_risk_001` | AMZN-10-K-2024 | Risk Factors | 0.93+      |

---

### Query 2.3: Business Strategy

**Prompt:**

```
What is Microsoft's Azure strategy?
```

**Expected Response:**

> Microsoft's strategy focuses on expanding Azure and AI services, leveraging the OpenAI partnership. The Intelligent Cloud segment shows strong enterprise cloud adoption driving growth.

**Expected Citations:**

| Citation ID        | Filing         | Section                 | Confidence |
| ------------------ | -------------- | ----------------------- | ---------- |
| `cit_msft_bus_001` | MSFT-10-K-2024 | Business Overview       | 0.91+      |
| `cit_msft_mda_001` | MSFT-10-K-2024 | Management's Discussion | 0.88+      |

---

## Step 3: Cross-Company Analysis (5 min)

### Query 3.1: Revenue Comparison

**Prompt:**

```
Compare revenue growth across AAPL, AMZN, and MSFT
```

**Expected Response:**

> Revenue growth comparison for fiscal 2024:
>
> - **Apple (AAPL)**: $394.3B, +8% YoY
> - **Amazon (AMZN)**: $574.8B, +12% YoY
> - **Microsoft (MSFT)**: $236.6B, +16% YoY
>
> Microsoft showed the strongest percentage growth driven by Azure and AI services.

**Expected Citations:**

| Citation ID        | Filing         | Section               | Confidence |
| ------------------ | -------------- | --------------------- | ---------- |
| `cit_aapl_fin_001` | AAPL-10-K-2024 | Financial Performance | 0.94       |
| `cit_amzn_fin_001` | AMZN-10-K-2024 | Financial Performance | 0.93       |
| `cit_msft_fin_001` | MSFT-10-K-2024 | Financial Performance | 0.95       |

**Talking Points:**

- Show how multiple filings are cited
- Each claim links to specific source
- Highlight the comparison table formatting

---

### Query 3.2: Operating Margin Comparison

**Prompt:**

```
Compare operating margins: Apple vs Microsoft
```

**Expected Response:**

> Operating margin comparison:
>
> - **Apple**: 29% operating margin
> - **Microsoft**: 42% operating margin
>
> Microsoft's higher margin reflects its software-focused business model with recurring subscription revenue.

**Expected Citations:**

| Citation ID        | Filing         | Section               | Confidence |
| ------------------ | -------------- | --------------------- | ---------- |
| `cit_aapl_fin_002` | AAPL-10-K-2024 | Financial Performance | 0.92       |
| `cit_msft_fin_002` | MSFT-10-K-2024 | Financial Performance | 0.94       |

---

## Step 4: Citations Deep-Dive (5 min)

### Demonstrating Citation Features

**Prompt:**

```
What was Apple's earnings per share in 2024?
```

**Expected Response:**

> Apple's earnings per share (EPS) was $6.16 for fiscal year 2024.

**Demo Actions:**

1. **Click the citation badge** → Shows source panel
2. **Expand "View Source"** → Shows exact text from filing:
   ```
   Earnings Per Share: $6.16
   ```
3. **Click "Open Filing"** → Opens PDF viewer at exact location
4. **Show provenance trail** → Filing → Section → Chunk → Sentence

**Screenshot Opportunity:** 📸 Citation panel with highlighted source

---

### Citation Confidence Levels

Explain the confidence scoring:

| Confidence | Color     | Meaning                                 |
| ---------- | --------- | --------------------------------------- |
| 0.90+      | 🟢 Green  | High confidence, direct match           |
| 0.75-0.90  | 🟡 Yellow | Good confidence, semantic match         |
| 0.50-0.75  | 🟠 Orange | Moderate confidence, review suggested   |
| < 0.50     | 🔴 Red    | Low confidence, multiple sources needed |

---

## Step 5: Conflict Detection (5 min)

### Query 5.1: Trigger Conflict Panel

**Prompt:**

```
What regulatory changes affect the tech sector?
```

**Expected Response:**

> Regulatory changes affecting tech companies include data privacy requirements, antitrust concerns, and international trade policies.
>
> ⚠️ **Potential Conflict Detected**: Multiple filings discuss regulatory impacts differently.

**Demo Actions:**

1. **Click conflict indicator** → Opens conflict panel
2. **Show conflicting statements:**
   - AAPL mentions EU regulations primarily
   - AMZN emphasizes antitrust scrutiny
   - MSFT focuses on data privacy
3. **Demonstrate resolution options:**
   - View all sources
   - Request clarification
   - Mark as reviewed

**Screenshot Opportunity:** 📸 Conflict detection panel

---

### Self-Healing Demonstration

**Talking Points:**

- System detects when sources disagree
- Automated alerts to ops team
- Tracks resolution over time
- Prevents hallucination propagation

---

## Step 6: Ops Dashboard (3 min)

### Navigate to Ops Dashboard

Open: `http://localhost:3001`

### Key Metrics to Show

1. **System Health Panel**

   - API latency: p95 < 2.5s ✅
   - Error rate: < 1% ✅
   - Cache hit rate: > 80% ✅

2. **Evaluation Metrics**

   - Faithfulness: 0.92 ✅
   - Hallucination rate: 0.8% ✅
   - Citation accuracy: 94% ✅

3. **Recent Alerts**
   - Show self-healing in action
   - Drift detection alerts
   - Auto-remediation logs

**Screenshot Opportunity:** 📸 Grafana dashboard with all green metrics

---

### Trace Viewer

**Demo Actions:**

1. Click on a recent query in the trace list
2. Show the distributed trace:
   - API Gateway → Retrieval → LLM → Response
3. Point out latency breakdown
4. Show token usage metrics

**Screenshot Opportunity:** 📸 Distributed trace view

---

## Step 7: Wrap-up (2 min)

### Summary Points

> "In this demo, you've seen how VESPER:
>
> 1. ✅ Provides evidence-grounded answers with citations
> 2. ✅ Enables cross-company comparative analysis
> 3. ✅ Detects and surfaces conflicting information
> 4. ✅ Offers production-grade observability
> 5. ✅ Self-heals when issues are detected"

### Next Steps

- [ ] Schedule technical deep-dive
- [ ] Discuss domain customization (healthcare, legal, etc.)
- [ ] Review security and compliance requirements
- [ ] Plan pilot deployment

---

## Troubleshooting

### Demo Not Working?

| Issue              | Solution                              |
| ------------------ | ------------------------------------- |
| No data returned   | Run `python scripts/demo_seed.py`     |
| Slow responses     | Run `python scripts/cache_warmers.py` |
| Connection refused | Check `docker-compose up -d`          |
| Auth errors        | Use demo tenant: `X-Tenant-ID: demo`  |

### Reset Demo Environment

```bash
# Full reset
docker-compose down -v
docker-compose up -d
python scripts/demo_seed.py
python scripts/cache_warmers.py --persist
```

---

## Appendix: All Demo Queries

Quick reference for all 20 demo queries:

| ID  | Query                                                   | Expected Ticker |
| --- | ------------------------------------------------------- | --------------- |
| q01 | What was Apple's total revenue for fiscal year 2024?    | AAPL            |
| q02 | What are the main risk factors for Amazon?              | AMZN            |
| q03 | What is Microsoft's operating margin?                   | MSFT            |
| q04 | Compare revenue growth across AAPL, AMZN, and MSFT      | ALL             |
| q05 | What are Apple's main business segments?                | AAPL            |
| q06 | How much cash does Microsoft have on its balance sheet? | MSFT            |
| q07 | What is Amazon's strategy for AWS growth?               | AMZN            |
| q08 | What was Apple's earnings per share in 2024?            | AAPL            |
| q09 | What cybersecurity risks does Amazon face?              | AMZN            |
| q10 | How much did Microsoft return to shareholders?          | MSFT            |
| q11 | What are Apple's AI and machine learning initiatives?   | AAPL            |
| q12 | What is Amazon's quarterly segment breakdown?           | AMZN            |
| q13 | What is Microsoft's Azure strategy?                     | MSFT            |
| q14 | What supply chain risks affect Apple?                   | AAPL            |
| q15 | What was Amazon's free cash flow?                       | AMZN            |
| q16 | What regulatory changes affect Microsoft?               | MSFT            |
| q17 | Compare operating margins: Apple vs Microsoft           | AAPL/MSFT       |
| q18 | What leadership changes were announced?                 | ALL             |
| q19 | What is Amazon's logistics network strategy?            | AMZN            |
| q20 | What is Apple's gross margin trend?                     | AAPL            |

---

**Demo Version:** 1.0  
**Last Updated:** December 2025  
**Maintainer:** VESPER Team
