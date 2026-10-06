# Platform design system

The implementation lives in `frontend/app/ui/tokens.ts`, `frontend/app/theme.ts`, and `frontend/app/ui/kit.tsx`. The interactive component gallery is Settings → Design system. All platform modules inherit this MUI theme; generated client artifacts retain their own brand styles.

## Foundations
- Neutral ink actions, white surfaces, subtle borders, restrained shadows. Reserve green, amber, and red for meaningful status.
- Body text 14–15px, captions 12–13px, section headings 17–21px. Secondary text must remain readable.
- Use the shared 4/8px spacing scale. Content padding is 16px on mobile and 24–32px on desktop.
- Controls use an 8px corner radius; cards 12px; dialogs 16px. Animation must not bounce or shift content.

## Structure
- The shell owns the single page h1. PageHeader adds a description and only renders a secondary heading when it adds new context. Never repeat the module title below the shell title.
- Keep the main navigation consistent. Settings has an internal section navigation, horizontal on narrow screens and vertical on wide screens.
- Codebase branch selection and repository configuration live in Settings → Codebase & branch. The existing Codebase navigation shortcut and /codebase route redirect there.
- Keep primary actions with the relevant page, form, or section. Prefer one primary action per task. Secondary actions use outlined/text buttons; no decorative arrows by default.
- Copilot opens from navigation or search. Do not add floating launchers over page content.

## Components and behavior
- Use PageBody, PageHeader, FrostCard, Section, PillButton, and shared state components.
- Use real buttons and links, visible keyboard focus, named icon actions, and accurate disabled states.
- Keep tables horizontally scrollable inside their container. Use min-width: 0 on flex/grid children; allow long titles and file paths to wrap. Do not force global box-sizing on MUI inputs: their content-box height includes padding.
- Form labels, values, and helper text must fit without collision. Never reduce field height to make a dense layout fit.
- Show loading, empty, failure, retry, and completion states where the action takes place. A failed run is View run, not Review ready content.
- Validate desktop and narrow-screen navigation, dialogs, long names, controls, and table overflow after shared style changes.

## Workspace interaction patterns
- Notes keeps document actions in its editor toolbar and optional writing tools in one menu. Autosave and explicit save share an unfinished write; do not open or overwrite an unloaded note. Filtered action lists include only the action blocks needed by that view.
- List refreshes show progress in context, report failures with retry, and keep search and reset controls together. Use a project selector when project names or counts can vary.
- Cliq categories share one searchable list. Hiding an item offers Undo; preparing a response opens a draft in Copilot.
- The weekly metric cards are the category navigation. Do not duplicate them with a second tab row.
- Prototype lists use cards on narrow screens and a paginated table on wider screens. Keep long names readable and project links keyboard accessible.
- Marketing separates feature briefs from optional launch planning. Show request errors inside the dialog that initiated them, and give campaign history search and status filters.
- Document previews open immediately with a loading state, close control, and local retry on failure.
