# Hackuna Matata — Learn Different (GDG AI Hack 2026)

> **Track:** *Learn Different* — partner: **Braynr**.
> A study companion that scaffolds the **process** of learning, not the **output** at the end of it.

---

## 0. TL;DR

We built a full-stack web app that:

1. **Ingests** any study artifact (PDF / PPTX / Markdown / audio / video) and produces a **hierarchical, source-traceable index** with adaptive depth (chapters → sections → subsections → paragraphs).
2. **Generates** flashcards, multiple-choice or open questions on a single section, on a multi-section selection, or on the whole document, at three difficulty levels.
3. **Evaluates** the student's response — text **or** audio — through a **three-dimensional rubric** (completezza / correttezza / elaborazione) that diagnoses *what kind* of misunderstanding occurred and routes to the right scaffolding move.
4. **Drives the learning loop**: hint + source redirect, modality switch, full redirect, advance — and **never shows a numerical score**.
5. **Wraps it in a reading UI** that mirrors how students actually study: a live index sidebar with hierarchical numbering, a scroll-tracked breadcrumb, a persistent 5-color highlighter and a keyword-bolding tool, a friendly chat panel for collaborative study, and a popup-driven assessment flow.

The whole thing is one repository with three Python LangGraph/LangChain agents, a FastAPI backend, a React + TypeScript frontend, and Postgres as the artifact store.

---

## 1. Setup

### 1.1 Prerequisites

- **Python 3.11+** (we test on 3.13)
- **Node.js 18+** with `npm`
- **Docker** (for Postgres) — or any local Postgres on `:5432`
- A **Google AI Studio** API key with access to `gemini-2.5-flash`

### 1.2 Clone and configure

```bash
git clone <repo-url> hackuna-matata
cd hackuna-matata

# Top-level .env (read by backend + agents)
echo "GOOGLE_API_KEY=YOUR_KEY_HERE" > .env
# Optional: override the model
# echo "AGENT_GEMINI_MODEL=gemini-2.5-flash" >> .env
```

### 1.3 Database (Postgres via Docker)

```bash
cd backend
docker compose up -d   # starts Postgres on localhost:5432, user/pass admin/admin
```

The backend creates its tables at startup via SQLAlchemy `create_all`. No migrations needed for the demo.

### 1.4 Python environment

From the **repository root**:

```bash
python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1
# macOS / Linux
source .venv/bin/activate

pip install -r backend/requirements.txt
```

`backend/requirements.txt` is intentionally a superset — it lists FastAPI/SQLAlchemy plus every agent's deps (LangGraph, LangChain, PyMuPDF, python-pptx, markdown-it, faster-whisper, lingua, …). At hackathon speed we preferred one fat venv over per-agent installs.

> **GPU note.** `faster-whisper` is much faster on CUDA. If you want GPU inference, install Torch + Torchaudio CUDA wheels yourself before the `pip install` above; otherwise it runs on CPU.

### 1.5 Backend

From `backend/`:

```bash
uvicorn main:app --reload --reload-dir . --reload-dir ../eval_agent --reload-dir ../quiz_creation_agent --reload-dir ../processing_agent
```

The extra `--reload-dir` flags matter: changes to the agent packages outside `backend/` are *not* picked up by default `--reload`. The first call into any agent pays a one-shot warm-up cost (≈30–60 s) for LangGraph + Lingua imports; subsequent calls reuse the cached graph.

The backend is then on `http://localhost:8000` with the auto-generated docs at `/docs`.

### 1.6 Frontend

```bash
cd frontend/Hackuna-Matata
npm install
npm run dev
```

Dev server on `http://localhost:5173`. By default the frontend calls `http://localhost:8000`. Open it, click **+ Create new session**, give the subject a name, drag a PDF in, confirm — the document is indexed in the background and ready when you click on it.

---

## 2. What we built

The project is organized around **three LangGraph agents**, glued to a FastAPI backend, served to a React frontend.

```
hackuna-matata/
├── processing_agent/        # Part 2: ingest → hierarchical index.json
├── quiz_creation_agent/     # Part 3a: index.json + node_id → assessment items
├── eval_agent/              # Part 3b: response → rubric → conversational intervention
│
├── backend/                 # FastAPI + SQLAlchemy + Postgres
│   ├── controller/          # HTTP routes (group / subject / material / agent)
│   ├── service/             # Orchestration; agentService imports the 3 agents
│   ├── repository/          # SQLAlchemy CRUD
│   ├── model/               # ORM models (User, Group, Subject, Material, MaterialArtifact)
│   ├── database.py          # Engine + SessionLocal
│   ├── docker-compose.yaml  # Postgres
│   └── main.py              # Lifespan (seed defaults, prewarm agents, env summary)
│
├── frontend/Hackuna-Matata/ # React 19 + Vite + TypeScript
│   └── src/
│       ├── components/      # MaterialReader, IndexTree, QuizModal, QuizPlayer, ChatPanel, …
│       ├── pages/           # HomePage with sidebar/reader composition
│       ├── services/        # axios clients (subjectApi, materialApi, agentApi)
│       └── utils/           # Tree linearisation, numbering, picker flattening
│
├── data/                    # Sample materials and trace fixtures
└── REPORT_agents.md         # Strategic / cognitive-design report (jury-facing)
```

### 2.1 The three agents in one screen

```
   PDF / PPTX / MD / audio / video
                 │
                 ▼
   ┌─────────────────────────────┐
   │  processing_agent           │  format-polymorphic parser
   │  (LangGraph, adaptive depth)│  → IndexOutput (tree + locators)
   └─────────────┬───────────────┘
                 │  index.json + node_id(s)
                 ▼
   ┌─────────────────────────────┐
   │  quiz_creation_agent        │  3 prompt families × 3 difficulties
   │  (extractor + generator)    │  → QuizOutput (flashcard / mcq / qa)
   └─────────────┬───────────────┘
                 │  AssessmentItem (via eval_agent.bridge)
                 ▼
   ┌─────────────────────────────┐
   │  eval_agent                 │  judge → routing → intervention
   │  (text + paralinguistic)    │  → TraceEvent (one per turn)
   └─────────────┬───────────────┘
                 ▼
       Cognitive trace store
```

### 2.2 Persistence model

Postgres holds the chain of artifacts so every step is reproducible and queryable. The schema is intentionally narrow:

- `users / groups / subjects / materials` — classroom-shaped containers
- `material_artifacts` — one row per agent output, typed by an `ArtifactType` enum:
  - `INDEX` → processing_agent payload
  - `QUIZ` → quiz_creation_agent payload (with `metadata.requested_node_ids`)
  - `TRACE` → eval_agent per-turn event

**Why this shape**: a session log is the natural substrate for everything downstream — analytics, spaced repetition, profile refinement. Building it as a flat append-only table from day one means we don't have to migrate anything when those features land.

---

## 3. Cognitive design — what governs every choice

The track penalises **eduslop**: AI that optimises *outputs* (passed tests, generated answers) without producing *outcomes* (genuine understanding). Three corollaries shaped every decision in the codebase.

### 3.1 No score is shown to the student

Anywhere. Not a 0–10, not a letter grade, not a dimension label, not a JSON. The rubric is **the agent's compass, never the student's grade**. Numerical grading collapses cognitively distinct cases into the same number and turns a learning interaction into an evaluation event.

> Practically: when a session ends, the user sees a textual three-line recap (e.g., *"Completeness: good · Correctness: partial · Reformulation: good"*) — and never a percentage.

### 3.2 Source-centric traceability is non-negotiable

Every artifact — index node, assessment item, judgment — traces back to a precise position in the original material. This is what makes "shortcuts structurally useless": the only path through the material is one that requires the user to construct meaning from it.

> Practically: every leaf paragraph carries a `SourceLocator` (page range for PDFs, slide indices for PPTX, char offsets for MD, time ranges for audio); every quiz item carries a `SourceRef` linking to a `node_id`; every error in eval triggers a redirect that quotes the source paragraph and points at it.

### 3.3 Process is observable, not just inferable

Hesitations, self-corrections, reformulations — these are signals of what is happening cognitively, not noise to be cleaned away. A system that ignores them collapses back into output-grading.

> Practically: `eval_agent.paralinguistic` extracts filler density, self-correction patterns, thinking pauses and reformulation events from Whisper output. These features are passed to the rubric judge with explicit instructions on weighting; they primarily affect the **elaborazione** dimension. A textbook-perfect typed answer is `riportata` (reporting); the same answer spoken with productive friction is `rielaborata` (reworking). **Process is literally audible** in ways it isn't visible in text — and that is the single biggest piece of "frame innovation" in the system.

### 3.4 Decisions that follow from the frame

| Decision | Why |
|---|---|
| **Adaptive depth (2–4 levels)** in the index, not forced 4-level hierarchy | Cosmetic structure (output) without backing in the material is exactly the kind of thing the frame penalises. |
| **Semantic paragraphs as leaves**, not typographic blocks | The leaf is the grain of every downstream cognitive operation (assessment, redirect). Wrong grain = degraded operations. |
| **Source-preservation rule**: agent never summarises | If we summarise at index time, the assessment assesses *our summary*, not the user's *actual* material — leaking content into the agent and short-circuiting the elaboration the student is supposed to perform. |
| **Three-dimensional rubric for open questions** | A monolithic score collapses cognitively distinct cases. *Completezza/correttezza* capture *what* is said; **elaborazione** captures *how* — and "how" is where process-vs-output becomes operationally measurable. |
| **Hint + source redirect always combined** on completeness errors | A hint without source pushes the student to invent. A redirect without hint pushes them to re-read passively. Together they scaffold *productive struggle*. |
| **Two-strikes rule**: after the second wrong attempt, full source redirect | Forcing a third attempt is frustration, not productive struggle. Frustration → avoidance, not learning. |
| **Cognitive trace as event-per-turn**, not session summary | Events are the source of truth; summaries are computed from them at read time. Matches Braynr's existing architecture. |

The longer-form jury-facing version of this argument lives in [`REPORT_agents.md`](REPORT_agents.md).

---

## 4. Architecture and design motives

### 4.1 Why three agents, not one

Each agent has a different cognitive job and a different failure mode:

- **Indexing** is a *parsing* problem: must be deterministic where possible (structured PDFs, PPTX, MD), LLM-driven only where unavoidable (raw notes, ASR transcripts). Errors here corrupt every downstream agent.
- **Quiz creation** is a *constrained-generation* problem: prompts must forbid rewriting and bias, and difficulty must be calibrated.
- **Evaluation** is a *judgment + routing* problem: prompt-sensitive in a way no other component is, and the only one with a hard pedagogical contract.

Splitting them gives each one its own LangGraph topology, its own prompt family, its own validation surface.

### 4.2 Why in-process imports instead of HTTP

The backend imports the agent packages in-process (`from processing_agent.orchestrator import index_document`, etc.). Trade-offs we made consciously:

- ✅ **Zero serialisation overhead** for tree payloads that can be tens of KB.
- ✅ **One venv** to install, one process to log.
- ✅ **Trivial debugging** — any exception in any agent shows up in the same Python traceback as the FastAPI handler.
- ❌ The agents are not independently deployable. We're fine with that for a 24h hackathon; it's an explicit migration target post-event.

`backend/service/agentService.py` is the only place that knows about the agent packages — every controller goes through it, so swapping to HTTP later is a one-file change.

### 4.3 Why the multi-node quiz path concatenates raw text

The frontend lets the user pick a single section, multiple sections, or the whole document for a quiz. The backend handles the three cases on a single endpoint with explicit branches:

- **One node** → existing path: write `index.json` to a temp file and call the agent with `node_id=...`. Source-ref stays rich (label, locator).
- **Multiple nodes** → ancestor-deduplicate the selection, concatenate the leaf text of survivors, write to a temp `.txt`, call the agent without a node_id. Source-ref is partial — accurate for a multi-section quiz, since there's no single anchor to point at.

`eval_agent.bridge` accepts items with no `node_id` by falling back to a synthetic `merged:<item_id>` id and to a paragraph excerpt for the locator summary, so the eval still works end-to-end and the source redirect on errors remains useful (the student gets a quoted paragraph instead of a precise page anchor).

### 4.4 Why the frontend is structured the way it is

The reading view is a three-pane layout that mirrors how a student actually reads:

- **Left:** the index — both as a navigation aid and as a hierarchical map ("where am I?"). The tree is rendered with **automatic numbering** in the format `1.1.I.a` (arabic / arabic / roman / lowercase letters) so a section reference is unambiguous in the tutor's messages and the chat. Clicking a node scrolls the reader; scrolling the reader updates which node is highlighted in the tree, in sync.
- **Center:** the document itself, rendered as long-form HTML with inline numbering. A live breadcrumb above ("Currently reading: 2.1.II Heading") tracks scroll position via `IntersectionObserver`-like logic, so the student never wonders where they are. This is also what feeds the auto-detected `targetNode` for assessments.
- **Right:** a chat panel (cosmetic in the demo, but architecturally a placeholder for collaborative-study features) plus the **Tools** column with two functional buttons (Highlight, Keywords) and four placeholders for next iteration (Study-map, Notes, Podcast, Image), all sitting above the green **Test my knowledges** CTA.

Two design choices deserve a separate paragraph:

#### Highlight + Keywords as a "real" highlighter

We didn't fake the highlighter. The reader is a `contentEditable` element with all input events blocked (`onBeforeInput`, `onPaste`, `onDrop`, filtered `onKeyDown`) — the user can **select** text but never **edit** it. We then drive the actual annotation through `document.execCommand('hiliteColor', …)` and `document.execCommand('bold')`, the native browser APIs, and persist each annotated paragraph's `innerHTML` in `localStorage` keyed by material id. Highlights and bolded keywords **survive page reloads, navigation, and scrolling** — which is what the user expects from a real highlighter.

The toolbar exposes 5 colors plus an eraser (transparent fill), and **Keywords** is a "classic highlighter pen" mode: clicking it with text selected bolds the selection; clicking it with no selection enables a click-to-bold mode where each clicked word toggles bold.

#### The QuizModal multi-select with cascading

The assessment popup has a **scope picker** that's a tree-aware multi-select with **cascading** behavior: ticking a section auto-selects every paragraph below it; partial subtree selections render an HTML *indeterminate* checkbox. "All document" is just the root entry — selecting it cascades the whole tree. Backend ancestor-deduplicates so passing `[section, paragraph_in_section]` produces the same result as passing `[section]` alone.

### 4.5 Why we hand-rolled small things

A few places where we stayed close to the metal on purpose:

- **Hierarchical numbering** is computed once on the React side (`computeNumbering(tree)` in `utils/treeWalk.ts`) and threaded through `IndexTree`, `MaterialReader` and the QuizModal picker. One source of truth, no per-component re-walks.
- **Tree linearisation for the reader** (`linearizeTree`) is its own utility — keeps `MaterialReader` purely a renderer.
- **Annotation persistence** uses `innerHTML` snapshots per item, restored via `dangerouslySetInnerHTML` on mount. We rejected fancier "ranges + offsets" approaches because they're brittle when the underlying tree is regenerated (e.g., by the *Add sources* flow).

---

## 5. Notable single decisions

### 5.1 Whisper `medium` multilingual, not language-specific Italian fine-tunes

We evaluated FAMA (FBK) and `distil-whisper-it` (bofenghuang). They gain ~3–5 WER points on Italian but force two pipelines, two models in memory, and a routing layer. We accept the gap to keep the audio path clean — and the LLM cleaning step downstream absorbs most of the difference.

### 5.2 Gemini 2.5 Flash, not Pro

Free tier on Google AI Studio. The free quota is small (~20 calls/day on Flash) but enough to demo, and Flash's quality is sufficient for our prompts (constrained generation, structured output, brief judgments).

### 5.3 `--reload-dir` for the agent dirs

Default `uvicorn --reload` only watches the directory it's launched from. Changes to `eval_agent/` etc. are silently missed. We document the explicit incantation above; we'd like to wrap it in a `make dev` (see §7).

### 5.4 Add-sources merge with `s<N>_` node-id remap

The "+ Add sources" button on the index sidebar appends a freshly-indexed file to the existing material. The backend remaps every node_id of the new tree to a unique `s2_…` (or `s3_…`) prefix, wraps the new tree in a synthetic chapter, and appends. Hierarchical numbering picks it up automatically because the new chapter is just "the next sibling at the root level".

### 5.5 Multi-node text concatenation with ancestor dedup

If the user picks both a section and one of its paragraphs, the agent would otherwise see the same text twice. We resolve every selected id, then drop any id whose ancestor is also in the selection — which is the right semantics ("the ancestor already covers this content").

---

## 6. What we explicitly did not build, and why

A short list, because it matters for honest evaluation:

- **Onboarding profiling quiz** (Part 1). Designed (R-SPQ-2F + MSLQ subscales + Need for Cognition → 4–6-D profile vector), but deprioritised. The cognitive-design budget pointed at the components that make direct contact with the user's behaviour. A poorly-designed Part 1 leaks bad signal into Parts 2–3 and is hard to extract.
- **Cross-file knowledge integration** in indexing. One file → one index. Cross-file alignment is a doctoral-thesis problem in 24h. *Add sources* is the closest substitute, and it's enough for the demo.
- **Human-in-the-loop refinement** of the index. We didn't want the agent to become a co-author of the structure; we wanted the structure to come from the material.
- **OCR for scanned PDFs**. Out of scope. Scanned PDFs fail loudly with an explicit error rather than silently producing garbage.
- **A "show the correct answer" path** in eval. Even on the second strike, we redirect to the source — never reveal. This is the strongest commitment to source-centricity we could make.
- **Score display anywhere**. Ruled out by principle, not cut for time.

---

## 7. What we'd do with another week

Roughly in priority order:

1. **Wire the four placeholder Tools buttons.** Study-map (concept map from the index), Notes (markdown notepad with autosave), Podcast (TTS readback of selected sections), Image (visual mnemonic generation per concept). The architecture already supports them — they're frontend buttons + new `agent` endpoints.
2. **Profiling quiz (Part 1) MVP.** R-SPQ-2F + MSLQ subscales as a Likert form, deterministic scoring, LLM only for narrative interpretation. Profile vector flows into the eval rubric judge ("deep approach" → stricter on `elaborazione`).
3. **Spaced repetition over the cognitive trace.** `concept_status_after = "fragile"` is already emitted by eval; a small scheduler component would turn that into a "review queue" overlay on the next session.
4. **Real chat backend.** The chat panel is currently a cosmetic mock. Full collaborative study would back it with WebSockets and let two students share an annotation layer over the same material.
5. **Cross-file index aggregation.** A *Subject* would have a single navigable index combining all its materials, with cross-document concept linking by semantic similarity on leaf paragraphs.
6. **OCR for scanned PDFs.** A `--ocr` switch that routes through Tesseract or Google Vision before the parser. Probably half a day; we just didn't have it.
7. **Tighten the `(unknown location)` UX in multi-section quizzes.** The bridge already falls back to a paragraph excerpt; we'd extend the merge metadata so `quiz_creation_agent` can attach a `source_label` like *"Sections 2.1 + 3.4"* even on the raw-text path.
8. **GPU detection auto-config.** Right now the user has to install Torch CUDA wheels manually. A startup probe could detect the env and skip the warning.
9. **End-to-end tests** with fixture audio responses against the rubric judge. The eight hand-crafted fixtures we used during prompt development are still the only safety net there.
10. **Deploy.** Containerise both halves, drop on Fly.io / Render with managed Postgres, rotate API keys properly.

---

## 8. References

- [`REPORT_agents.md`](REPORT_agents.md) — long-form, jury-facing technical writeup with the full cognitive-design argument.
- `processing_agent/`, `quiz_creation_agent/`, `eval_agent/` — each agent has its own CLI (`python -m <agent>.cli --help`) for standalone testing.
- backend API routes: `http://localhost:8000/api/v1/…` (see `backend/controller/` for the full list).
- frontend: open dev server on `http://localhost:5173`, inspect React components with React DevTools, watch API calls in the Network tab.
- API docs: with the backend running, `http://localhost:8000/docs`.

---

*Built in 24 hours during GDG AI Hack 2026. Track: Learn Different. Partner: Braynr.*
