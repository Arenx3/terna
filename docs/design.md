# Design

Terna's visual direction is called **"highlighter on graphite"** (*resaltador sobre grafito*). This document is the source of truth for the app's look and behavior. Tokens live in [`frontend/src/index.css`](../frontend/src/index.css); this file explains why they are what they are and how to use them.

## Who we design for

The primary user is an in-house recruiter. They spend long sessions in Terna: screening a stack of résumés, moving people through the pipeline, and preparing the *terna* (the three finalists) for a hiring manager. The interface has to stay calm for hours and get out of the way. It also has to make one thing obvious at a glance: **why** a candidate fits, shown as evidence.

## The idea

A recruiter reading a printed résumé runs a highlighter over the line that proves a requirement. Terna does the same on screen.

- **Graphite** carries the structure in dark mode, the default for long sessions. **Bond paper** carries it in light mode. Both are warm neutrals with one hue, stepped only by lightness.
- **The marker** is the only colour: *cempasúchil* (marigold), `oklch(0.8 0.155 68)`. It means "this is the evidence", "this is where you are" or "this is the main action". It is never decoration.

If a screen has two things in marker colour that mean different things, one of them is wrong.

## Signature: the marker stroke

The `marker` utility draws a highlighter stroke behind inline text. The stroke has slightly uneven ends and a lifted baseline, like a real marker pass, and it wraps line by line (`box-decoration-break: clone`).

| Use it for | Do not use it for |
|---|---|
| Evidence from a résumé or interview that proves a requirement | Decorating headings or marketing copy |
| The current item in navigation (sidebar, ⌘K selection) | Status badges, tags or counts |
| One word in a page title that names who or what the page is about | More than one highlight per heading |
| Text selection (`::selection` uses the same colours) | Large blocks of text |

Add `marker-draw` to sweep the stroke in once from the left (520 ms, ease-out-quint). Reserve it for moments where evidence appears, such as a screening result or the sign-in panel. Stagger strokes by roughly 380 ms when several appear together.

## Colour tokens

Semantic tokens follow shadcn's names, so every shadcn component inherits the direction. Terna adds a few of its own:

| Token | Purpose |
|---|---|
| `--marker`, `--marker-ink` | The highlighter stroke and the text on top of it |
| `--primary`, `--primary-foreground` | Filled main action: marker fill with ink-dark text |
| `--primary-edge` | Border on filled buttons. In light mode the marker alone is too pale against paper, so the edge carries the 3:1 non-text contrast |
| `--faint-foreground` | Fourth text level: IDs, timestamps, footnotes |
| `--success` | Met requirement, healthy service |
| `--graphite` | The base neutral, for illustrations and the favicon |

Text has four levels: `foreground` (content), `muted-foreground` (supporting), `faint-foreground` (metadata), and disabled (opacity on the control).

### Surfaces and depth

Depth comes from **borders plus small lightness shifts**, never from shadows. In dark mode, `background` is 0.175 L, `card` is 0.2, `popover` is 0.225, and `muted` and `accent` sit in between. Borders are the foreground colour at 8–11% alpha, so they disappear until you look for them. The sidebar uses the same colour as the page: it is part of the workspace, not a separate world.

### Contrast

Every text and control pair meets WCAG 2.2 AA in both modes: 4.5:1 for text and 3:1 for focus rings, icons and control edges. When you add or change a token, check its pairs again before merging.

## Typography

| Role | Typeface | Notes |
|---|---|---|
| Headings, brand statement | Bricolage Grotesque (variable) | Negative tracking, about −0.03em at 28px and above, with balanced wrapping |
| UI and body | Geist (variable) | 14px base, `text-wrap: pretty` on paragraphs |
| IDs, codes, shortcuts | Geist Mono (variable) | Candidate IDs, keyboard hints |

The scale uses a ratio of about 1.25 from a 14px base: 12 (meta), 14 (body), 16 (card titles), 28 (page titles), 32 (home greeting) and 44 (auth brand statement). Hierarchy comes from weight and colour first and size second: titles at 600, labels at 500, metadata at 400 in faint colour.

All fonts are self-hosted through `@fontsource-variable`, with no external requests.

## Density and spacing

- The base unit is 4px. Gaps and padding use multiples of it.
- Density is *workbench*. Sidebar items are 36px tall, control rows 32–36px, and cards have 16–20px padding. Space opens up between groups, not inside them.
- Radius scale: `--radius` is 10px; inputs and buttons use `md`, cards use `xl`, dialogs use `xl` or `2xl`.
- Content columns cap at about 672px (`max-w-2xl`) for forms. Tables and boards use the full width.

## Motion

- Motion confirms an action or reveals evidence. It never decorates.
- Use ease-out-quint (`--ease-out-quint`) for entrances and keep durations under 300 ms. The marker stroke (520 ms) is the one exception.
- Buttons scale to 0.98 on press. The ⌘K palette opens instantly, like a native launcher.
- Animate only `transform`, `opacity` and `background-size`. Never use `transition: all`.
- `prefers-reduced-motion: reduce` ends every animation and transition immediately (see `index.css`).

## Shell

- **Sidebar** (collapsible to icons; a sheet on mobile): company switcher at the top, navigation grouped by *Work* and *Company*, account menu at the bottom. The active item gets a marker stroke on its label.
- **Top bar:** sidebar toggle, search (opens ⌘K; icon-only on small screens), language and theme menus.
- **⌘K / Ctrl K:** pages, companies, actions (invite and log out) and preferences (theme and language). Anything you can click in the shell, you can reach from here.
- **Loading:** skeletons shaped like the content they replace, never spinners on a blank page.
- **Auth pages:** a two-column layout. The left panel shows a synthetic screening result with its evidence highlighted: the product's promise, shown working. The form column comes first in the reading order, and the panel is hidden on small screens.

## Public careers pages

Candidates read; they don't operate. The careers pages (`/careers/<slug>`) switch to reading mode:

- The company leads. Its name is in the header, in the browser tab and highlighted in the headline. Terna is a one-line footnote.
- The reading width is about 720px and body text is 16px with generous leading. There is no sidebar and no ⌘K.
- A posting keeps its own language (`lang` on the content), while the interface around it follows the reader's.
- Must-haves get a success check and nice-to-haves a muted plus. The marker colour stays out of the lists, since a posting has no evidence yet.
- Each job embeds schema.org `JobPosting` JSON-LD, generated by the API, and sets its canonical URL.

## Accessibility

- Every page has a skip link to `#main`, one `h1`, and headings in order.
- Everything is reachable by keyboard with a visible focus ring (`--ring`, 3:1 or better).
- Icon-only buttons have an accessible name. Text in `components/ui` is translated too.
- The `<html>` element sets `color-scheme` and the theme updates `theme-color`.

## Voice (es / en)

Terna speaks to the recruiter as a colleague: **direct and warm**, using *tú* in Spanish.

- Use neutral Spanish that reads naturally in Mexico and the rest of Latin America. Write English as plain, everyday English rather than a translation of the Spanish.
- Use verbs on buttons: *Enviar invitación / Send invitation*, not *OK*.
- Errors say what happened and what to do next: *Demasiados intentos. Espera un minuto y vuelve a intentar.*
- Empty states explain what will appear and how to make it appear.
- The AI suggests and the recruiter decides. Copy never says the AI "chose" or "rejected" anyone.
- Use the ellipsis character (…) for actions that continue: *Busca o ve a… / Search or jump to…*

All user-facing text goes through i18n. The lint rule `i18next/no-literal-string` enforces this.
