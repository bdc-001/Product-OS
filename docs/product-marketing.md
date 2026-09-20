# Product Marketing

Open `/marketing` under Product Marketing. The **Features** tab is the Product Marketing mastersheet (Module, Feature, Description, Use Case, Industry, plus campaign fields). It lives in the platform database and is synced with the Product Marketing Google Sheet on every platform refresh. CSV export uses the same five shared columns. Each row shows the status of every PMM content type (LinkedIn post, carousel, portrait video, YouTube Short, landscape video, article, feature brief, release notes, case study).

The live Google Sheet is [Product Marketing Automation](https://docs.google.com/spreadsheets/d/1K1iC6I8k3UL77ik7tqvLHyHcA3t0egldebrYovmiDiI/edit?usp=sharing). Override with `MARKETING_SHEET_ID` if needed. Share that spreadsheet with the Drive service-account email as Editor, and enable the Google Sheets API on the same Cloud project.

## Manual start

Campaigns are **manual**. Open a feature’s content strip, then create one type (carousel, artifact, video, release notes, case study, and the rest) or several. **Create** on a row opens the same picker; you can also let the PMM recommend formats. `POST /marketing/generate` accepts optional `formats`. Global Refresh fetches origin branches, inspects merged Sense `release/YYYY-MM-DD` branches, discovers marketable buyer capabilities into the product sheet, then writes Module / Feature / Description / Use Case / Industry back to Google. **Fetch releases** on `/marketing` runs that discovery without a full platform refresh. Neither path auto-queues production. Engineer, internal-staff and infrastructure work is skipped; small operator tools stay in.

Add features in the UI, in the Google Sheet, or seed from `data/marketing/mastersheet.csv` on first workspace load. Refresh pulls non-empty Google cells (sheet wins for those five fields), then discovery adds new released features, then the product list is pushed to Google. Saving a feature in `/marketing` also pushes the sheet. New rows get tag **New**; starting a run moves tag to **In pipeline** and sheet status to **In Progress**; successful completion sets **Done** / **Completed**.

## Central manager

`MARKETING_MODEL` defaults explicitly to `claude-opus-4-8`. The manager, specialists and editors reuse the existing Claude writing-model credentials through Settings; credentials are never rewritten. The page shows the model selected by the backend. Provider availability is required; there is no silent model fallback.

A useful use-case / description needs at least 20 characters. Priority (P1–P3) is an organizational flag. Editing and saving a brief clears its current decision and creates a new assessable revision; prior campaigns retain their snapshots. Dismissed features stay excluded.

The PMM understands the released capability and whether a Sense buyer would buy it, then returns approve, skip or defer. Engineer, developer, internal-staff and infrastructure work is skipped even when newly merged. Small operator tools such as phone-number rotation stay in. It records rationale, audience, positioning, supporting quotes, missing evidence, a CTA, and selected formats with individual angles, objectives and outlines. Every omitted format has an explanation. Approved features have at least one assignment; skipped/deferred features have none.

Available formats: LinkedIn post, LinkedIn carousel, LinkedIn portrait video, YouTube Short, YouTube landscape video, article, feature brief, release notes, case study. Selection is dynamic; the system does not generate an obligatory full kit. Requesting a single format still runs PMM editorial checks for that type only.

## Released-feature discovery

Global refresh completes code indexing and remote branch fetch before marketing assessment. Marketing uses its own checkpoints and reads `release/YYYY-MM-DD` merges into `origin/main` through the existing release detector. It does not approve or change Comms release jobs. Git release merges are the current proxy for release; they are not independent deployment evidence and the prompts prohibit claiming universal availability.

After the initial sheet has an entry, the first successful scan evaluates the latest detected release and baselines older history. Later scans assess unseen merges in the latest 300 main-branch merges. Only eligible Sense `convin-activate/` files are read; secret paths and generated/dependency directories are excluded. Diff windows retain exact source text and added lines. A discovered capability needs a quotation from changed code, not only unchanged context. Source references are pinned to immutable release commits. Large releases are processed in checkpointed windows. Unreadable or invalid evidence leaves the unfinished scan retryable.

The manager compares all existing and dismissed feature descriptions to omit semantic duplicates. A deterministic sellability gate then keeps buyer-facing Sense capabilities (including small ops tools such as DID / phone-number round-robin, campaign scheduling, activity hours, retries and warm transfer) and dismisses engineer, internal and platform-infra rows without deleting them. Normalized names and feature-revision campaign keys enforce persistence-level deduplication. Exact quotations are checked in code; semantic novelty and interpretation remain model judgments visible for review. User entries and notes are not overwritten by discovery.

## Specialist quality and design

Each selected form has a separate writing call and an independent factual/creative editorial call. Structured validation checks completeness, channel-specific length, readable text bounds, narrative structure and placeholder absence. Editorial scores require factuality 5/5 and specificity, channel fit, narrative and readability at least 4/5. The writer can repair failed content twice before the format needs attention. Generated descriptions and PMM positioning are interpretation, not additional evidence.

The design reference is `backend/app/static/artifacts/marketing-design.md`, with shared palette, Inter body type, Helvetica display typography where available, 20px panels, clear visual hierarchy and no invented statistics. Outputs include:

- Carousels: 6-8 distinct narrative slides at 1080×1350, separate PNGs, a multipage PDF and a LinkedIn caption. Each slide also names its visual treatment (statement, contrast, steps, spotlight, stat), carries one short supporting line and short diagram labels rather than sentences, and at least three treatments must appear so no single card is repeated.
- Articles: 650-950 word educational stories with structured sections, Markdown, escaped HTML and branded A4 PDF.
- Feature briefs: a visual pack rather than a document. The writer supplies a short dek, an optional stat band of real supported figures, 3-5 typed blocks (why, cards, flow, steps, comparison, panel) with a scannable lead and one sentence per item, and a CTA. At least three block kinds and one structural device are required, total copy stays between 110 and 250 words, and the Markdown deliverable is assembled from the approved pack. Exported as Markdown, HTML and A4 PDF with selectable body text.
- Videos: independent channel scripts and descriptions. LinkedIn portrait uses 10-12 scenes, Shorts 8-10, landscape launch films 10-14. Only the selected aspect is rendered. Feature-specific conversations, input stacks, connected mechanisms, contrasts, processes and kinetic statements follow the supplied Convin launch-film reference. Narration is validated as a performed script rather than a list of statements: spoken sentences average at least seven words, one line runs to eleven or more and one lands in four or fewer, and at least a third of the shots carry a comma or colon, because uniform short statements all receive the same falling contour.

The reusable Sense Communication composition lives in `Sense_Communication/remotion/src/marketing/`. It receives data-only props; model JavaScript/HTML is never executed. Existing feature-specific Sense and Billing films remain independent. Install the existing Remotion dependencies with `npm ci` if needed; Node and the bundled FFmpeg/FFprobe must be available to the backend. Generated films use the pinned Remotion motion stack (`@remotion/lottie`, `@remotion/shapes`, `@remotion/paths`, `@remotion/motion-blur`) through `src/marketing/Motifs.tsx` rather than stock animation packs.

Narration reuses configured Cartesia credentials from the reference project, with root Settings taking precedence. The whole script is one continuous take at the model's default speed, so punctuation sets the pacing; the transcript must match the caption words exactly, which rules out SSML tags or stage directions. Mac system narration is available only through an explicit local preview; production cannot silently fall back to it. Takes are measured; corrupt takes are regenerated. Edit lengths use a half-second grid with breathing room. Captions use estimated phrase timing within each measured take, not word-aligned transcription. Exports use 30fps, 1920×1080 or 1080×1920, H.264 CRF16 and AAC192k with a -16 LUFS normalization target. Resolution, duration, codec, audio presence and encoded loudness/true peak are checked before finalization; cached masters are checked again on retry. Films include thumbnail, SRT and quality report. These are branded explanatory motion graphics, not automatically recorded product UI footage.

## Queue, Drive and recovery

Every feature revision has a stable campaign key. Decisions and each format's approved copy, production state and file manifest are saved separately. A failed format does not stop other assignments; completed files still upload. Retry reuses saved copy and completed formats. A new assessment requires an edited feature revision. Skip/defer decisions are saved locally and in the database without producing content.

API refresh dispatches production to the persistent marketing queue; the page can be closed. Startup and a 30-second recovery check resume queued/interrupted stages. Cross-process locks serialize discovery and production, including scheduled CLI refreshes alongside the server. Failed/partial campaigns wait for a user retry so provider failures do not create an endless paid retry loop. An unattended in-process refresh drains pending production before exit, so its work does not depend on a daemon surviving process exit.

Drive uses `GDRIVE_ASSETS_FOLDER_ID`, falling back to `GDRIVE_FOLDER_ID`, with existing service-account credentials. Destination: existing artifact root / Product Marketing / Feature name (id) / Campaign id. Local copies live in `data/marketing/<campaign-id>/`. Each uploaded file ID is checkpointed; a stable Drive appProperty recovers uncertain create responses. No content is automatically posted to LinkedIn, YouTube, Cliq, Jira or email. Scheduled marketing storage is explicitly authorized in AGENTS.md; Comms publication and release approval remain excluded.

## Validation

From backend: `.venv/bin/python -m pytest tests/test_marketing.py tests/test_refresh_jobs.py tests/test_release_asks.py -q`.

Type-check frontend and Remotion with their local `tsc --noEmit`; run the frontend production build. Render local fixture carousels, PDFs and video compositions for visual QA without adding fixtures to the user's feature sheet or uploading them to Drive. Model quality scores are an automated gate, not a guarantee of human editorial judgment.

## Quality hardening (September 2026)

Marketing success now requires more than generation finishing:

- Manual feature assessment reads bounded implementation files from the committed product index. It preserves the source SHA and excludes planning docs, tests, scripts, secret paths and generated files. This avoids treating short search-result fragments or marketing slogans as proof.
- Discovery repairs invalid quotation responses up to twice within the same window. A failed window remains retryable while later windows can progress. Only approved capabilities enter the working roadmap; skip/defer assessments are saved under `data/marketing/discovery/`. Existing rejected rows remain available under Not selected, Needs evidence and All features / history, with their original data preserved.
- Discovery processes at most 12 new windows per invocation and checks an eight-minute budget between windows. An in-flight provider call/repair may extend that elapsed time. Budget exhaustion and a held worker lock are reported as incomplete, not successful. Global refresh reports any failed/error-bearing step in its top-level result.
- Writing is assessed for a specific buyer, actual feature mechanism and practical decision. Editors must explain why content would not work after substituting an unrelated feature name. Sibling formats are supplied to identify recycled openings, examples and narrative. Format choice remains proportional to the available evidence.
- Editorial review must cover the caption/body and every slide, scene or document section. Material assertions require actual copy quotations and exact source quotations, plus a support explanation. Generated positioning cannot serve as evidence. Passing scores with unresolved issues, omitted units or no grounded product claim are rejected. These checks validate the audit structure and quotations; semantic support remains an automated editorial judgment.
- Every rendered PDF page and entry/middle/late frames from every video shot receive visual review before the format enters the deliverable manifest. Static layout/visual defects trigger up to two automatic design revisions while preserving approved copy; exhausted design repairs fail the format without sending it back to the writer. Video render failures retain the existing copy-and-render repair path. Saved review reports distinguish sampled-frame checks from human playback review; motion, voice pronunciation and real provider reliability are not proven by local tests.
- A completed old campaign cannot overwrite a newer feature revision's sheet status. Failed formats remain separate from successful deliverables and keep their saved work for retry.

The local Agent Testing sample in `output/marketing/agent-testing/` demonstrates feature-specific copy, a seven-slide carousel and a feature brief. It was authored and visually inspected locally, without external writing calls or Drive upload. It is deliberately not marked as a completed live campaign or a model-reviewed output.

Validation includes `tests/test_marketing_quality.py` in addition to the existing marketing, refresh and release-ask tests. Visual PDF inspection uses PyMuPDF, now declared in the backend requirements.

## Artifact design standard

Static marketing deliverables (`feature_brief`, `article`, `linkedin_carousel`) use `marketing_design.py`: the existing artifact design contract, approved reference images, Convin lockups and embedded Inter fonts feed a feature-specific HTML composition and separate design-polish pass. The superseded paragraph PDF and repeated Pillow card renderers have been removed.

Because the brief and the carousel are designed rather than written, the designer also receives per-format direction naming the device each piece of approved copy has to become: a why block is a risk statement with its reasons, flow and steps are a connected sequence, comparison is a two-sided split panel, panel is the dark caveat grid, and each carousel slide is composed as its named treatment. A brief targets one dense A4 page. The visual reviewer judges the same standard and rejects running paragraphs, a heading-plus-text-block repeated down the page, and slides that are stacked text boxes; it may ask for better structure but never for more words.

The designer receives approved display copy, not the editorial evidence audit. Copy is preserved verbatim and checked against visible rendered text. Documents use fixed A4 boards; carousels use one 1080x1350 board per approved slide. Chromium blocks outbound resource requests and disables page scripts. Rendering rejects missing copy, wrong page/slide counts, wrong board sizes and content outside its board. Visual review compares the outputs with the artifact references, and rejects added claims or diagrams that change the approved copy's meaning.

Composition and polish are checkpointed by content, model, design contract, per-format direction and references. The revised local Agent Testing sample demonstrates that design language with an admissions conversation flow, test sequence, evidence grid and draft-versus-published prompt diagram, now composed from the visual contracts and validated through the production validators before rendering. These are explanatory diagrams, not product UI captures. Its previous designs are retained in `output/marketing/agent-testing/previous-design/`.

Video uses the Convin Remotion launch-film renderer described below. Live provider-generated design and end-to-end delivery still require the outstanding external-run authorization.

## Mastersheet and launch films (September 14)

The mastersheet now uses a compact feature list with priority, audience, use case and a content-status strip for every PMM format. Click a strip to open the inventory and start one type. The latest campaign for the current feature revision still drives Review. Search, product-area filters, priority/name/recent sorting and explicit batch selection replace the 14-column editing grid. Feature briefs, dates, notes, links and source evidence remain available in a drawer; unsaved drafts survive polling and require a discard choice when closing. Existing records and earlier campaign versions are preserved. Mobile uses feature cards.

Film composition is defined in `backend/app/static/artifacts/marketing-video-design.md` and `Sense_Communication/remotion/src/marketing/Film.tsx`. The reference informs the shift between spare white narrative scenes, blue feature reveals and meaningful animated relationships. It is not a source for unrelated feature claims. Extracted low-resolution reference frames are used only as design references, not as output footage.

The writer supplies a visual reason, short labels and an optional exact headline emphasis per shot. Films open on a lived example animation (call or conversation). Narration determines shot lengths and label reveal timings. Phrase subtitles are estimated within measured takes, not word-aligned. The renderer uses the actual Convin lockup, Helvetica Neue display fallback, bundled Inter body/caption fonts, blue/pale/dark tokens and separate portrait layouts. No unlicensed soundtrack, synthetic dashboard UI or reused reference narration is added. A campaign may request an original ducked score composed in-process so the voice stays in front.

Renderer/voice/content changes invalidate video caches. Technical QA is explicitly separate from production readiness and human playback review. Local system-voice previews are marked DESIGN PREVIEW in the film and cannot become a production campaign through the normal render call. The external writing/narration/Drive path still requires the previously requested authorization before a live test in this task.

Launch films are capped at 90 seconds and Shorts at 60 seconds after measured narration. The renderer rejects text outside the frame or overlapping text once each shot has settled. Validation: `tests/test_marketing_video.py` covers shot contracts, voice isolation, caption/reveal timing, encoded audio checks, frame rate and three-phase visual sampling.

## September 20 film review

The PII sensitive-sales builder preserves v7 and writes `render-v8` for fresh narration,
or `render-v8-review` with `--existing-voice` for an explicitly identified local visual review.
The review inserts measured pauses in the existing voice without stretching its speech.
The shared renderer now uses 26-frame dissolves; call-first no longer stacks fast wipes on
those fades. Configuration uses an illustrative selection panel, phone controls stay stable,
and the builder derives speaking-indicator amplitude from the voice samples. The soundtrack
mix is quieter. Fresh narration needs the configured TTS service; review audio is not a
substitute for approval of the new performance.

An installed headless Chromium can be selected with `REMOTION_BROWSER_EXECUTABLE`, avoiding
an implicit browser download in restricted environments.
