# Marketing film kit — what Claude actually renders

This is the component catalog for launch films. The writer picks a visual enum and copy.
The renderer owns the kit. Do not invent a new phone, a new lockup polarity, or a new
background recipe in prose.

## Visibility, before any background

Decide the field first, then the chrome. Never the other way around.

- Black device chrome (iPhone bezel, Dynamic Island) only sits on `stage-light`: a clean pale
  desk (`#F7FAFF` → `#E4EEFF`). No photographic plate, no navy bloom, no generated chat UI
  behind the handset.
- Dark Convin lockup (`convin-lockup-light.svg`) only on a light field.
- White Convin lockup (`convin-lockup-dark.svg`) only on navy, black, or brand-blue fields.
- If a generated plate would sit under a black header, drop the plate. Own a solid band instead.
- Captions, numbers and labels must keep contrast against the surface they sit on. Do not put
  `#050505` type on a dark world, and do not put `#F1F1F1` type on a pale world.
- Subtext follows the same polarity: never brand-blue (`#1A62F2`) type on a navy or brand-blue
  field. On a dark field the note line is `#F1F1F1`.
- The Convin lockup lives in a reserved header band (`CALL_HEADER`). It never overlays the
  iPhone bezel, island, or screen.

## Libraries the frames may use

Installed in `Sense_Communication/remotion`:

- `lucide-react` — iOS-style call icons (Phone, Mic, Grid3x3, Volume2, UserPlus, Video, Contact)
- `@remotion/lottie`, `@remotion/paths`, `@remotion/shapes`, `@remotion/motion-blur` — motifs
- Helvetica Neue display, Inter body, Kohinoor for Hindi

Frame authors compose from `src/marketing/kit/`:

| Primitive | Use |
|---|---|
| `IPhone` | Every call / conversation device. iPhone 15 Pro chrome, island, status bar, home indicator. `appearance="light"` on the lock screen; `appearance="dark"` on incoming and in-call. Hold the ring until just before first speech. Scale the same screen into landscape and portrait. |
| `IdentityCard` | Physical Indian PAN card, ISO ID-1. Name, photo, PAN strip. HTML, not SVG. |
| `PaymentCard` | Physical plastic credit card, ISO ID-1. EMV chip, contactless, number, name, expiry. No 3D rotate. |
| `ExamplePanels` | Before → after redaction. |
| `Motif` / `WriteOnPath` / `SignalTrail` | Palette-locked marks and connections. |
| `lockupFile(luma)` / `headerInk(luma)` | Lockup polarity helper. Always follow world luma. |

Do not draw a rounded-rect “phone”. Do not restart the device or the live transcript on a
new spoken turn. Consecutive `call` scenes are one persistent handset; whole spoken lines
appear at once. Never karaoke word-by-word.

## Visual enum → kit

- `call` / `conversation` → `IPhone` on `stage-light`. Opening ring, answer, connected states.
- `detect` / `collect` → same iPhone, tags on the live transcript.
- `spread` / `flow` → artefacts travelling to named surfaces.
- `mask` / `split` → `ExamplePanels` plus the waveform, never a fake product screenshot.
- `statement` → type on a rotating mechanical treatment (centre-dark / left-light / emphasis-dark).
- `contrast` / `stack` / `orchestration` / `steps` / `spotlight` → existing diagram kit.

## Motion the writer does not control

The call is one Sequence. Transcript lines appear as complete utterances. Cards ease in once
and settle (`translateZ(0)`), sitting on the desk as ID-1 objects, never a 3D cut-in.
Camera drift on a device stage is a few pixels at scale 1 so the iPhone does not shimmer.
Consecutive transcript turns must not replay an entrance.

## Voice (Cartesia Sonic-3)

Siya narrates near 0.96–1.00. Arushi (agent) uses normal 1.0 delivery with natural sentence punctuation. Kabir (customer) is painted through a telephone
handset EQ so the first part of the film sounds like a real person on the other end of the
line. Emotion tags are English-only; Hindi takes send speed only. Do not mark every English
line `confident`. Let punctuation guide normal delivery; reserve explicit emotion for a deliberate performance choice. Write the sentence the way a person
would say it; Sonic phrases from punctuation.

## September 20 pacing and call revision

Use 26-frame scene dissolves and 24-frame entrances for the call-first explainer.
Do not overlay a second fast wipe on that dissolve. Give explanatory shots a 1.25-second
inter-shot pause, or 1.6 seconds for configuration, masking examples and the reveal.
Pauses are silence between measured takes; speech and word timestamps are never stretched.
Retain a two-second hang-up gap and normal conversational turn-taking.

The phone holds its controls and speaker mode across utterances. Speaking indicators can
use per-frame audioEnvelope RMS values. Transcript text keeps one font size and remains
legible after a turn ends. A configuration example may show the actual supported choices
(identifiers and surfaces), with icons, selection states and a summary; label it illustrative.

Arushi and Kabir now use normal 1.0 delivery rather than slowed 0.85/0.92 takes. Prefer
conversational sentences without extra break tags. Hindi continues to omit emotion tags.
Customer audio uses gentle 120–7200 Hz wideband coloration and preserves the original RMS;
never normalize each take to full scale before saturation. Voice profile versions invalidate
older takes. Existing audio may be used for a clearly identified visual review, but does not
validate new synthesis. Technical QA is separate from listening review.
