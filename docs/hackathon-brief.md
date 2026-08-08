# 🏆 AutoPilot Hackathon — Round 2 Brief

## Mission

Build an **AI Employee** — a multi-agent ecosystem that automates a real business process with human-in-the-loop oversight.

Your submission must demonstrate a working **AI Command Center** with live orchestration, policy enforcement, exception handling, and performance insights.

---

## ⚠️ MANDATORY: Agent Platform Requirement

> **All Orchestrator and Operator agents MUST be built on [auto.supervity.ai](https://auto.supervity.ai).**

This is a **non-negotiable requirement**. Your multi-agent orchestration — the Orchestrator that delegates tasks and the 5+ Operator agents that execute them — must be designed, configured, and run through the **Auto by Supervity** platform.

### What MUST use auto.supervity.ai:
- ✅ Orchestrator agent definition and routing logic
- ✅ All Operator agents (minimum 5)
- ✅ Agent-to-agent communication and handoffs
- ✅ Task delegation and result collection
- ✅ Multi-step workflow orchestration

### What you CAN build independently:
- ✅ AI Policies engine (use any LLM — Gemini, GPT, Claude, etc.)
- ✅ AI Insights generation pipeline (use any LLM or ML approach)
- ✅ Custom backend logic and API endpoints
- ✅ Frontend customizations and extensions
- ✅ Database schemas, business logic, integrations
- ✅ Exception handling and workbench logic

**In short:** Build your agents in Auto, build everything else however you want.

---

## What You're Building

### The AI Employee Ecosystem

Your AI Employee is a **multi-agent system** composed of:

| Component | Min Required | Purpose |
|-----------|-------------|---------|
| **Orchestrator** | 1 | The manager — routes tasks, maintains state, coordinates operators |
| **Operators** | 5 | Specialist agents — each handles one task type |
| **AI Policies** | 3+ active | Business rules that constrain agent behavior |
| **AI Workbench** | 1+ exception flow | Where humans handle what AI can't |
| **AI Insights** | Dashboard | AI-generated observations about system performance |

### The Platform Pillars

Your Command Center must include:

1. **Dashboard** — KPIs, agent status, pipeline metrics
2. **AI Manager** — Agent orchestration, task routing, context management
3. **AI Policies** — Natural language or structured business rules, evaluated at runtime
4. **AI Workbench** — Exception handling queue with human-in-the-loop
5. **AI Insights** — Pattern detection, anomaly alerts, optimization recommendations

---

## Problem Tracks


### Track 1: Sales Command Center 💼

**Scenario:** You're building an AI Employee that manages a sales pipeline — from lead intake to deal closure.

**Key Challenges:**
- Ingest leads from multiple sources and score them automatically
- Keep the CRM updated without manual data entry
- Generate personalized outreach based on lead context
- Monitor deal health and flag at-risk pipelines
- Forecast revenue based on historical patterns

**Example Agent Ecosystem:**
- Orchestrator: Sales Pipeline Manager
- Op 1: Lead Scorer (evaluates lead quality)
- Op 2: CRM Updater (syncs contact/deal data)
- Op 3: Outreach Drafter (creates personalized emails)
- Op 4: Deal Analyst (flags stalled or at-risk deals)
- Op 5: Revenue Forecaster (projects pipeline outcomes)

**Example Policies:**
- "Auto-approve CRM updates for deals under $10K"
- "Escalate enterprise leads (>500 employees) to VP"
- "Never send outreach after 6 PM recipient's time"
- "Flag deals inactive for >14 days as at-risk"

---

### Track 2: Marketing Command Center 📣

**Scenario:** You're building an AI Employee that orchestrates multi-channel content marketing — from content creation to performance analysis.

**Key Challenges:**
- Adapt one piece of content across 5+ channels (LinkedIn, Twitter, email, blog, ads)
- Maintain consistent brand voice across platforms
- Optimize posting schedules based on engagement data
- Track campaign performance holistically
- Detect trending topics and suggest timely content

**Example Agent Ecosystem:**
- Orchestrator: Campaign Manager
- Op 1: Content Adapter (multi-platform formatting)
- Op 2: Trend Analyzer (industry monitoring)
- Op 3: SEO Optimizer (keyword and metadata)
- Op 4: Social Scheduler (optimal timing)
- Op 5: Performance Tracker (cross-channel metrics)

**Example Policies:**
- "Never post content without a CTA link"
- "Cap Twitter threads at 5 tweets"
- "Require brand review for LinkedIn posts"
- "Auto-approve posts following the template format"

---

## Deliverables

### Required for Submission

1. **Working Application** — Fully functional frontend connected to your AI backend, would be preferred if deployed somewhere or also you can show on localhost
2. **Agents on Auto** — Orchestrator + 5 Operators built and running on [auto.supervity.ai](https://auto.supervity.ai)
3. **Live Demo** (5-10 minutes) showing the full flow:
   - Trigger → Orchestrator receives task (via Auto)
   - Orchestrator delegates to operators (via Auto)
   - Policies evaluated and enforced
   - Exception detected → routed to Workbench
   - Human resolves exception
   - Insights generated from execution data
4. **Code Repository** — Clean, documented codebase
5. **Architecture Diagram** — Visual overview of your agent ecosystem (showing Auto integration)

### Bonus Points

- Creative policy implementations (beyond simple IF/THEN)
- Sophisticated exception handling (multiple exception types)
- Real data integration (actual APIs, not just mock data)
- Advanced insights (ML-based pattern detection)
- Beautiful, polished UI with meaningful animations
- Advanced use of Auto's orchestration capabilities

---

## Judging Criteria

| Criteria | Weight | What Judges Look For |
|----------|--------|---------------------|
| **Agent Architecture** | 25% | Clear orchestrator-operator pattern, 5+ operators, clean delegation |
| **Policy Engine** | 20% | Dynamic policies, runtime evaluation, multiple policy types |
| **Exception Handling** | 20% | Graceful failure, context-rich workbench, human-in-the-loop |
| **Insights & Visibility** | 15% | Meaningful insights, pattern detection, actionable recommendations |
| **UI/UX & Polish** | 10% | Clean design, responsive, good user experience |
| **Innovation** | 10% | Creative solutions, novel approaches, "wow" factor |

### The Golden Rule

> **"A system that gracefully handles what it can't do is more impressive than a system that tries to do everything and fails silently."**

Judges value a well-implemented exception handling flow over an ambitious but fragile automation pipeline. Build your safety net first.

---

## Technical Guidelines

### Agent Platform: auto.supervity.ai

All agent orchestration **must** be built on [auto.supervity.ai](https://auto.supervity.ai). This is the platform where you:
- Define your Orchestrator agent with routing logic
- Create your 5+ Operator agents with distinct capabilities
- Configure agent-to-agent handoffs and communication
- Set up multi-step workflows and task delegation
- Connect agents to external tools and APIs

Your Command Center's backend will call the Auto platform APIs to trigger orchestrations, and your frontend will display the results.

### Using This Template

This repository provides:
- ✅ FastAPI backend with auth, audit, and CRUD patterns
- ✅ Next.js frontend with premium UI components
- ✅ AI Policies page (frontend only — with demo data)
- ✅ AI Insights page (frontend only — with demo data)
- ✅ AI Manager chat interface (frontend only — needs backend)
- ✅ Docker Compose for instant startup
- ✅ PostgreSQL database with migrations

You need to add:
- 🔨 **Agents on Auto** — Build orchestrator + operators on [auto.supervity.ai](https://auto.supervity.ai)
- 🔨 **Auto API integration** — Connect your backend to Auto's orchestration APIs
- 🔨 Policy evaluation engine (use any LLM — backend)
- 🔨 Exception routing to workbench (backend + frontend)
- 🔨 Insight generation pipeline (use any LLM — backend)
- 🔨 API endpoints connecting frontend to your AI logic

### LLM Choice (for Policies & Insights)

For AI Policies and AI Insights, you may use **any LLM or provider**:
- Google Gemini
- OpenAI GPT-4/4o
- Anthropic Claude
- Open source models (Llama, Mistral, etc.)
- Mix-and-match for different features

> **Remember:** LLMs power your policies and insights. **Auto** powers your agent orchestration. Don't mix these up.

### Architecture Tips

1. **Set up Auto first** — Get your agents running on auto.supervity.ai before writing backend code
2. **Start with exception handling** — Get one full exception flow working before adding complexity
3. **Use the template** — Don't rebuild the frontend from scratch; extend what's here
4. **Policies first** — Implement 3 simple policies before attempting complex ones
5. **Mock then build** — Start with hardcoded demo data, replace with real logic incrementally
6. **Document your agents** — Clear README explaining what each operator does and how they connect via Auto

---

## Timeline

| Phase | Focus |
|-------|-------|
| **First 2 hours** | Set up template, design agent architecture, define policies |
| **Hours 2-6** | Build orchestrator + first 2-3 operators, implement basic policy engine |
| **Hours 6-10** | Connect remaining operators, add workbench exception flow |
| **Hours 10-14** | Add insights, polish UI, test full demo flow |
| **Final 2 hours** | Practice demo, fix bugs, document |

---

## Resources

- **[Command Center Guide](command-center-guide.md)** — Full architecture reference
- **[Design System](design-system-template.md)** — UI component patterns
- **[Audit System Guide](Audit%20System%20Guide.md)** — Built-in audit logging
- **[README](../README.md)** — Setup, commands, project structure

Good luck! 🚀
