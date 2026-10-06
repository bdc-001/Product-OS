# Feature launch films

Design authority: the brand design system. Creative reference: the operator-supplied
product storyboard (`references/video/*board*.png`), plus
an operator-supplied product video (about 65 seconds, 1920×1080).
Motion reference: operator-supplied "Multilingual Video_23.06.mp4" (75.47 seconds).
The storyboard sets post-call product craft: the headless suited figure, large circular
blue crops, full-bleed blue problem and reveal fields, connected node diagrams, and a
white product end card. Its progressive type, evolving conversations, moving
connections and shifts of visual scale guide animation. Preserve the approved the company
design; do not copy the board's copy, metrics, photography, WhatsApp chrome, or
unrelated feature claims. The reference is a guide to composition, not authority for
feature claims. The PII Hindi-sales film still opens on the approved iPhone call. Every call or conversation
uses the `IPhone` kit (iPhone 15 Pro chrome, Dynamic Island, status bar, home indicator) on a
clean `stage-light` desk. Black bezels and the island are not placed on a generated photographic
plate, a navy bloom, or a dark world.

## Story
Open on a lived example the buyer would recognise, animated rather than described: a phone call,
a conversation, or another concrete situation, always labelled illustrative. The agent and customer voices are fixed, but the characters are recast every film: a new customer first name and a new reason for the call, never one a recent film used. A natural preference exchange can start in English and continue in Hindi; retain each speaker’s identity across the switch. Never label them Support Specialist or use a support scenario unless explicitly requested. Films are industry-neutral: the situation is one every customer-facing team has (a callback that never happened, a reminder nobody read), never a named vertical. Then name the friction, reveal this feature, show only how it solves that problem,
and finish with one action. Earn every shot. A launch film normally has 10–14 shots
and runs about 30–55 seconds; use 8–10 for a short. Do not pad to 24 scenes.
Write conversational narration in 8–14 words per shot, usually one sentence that finishes its thought.
Sixteen words is the ceiling for a necessary mechanism or boundary, not a target; a 3–4 word beat is for
a reveal or the closing landing. Siya performs the product story in connected acting beats, so write it to be said aloud:
contractions, active verbs, a cause joined to its effect inside the sentence, commas where the voice
leans and carries on, a real question where the story turns, and a long explanatory line answered by a
short one. A film whose sentences are all the same short length receives the same falling contour on
every line and sounds recited rather than told. Avoid repetitive introductions and lists of
abstract benefits. Keep feature names pronounceable; do not insert phonetic spellings into captions.
Use a concrete example explicitly labelled as illustrative. Never use a real customer recording.
Do not copy the reference's claims about training, speed or production readiness into unrelated features.

## World, not slides
The renderer owns a single persistent world and a camera. Scenes enter and exit inside that
world; the root layer is never remounted between shots. The writer supplies narrative, visual
enum, labels and evidence. Treatment, luma band, transition vocabulary, elevation, bloom and
ambient motion are mechanical in the render layer. Flat full-frame fills, a frozen canvas, and
identical consecutive treatments are unreachable from the component set.

## Visual grammar
The reference changes visual scale and composition: a conversation on a photographic field, spare kinetic
headlines, overlapping source documents, a blue brand reveal, a connected intelligence hub,
and a concise closing statement. Follow that variety, not a repeated presentation slide.
Choose visuals to explain the approved feature:
- call: an illustrative phone example with recognizable people and their environment, an incoming ring, answer and connected states, and word-timed dialogue. Prefer articulated characters to initials in circles. Never use a real customer recording or imply a conceptual demo is a product screenshot.
- detect: the same call, with a detection tag or bounding box on a value that is still unmasked.
- collect: the same call, with identifiers gathering in a labelled sidebar as they are spoken.
- spread: freeze the call, then duplicate it as a metaphor for volume; do not speak a metric.
- flow: PII travelling through supported surfaces (transcript, audio, UI, reports).
- mask: scan a clear value, then lock it to a masked form.
- split: transcript redaction beside a muted waveform span on the recording.
- conversation: 2–3 short example utterances, alternating left/right, always marked Illustrative scenario.
- stack: 2–3 actual supported inputs or versions, staggered editorial panels; no fake browser chrome.
- steps: 2–3 ordered supported actions, connected and revealed in sequence.
- contrast: exactly two genuine alternatives; do not imply measured before/after results.
- orchestration: 2–3 named inputs/outputs connected to a labelled feature mechanism.
- spotlight: one concrete output or takeaway, with a deliberate camera pullback.
- statement: a short reveal or CTA with one evidence-backed phrase highlighted; do not open the film on a statement.
  Consecutive statement shots must rotate mechanically: centred-on-dark, left-aligned-on-light,
  multi-line-with-emphasis. The writer does not pick the treatment.
Use at least four treatments in a launch film and at least three in a short, including one
call, conversation, stack or orchestration. The first shot must be a call or conversation.
Never more than two identical visual enums in a row. Consecutive scenes of the same type
cannot share a visual treatment. Alternate light and dark luma bands across the runtime.
Each scene supplies a visual_reason explaining why that visual communicates this feature.

## Brand appearance
Primary #1A62F2; dark #0A2E7A and #151515; pale #EEF4FF; white #FFFFFF as type and device chrome only.
Inverse type #F1F1F1 only on dark. Text #050505 on light. Fine blue strokes and blue-tinted
shadows. Twenty-pixel corner radii. No flat fills anywhere: every background is a multi-stop
gradient. Flat #FFFFFF and flat brand colour as full-frame backgrounds are a delivery failure.
Brand colour appears as saturated gradient mass, not a thin accent on grey. Every element sits
on a plane (drop shadow, inner glow, or scale offset). Bloom, soft orbs and atmosphere are a
default world layer. Each film includes at least one live-action or photographic plate.
Actual brand wordmark, not rings plus a typed replacement brand. Lockup polarity follows the
field: white lockup on navy/black/brand, dark lockup on pale/white. Check that contrast before
committing a background. Display: Helvetica Neue
(the available substitute for Helvetica Now Display), body and captions: Inter.
No random red/green scene colours, dashboard progress bars, numbered scene headings, or
internal terms such as proof, benefit and evidence in the film itself.

## Motion, sound and delivery
Fast, expressive marketing motion: masked word builds, directional conversation entrances,
cards arriving from depth, sequential action focus, moving signals on actual relationships,
contrast wipes and deliberate camera pullbacks. Production films use Remotion first-party
packages pinned to the film runtime: branded Lottie motifs (`@remotion/lottie`), `@remotion/shapes`
arrows and marks, `@remotion/paths` write-on connections, and `@remotion/motion-blur` trails on
traveling signals. Motifs are brand-palette originals in the closed visual enum. Do not load
Mixkit, Pexels, useAnimations, or generic SaaS Lottie packs at render time. A visual should develop during the sentence.
Change the focal point approximately every 0.6–1.2 seconds while retaining readable labels.
Target 2.5–4.5 seconds per shot; a lived example on a call may take up to ten seconds when the
spoken details need it. Only a necessary mechanism may take longer than that. Avoid a long
static hold after a single entrance. Use energetic motion to explain this feature, not random jitter.
Never render an empty frame: no cut-to-white, cut-to-black, or blank hold. Something must
cross every cut (the persistent world, or a matched element). Vary the transition vocabulary
across the film: cross-dissolve, matched-element, masked wipe, camera push. Do not use one
transition type throughout.
For every label supply a label_cues entry: an exact phrase from narration, in spoken order.
The cue must explain the label at that moment. Never introduce an output while the voice is
still discussing a different input. Leave enough spoken time after the final cue to read it.
Align label reveals to these actual spoken word timestamps. Leave a short opening and
closing hold. No motion while the viewer is expected to read a long paragraph.
Use a female narrator: the user-selected Cartesia Siya (4459a9a5-69d6-4680-b970-e13dc51845b6) remains the marketing default. Geeta 1 (b567e37e-2f09-4ad4-a0a0-aeeb59f0d528) performs the agent at normal 1.0 speed with no emotion tag, and Pranika (dc3e49d2-7b1f-40d6-8350-3fa51e85d4fe) performs the customer through gentle wideband handset EQ; both are the operator's own Cartesia clones, with preserved dynamics so the first part of the film sounds like a person on the other end of the line. Keep the customer and narrator distinguishable through the staging and delivery. Narration stays plain text. Emotion tags are English-only and omitted on the default `confident` presenter setting so Sonic reads the sentence. Use calm for a sales opener, curiosity at the problem question, a brighter product reveal, reassurance for the benefit, and a settled close. Narrator speed stays near 0.96–1.00; dialogue stays near 1.0. Use pauses between ideas rather than slowing every syllable. Do not make every line equally emphatic. The renderer alone inserts validated pause tags; captions retain the approved words. Generate separate directed takes when the acting intent changes, then stitch them onto one PCM clock. Obtain word timestamps from those exact audio takes; captions,
visual cues and scene cuts share the stitched clock. Never divide a sentence into equal time slots.
Keep captions at natural sentence or phrase boundaries. The renderer does not accelerate
the finished MP4. Voice or alignment changes invalidate cached takes. Missing or mismatched
timestamps fail production rather than silently reverting to estimated timings.
Local system voice is a labelled timing preview only, not evidence of production voice quality. Never extract
or reuse music, voice, footage or screenshots from the reference as production media.
No music is better than an unlicensed track. An original in-process score may sit under Siya
when a campaign requests one; duck it so the voice stays in front. Do not imply that no
soundtrack is a finished sound-design pass. Captions stay ≥40px in 1080p and within social-safe margins. Supply SRT.
Landscape and portrait have independently arranged compositions; never crop one into the other.
Validate resolution, duration, audio, loudness and readable layout. Sample entry, middle and
late frames of every shot for visual QA. Numeric craft gates reject a film before the LLM
review: mean saturation ≥ 0.10 and p90 saturation ≥ 0.22 per frame; soft-gradient area ≥ 30%;
luma standard deviation ≥ 14 (catches blanks); no identical-frame run longer than 1.0s;
≥ 12% of screen regions showing motion per sampled interval; encoded video bitrate at least
220 kbps for 1080p graphic masters (a photographic plate-heavy film sits much higher, typically
near 1.8 Mbps). Below that graphic floor the picture is empty and must fail automatically. Human playback still checks voice, rhythm and motion.

Use an original upbeat score with a clear rhythmic pulse for launch films, typically 120–132 BPM. Give the opening ring and customer exchange room; dip beneath the privacy question and lift at the feature reveal. Duck music under speech without making it inaudible. Ring, connection and demonstration effects must have their own timeline cues and must not interrupt a spoken word. Validate the encoded master against its PCM source; a technically valid MP4 does not constitute human creative approval.

Pronunciation is fixed in the lexicon, never in the copy. the brand pack pronunciation file is the marketing pronunciation dictionary: it holds the brand (CON-vin, short i, initial stress) and every term the model reads wrong, currently PAN (the word pan, not than) and recording/recordings (stress on the second syllable). Any script containing one of those terms is synthesised with the dictionary attached, and the attached dictionary is part of the take cache. When you hear a new mispronunciation, add an IPA entry and re-render; never respell a word in visible copy, captions or the spoken transcript to coax the model. Spoken abbreviations also keep their noun — “a PAN number”, not a bare “a PAN”, which is too short to hear. Keep lines carrying unusual terms at or below 1.05 speed.

Delivery is shaped by punctuation first. Write the sentence the way it should be spoken and let the provider phrase it; add an explicit break only where the sentence genuinely cannot carry the beat. An inserted break inside a short greeting makes the line land unevenly, which is worse than no pause at all. Explicit scene language and voice choices are part of the take cache; Hindi is passed as hi to the provider, not transliterated into English.

For the PII Hindi-sales film, match the supplied reference opening: iPhone lock screen, incoming call, animated slide-to-answer, then six in-call controls and a red end-call button, all inside the IPhone kit. The operator specifically requested classic iPhone Marimba; that cut uses the local system asset. The rest of the score remains original.

## Reusable production feedback
Select examples from the feature’s buyer stakes and a workflow every customer-facing team shares; never set the story in a named industry. For PII masking, use identity and payment details (PAN/card numbers) as the central demonstration instead of relying on a mobile number. Use fictional values; explain before/after behavior and retained conversational meaning. Do not imply compliance guarantees, infer unsupported capabilities, or normalize OTP/CVV collection. Other features need their own relevant example and failure mode rather than a PII story copied into them.

A demo scene should use the available frame purposefully. Prefer two supported variants side by side in landscape, stacked in portrait: a label, before value, after value, and one line of retained context. Use the structured examples field and exact narration cues so both transformations are synchronized. Examples enter the editorial evidence review as public-facing copy. Do not leave one tiny demo in a large empty field when a second approved example or useful result would help. A hook or reveal may deliberately retain whitespace; never fill it with repeated labels, decorative cards or dense text.

Three motion tiers always run. Primary is the thing the narration is about and may settle.
Secondary is supporting elements responding. Ambient is the world: background drift, slow
parallax, breathing glow, never stops. After a scene's primary animation resolves, secondary
and ambient continue. Any region that holds pixel-identical for more than one second is a
defect. Primary duration derives from the scene's word-timestamp span, not a constant.
Staggered entries overlap: the next starts before the previous settles. Ease so cumulative
motion accumulates across the shot rather than front-loading and flatlining. Never drive a
property from raw per-frame noise; ambient is a smooth function of the film clock.

Anything that stays on screen across a cut must animate on the film clock, not the shot clock. Scene components remount at every cut, so a card keyed to the local frame re-enters on each turn of a conversation and looks like it is flashing. Persistent call overlays, transcripts and status chips take the global frame and change only their content.

Illustrate the product, not a faceless body. Cropped or headless human figures read as an unexplained “half suit” and carry no information; use the device, the artefact being discussed, a diagram of where data travels, or a product mark instead. Reference boards may be used for palette, crops and composition without importing their mannequins.

A call scene is one iPhone drawn once in phone pixels and scaled into a device body in both aspects: landscape spends the freed width on a live transcript that accumulates the conversation as complete lines (never karaoke), tags each turn with its speaker and language, and flags the moment a personal detail is spoken, while portrait keeps the language and detection beats inside the phone. The handset does not remount when the speaker changes. Dead regions of the phone UI earn their place with product meaning, never with marketing cards floating beside the handset. Brand marks sit in a reserved header band above the handset so the lockup never overlays the bezel or island; polarity stays matched to the light stage, and the transcript panel is signed by the lockup, not by typed-out brand text. Hold the ring until just before first speech, hold the ended call long enough to read, then hand over in well under a second.

Motion comes from the shared library in Motifs.tsx and `src/marketing/kit/` (IPhone, IdentityCard, PaymentCard, lucide-react call icons), not from hand-rolled maths. Draw strokes with WriteOnPath so the dash geometry follows the real path, carry flow with SignalTrail so a signal has motion blur and follows the curve exactly, use BrandArrow for direction and Motif for a palette-locked Lottie icon. Identity and payment artefacts are physical ISO ID-1 cards that settle on the desk; never animate a credit card with SVG 3D, a dimensional cut-in, or per-frame stroke widths. Extend that module when a film needs a new option rather than reimplementing an effect locally.

The writer prompt also receives `marketing-film-kit.md`: the catalog of primitives Claude may compose, the lockup/stage visibility rules, and the Cartesia delivery notes. Describe the story, not a new device.

Time the picture to the voice. Every reveal that names something should fire on the word that names it, taken from the scene's word cues, not from a hand-counted frame offset. Hand-tuned offsets are a fallback for beats the script does not speak.

Three beats carry most of the motion: the opening ring, the active speaker’s turn, and the masking demonstration. The ring gets expanding rings and a device glow on the Marimba pulse, held until just before speech. The live speaker gets voice bars and a transcript accent on the whole line, not a word-by-word highlight. The masking demo warns as the playhead enters the sensitive band, then collapses and wipes the value on the spoken cue. Do not move the narration clock to make those cues land.

The end card is a designed frame, not centred text on white: a full-bleed brand field, the lockup with its product line, the closing statement, and the feature name in a mark or badge.

Dialogue is voiced by role: the Geeta voice plays the agent, the Pranika voice plays the customer, and Siya narrates. The on-screen characters take a fresh name each film; never name them Geeta or Pranika. The production preflight rejects shared agent/customer voice IDs and identity changes between language turns. A four-turn opening may establish a real language preference; it is one continuous conversation, not four repeated presentation slides. For unrelated features the switch establishes human context and must not be presented as a product capability.

For call-first films, use 26-frame scene dissolves without a second wipe layer. Allow 1.25–1.6 seconds between explanatory takes so choices and transformations remain readable. Keep phone controls persistent across speaker turns; use measured audio amplitude for speaking indicators.

## Launch film grammar (`filmKind: launch`)
Reference: the operator-supplied product films (Voice Agent Monitoring, Prompt Generator, Multilingual). Their craft is the default for feature films; the launch contract in the writer prompt lists the shots. Where this section conflicts with the older treatment vocabulary above, this section wins for launch films.

- **A story with a product moment.** The references open on a line inside a situation ("The agent wasn't bad, the prompt was."), let that situation play out and cost something, name the feature once ("Introducing PII Masking by the company."), show the one moment it fixes the problem, and close on a tagline that calls back to the opening ("Your agent was never the problem. Give it a prompt worth running on."). The viewer should remember the story first and the feature as its answer. The validator holds this: at least three story shots before the feature, at most two product screens and three feature shots, and product shots carrying no more than a third of the spoken words. Explaining the product screen by screen is the failure to avoid.
- **Industry-neutral.** A film sells to every market at once. Use shared situations and roles (a customer, a callback, a follow-up, a campaign, a team lead) and neutral sample data. Narration, headlines, labels, screen data, message rows and the end card never name a vertical or its jargon, and launch films carry no audience chip; the validator rejects them.

- **Fields, not slides.** Every block sits on a moving gradient field: light, brand blue, dark, or the pale call stage. Consecutive call scenes and consecutive product screens share one field so the demo pushes as one piece; the field changes only when the story turns. Photographic plates are optional here.
- **One theme per film.** New films render in Aura (below). The six classic themes stay available when a `look` names one: twelve backgrounds (three per field, all inside the brand ramp, neutrals and the two approved gradients) grouped so daylight, horizon and editorial lead white, night and eclipse lead dark, and blueprint leads brand blue. A re-rendered film keeps the theme it was first rendered in. Leave `look` unset unless the brief asks for a classic tone. Each background carries one quiet motif at most; the content is the motion.
- **Scale shots are one object, not a wall.** Like the references (one phone ringing, one hub, one chat), a volume shot is a dot field of the day's dials, a single 9 AM–9 PM timeline, or one live dialer; a message shot is one outbound thread, one lane per audience, or the customer's lock screen filling with what landed. The renderer rotates these per film and never repeats a layout back to back; the lock screen is skipped when most messages failed. Leave `layout` unset; the dense card wall is only used when pinned.
- **Kinetic type is the narration.** Each headline word rises out of a mask on the timestamp where it is spoken, in its final position, and lines wrap balanced so no word is orphaned. On brand blue an emphasized phrase shares one white pill that sweeps with the words; elsewhere emphasis is colour only.
- **One persistent call.** A single illustrative handset and live transcript carry the whole exchange on the film clock; the narrator's review scene tags the failing turn with the product's own parameter names and its one-line reason. The hangup lands after the last spoken word.
- **Illustrative product screens.** Recreate only surfaces the feature actually has, with its own headings, buttons, statuses and tags copied verbatim; names and values are fictional and the window is marked Illustrative. The cursor travels to the action and clicks on the spoken cue; the result (toast, done label, version chip) appears only if the product shows it.
- **Continuous narration.** Consecutive narrator scenes with one delivery are synthesised as one read so the voice keeps sentence cadence across cuts; cuts, cues and captions come from that read's word timestamps. Give every narrator scene the same performance unless the delivery must change.
- **Sound.** An original 120 bpm pulse (or the 132 bpm drive) sits about 11 dB under the voice and lifts between lines. Synthesised UI effects fire on picture cues only: a short swipe that lands on every cut except pushes inside one call or screen block, impact on the reveal and the end card, connect and hangup on the call, pops on label reveals, ticks as checklist rows select, a click on the cursor cue, and a chime when a toast confirms it. They sit under the voice at fixed level.
- **Close.** The end card holds the lockup, the closing line, the feature badge, and one line of context that does not repeat the badge or name an industry.

### Aura (the default language)
Reference: the voice-agents demo film. Aura looks airy but moves fast: one idea on screen at a time, the motion carries the meaning, and the frame never parks. Entrances land in a third of a second, morphs in under half a second, and the camera keeps pushing and drifting through every shot.

- **Field.** Off-white, with a soft brand-blue glow drifting along the bottom edge. No grain, bands or saturated fills; the blue lives in the glow, the objects and one accent word.
- **One phrase per beat.** Write headlines as short spoken phrases, usually 2–5 words, lighter in tone than a slogan. Characters blur and rise in on the words' spoken timestamps; a longer headline splits at its commas into phrases that dissolve one through the next, so punctuate where the viewer should read a new phrase. The emphasised word turns into a blue serif italic, so emphasise one or two words, not a clause.
- **UI as single cards.** A product moment is one floating card, never a full window or a wall of UI: one checklist, one row of result cards, one table, one chart or one filter panel. A macOS pointer glides to it, hovers, presses on the click cue and the card changes. The Illustrative badge stays.
- **Signature shots.** Each label lands on its own narration cue.
  - **pills:** 2–3 capability or situation pills float in; the pointer clicks each on its cue. May open the film.
  - **network:** 2–3 app tiles joined by curved lines; the camera travels tile to tile on the cues, then pulls back. Aura's mechanism shot; it replaces orbit and relay.
  - **stat:** one short claim with a figure ("Live in 2 minutes") inside a glow orb with radiating ticks, which collapses into a glass sphere. The figure must appear in the scene's evidence quote; never round or invent it. At most one label, a short qualifier.
  - **toggles:** 1–3 settings cards whose switches flip on their cues. Labels are the product's own setting names, quoted verbatim in the evidence; screen.title may head the stack.
  - **bloom:** a flower opens and fills the frame while 2–3 workflow words cycle over it (Call backs, Reschedules, Renewals). Workflows, never industries.
  - **screenshot:** one real product capture from available_screens as a floating card with a steady push and the pointer gliding across it to a press. At most one per film; it counts as a product shot. Without captures for the feature, show a ui card instead.
- **Set pieces.** The call rings out of waveform strands, the dot grows into a pulsing call button with floating caption lines, and the hang-up fills the frame white for the next shot. The presenting card bursts a gem swarm around the mark before the feature name blurs in. The close slides the wordmark out of the mark and blurs the tagline in beneath it.
- **Morphs, not cuts.** Blocks blur through each other, zoom through the centre, grow out of a dot, or open through the call's white fill. The renderer chooses them; never describe transitions.
- **Sound.** Aura is scored with the high-energy beds only: the 128 bpm surge (kick-pumped bass and stabs, open hats, a riser and crash every eight bars) or the 132 bpm drive. Siya reads narrator lines at launch pace (1.12; 1.05 on a line with a lexicon term); call voices keep their natural speed. Holds between lines are beats of a fifth of a second, so keep each narrator line to one short sentence. Morphs land with a short whoosh instead of the swipe, each pointer press clicks softly, a stat lands with a chime, and the call keeps its ring and hang-up.

### Shared pacing across topics
All campaign films use scene-level voice assembly, including scripts without performance or language overrides. Scenes with a visual or treatment receive a 1.25-second reading hold; explicit `hold_after` (0–3 seconds) overrides it. Dialogue keeps 0.32-second turn gaps and a two-second hangup beat. Word alignment includes every hold. Existing duration limits still apply; shorten copy rather than accelerating speech. PII-specific visual content remains in its own renderer; shared transitions, voice profiles, and pacing apply to other topics.
