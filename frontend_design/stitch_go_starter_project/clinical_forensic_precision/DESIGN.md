---
name: Clinical Forensic Precision
colors:
  surface: '#f8f9ff'
  surface-dim: '#cbdbf5'
  surface-bright: '#f8f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#eff4ff'
  surface-container: '#e5eeff'
  surface-container-high: '#dce9ff'
  surface-container-highest: '#d3e4fe'
  on-surface: '#0b1c30'
  on-surface-variant: '#434655'
  inverse-surface: '#213145'
  inverse-on-surface: '#eaf1ff'
  outline: '#747686'
  outline-variant: '#c4c5d7'
  surface-tint: '#2151da'
  primary: '#0037b0'
  on-primary: '#ffffff'
  primary-container: '#1d4ed8'
  on-primary-container: '#cad3ff'
  inverse-primary: '#b7c4ff'
  secondary: '#565e74'
  on-secondary: '#ffffff'
  secondary-container: '#dae2fd'
  on-secondary-container: '#5c647a'
  tertiary: '#374559'
  on-tertiary: '#ffffff'
  tertiary-container: '#4f5d71'
  on-tertiary-container: '#c7d6ee'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#dce1ff'
  primary-fixed-dim: '#b7c4ff'
  on-primary-fixed: '#001551'
  on-primary-fixed-variant: '#0039b5'
  secondary-fixed: '#dae2fd'
  secondary-fixed-dim: '#bec6e0'
  on-secondary-fixed: '#131b2e'
  on-secondary-fixed-variant: '#3f465c'
  tertiary-fixed: '#d5e3fc'
  tertiary-fixed-dim: '#b9c7df'
  on-tertiary-fixed: '#0d1c2e'
  on-tertiary-fixed-variant: '#3a485b'
  background: '#f8f9ff'
  on-background: '#0b1c30'
  surface-variant: '#d3e4fe'
  surface-canvas: '#F8FAFC'
  surface-panel: '#FFFFFF'
  surface-sidebar: '#0F172A'
  surface-sidebar-hover: '#1E293B'
  border-subtle: '#E2E8F0'
  border-strong: '#CBD5E1'
  verdict-real-base: '#059669'
  verdict-real-surface: '#ECFDF5'
  verdict-real-border: '#A7F3D0'
  verdict-uncertain-base: '#D97706'
  verdict-uncertain-surface: '#FFFBEB'
  verdict-uncertain-border: '#FDE68A'
  verdict-synthetic-base: '#DC2626'
  verdict-synthetic-surface: '#FEF2F2'
  verdict-synthetic-border: '#FECACA'
  waveform-active: '#2563EB'
  waveform-threshold: '#94A3B8'
typography:
  headline-lg:
    fontFamily: Inter
    fontSize: 1.75rem
    fontWeight: '600'
    lineHeight: 2.25rem
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Inter
    fontSize: 1.25rem
    fontWeight: '600'
    lineHeight: 1.75rem
    letterSpacing: -0.015em
  headline-sm:
    fontFamily: Inter
    fontSize: 1rem
    fontWeight: '600'
    lineHeight: 1.5rem
    letterSpacing: -0.01em
  body-lg:
    fontFamily: Inter
    fontSize: 1rem
    fontWeight: '400'
    lineHeight: 1.5rem
  body-md:
    fontFamily: Inter
    fontSize: 0.875rem
    fontWeight: '400'
    lineHeight: 1.25rem
  body-sm:
    fontFamily: Inter
    fontSize: 0.75rem
    fontWeight: '400'
    lineHeight: 1rem
  label-numeric:
    fontFamily: JetBrains Mono
    fontSize: 0.875rem
    fontWeight: '500'
    lineHeight: 1.25rem
    letterSpacing: -0.01em
  label-code:
    fontFamily: JetBrains Mono
    fontSize: 0.75rem
    fontWeight: '400'
    lineHeight: 1rem
  badge-label:
    fontFamily: Inter
    fontSize: 0.75rem
    fontWeight: '600'
    lineHeight: 1rem
    letterSpacing: 0.025em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  gutter: 1.5rem
  margin: 2rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2rem
---

## Brand & Style

This design system establishes an uncompromising, clinical, and evidentiary visual language tailored strictly for digital forensics, anti-fraud investigation, and audio security intelligence. Rejecting consumer SaaS conventions, dramatic gradients, and promotional rhetoric, the aesthetic operates as an analytical workstation: austere, sober, and exact.

The user posture is that of an investigative expert inspecting critical acoustic artifacts under high-consequence conditions. The interface must communicate institutional reliability, scientific neutrality, and mathematical clarity. 

Core principles governing this environment:
- **Evidentiary Humility**: Never project omniscient certainty. Probabilistic thresholds, confidence intervals, and uncertain bands take precedence over binary claims.
- **Instrumental Density**: Prioritize structured, tabular scan-rates, real-time waveform inspections, and high information throughput over decorative whitespace.
- **Tri-Fold Semantic Discipline**: Visual status tokens for integrity verdicts (*Likely Real*, *Uncertain*, *Likely Synthetic*) must always integrate high-contrast chromatic tokens, explicit geometric symbology, and exact textual nomenclature.

## Colors

The palette uses a dual-canvas model: an anchor of authoritative dark slate (`#0F172A`) for navigation and persistent monitoring rails, juxtaposed against a clinical, high-clarity neutral canvas (`#F8FAFC`) with pure white card surfaces (`#FFFFFF`).

### Primary & Accent Structure
- **Primary Accent (`#1D4ED8` / `#2563EB`)**: An authoritative cobalt blue reserved exclusively for primary execution targets (e.g., "Start listening", timeline sweeps, file drop activations) and focus outlines.
- **Sidebar & Frame Foundation (`#0F172A`)**: Communicates operational depth and visual containment. Subordinate items in navigation utilize lower-opacity slate shifts (`#1E293B` on hover) rather than chromatic color shifts.

### Verdict & Forensic Telemetry Tokens
Verdicts must strictly adhere to the designated tripartite scheme. Color is never permitted to stand alone without accompanying iconographic and text tokens:
- **Likely Real**: Baseline `#059669`, with container surface `#ECFDF5` and perimeter stroke `#A7F3D0`. Accompanied by a checkmark glyph.
- **Uncertain (Ambiguous Band)**: Baseline `#D97706`, with container surface `#FFFBEB` and perimeter stroke `#FDE68A`. Accompanied by an alert exclamation glyph. Represents values straddling the active model decision boundary.
- **Likely Synthetic**: Baseline `#DC2626`, with container surface `#FEF2F2` and perimeter stroke `#FECACA`. Accompanied by a dimensional cross glyph.

## Typography

Typography balances clean structural hierarchy via Inter with tabular data legibility driven by JetBrains Mono. 

- **Quantitative Alignment**: All forensic probabilities ($P(\text{fake})$), millisecond latencies, sample rates, window boundaries, timestamps, and confusion matrix coefficients **must** employ tabular numerals (`font-feature-settings: 'tnum' 1` or `JetBrains Mono`). This avoids visual jitter during rolling 60-second updates.
- **Case and Tracking**: Metric labels on analytical widgets (e.g., "SPEECH RATIO", "WINDOWS ANALYZED") leverage uppercase sizing at `body-sm` with tight positive letter spacing (`0.05em`) to structure dense card grids cleanly.
- **Editorial Subordination**: Explanatory disclaimer text ("Research prototype... not proof of identity") is rendered in muted neutral gray (`#64748B`) at `body-sm` to maintain analytical context without distracting from diagnostic readouts.

## Layout & Spacing

The layout is built around a rigid 12-column analytical desktop grid capped at a maximum width of 1280px within the main content viewport, paired with a permanent 240px navigation sidebar docked to the left edge.

- **Grid & Alignment**: Standard layout columns span multi-unit analytical panels (e.g., 8-column timeline alongside a 4-column telemetry inspector; 4-card equidistant KPI row spanning 3 columns per card).
- **Fixed Vertical Rhythm**: Panel interiors use a tight 16px (`space-md`) to 24px (`space-lg`) boundary padding to sustain density while retaining visual separation. 
- **Reflow & Responsive Boundaries**: 
  - Desktop (≥1280px): Full 12-column grid with permanent sidebar and persistent side-drawers for file inspection.
  - Compact Desktop / Tablet Landscape (1024px – 1279px): Grid condenses gutters to 16px; side-drawers overlay instead of pushing the primary canvas.

## Elevation & Depth

This system intentionally eliminates atmospheric, consumer-grade drop shadows. Depth and visual hierarchy are established entirely through flat, architectural layering:

- **Surface Tiers**:
  - `Level 0 (Canvas)`: Base page background in `#F8FAFC`.
  - `Level 1 (Card/Inspector)`: Crisp white `#FFFFFF` with a single, high-definition 1px boundary stroke (`#E2E8F0`).
  - `Level 2 (Active/Floating Elements)`: Contextual modals (such as the Call Monitor consent dialog) and flyout inspect drawers rely on a clean 1px border (`#CBD5E1`) paired with a minimal, neutral ambient diffusion: `0 4px 6px -1px rgba(15, 23, 42, 0.06), 0 2px 4px -2px rgba(15, 23, 42, 0.04)`.
- **Threshold & Inset Layers**: Gauges, timeline viewports, and audio level meters use inset background containers (`#F1F5F9`) with recessed 1px hairline inner borders to signify functional instrumentation fields.

## Shapes

The geometric framework balances technical precision with modern software ergometrics:

- **Panel & Structural Cards**: Uniform 12px outer radius (`rounded-lg` per scale 2) provides geometric consistency across KPI units, timeline viewports, and tabular containers.
- **Controls & Input Fields**: Buttons, segmented tab controllers, file drop areas, and dropdown fields adhere to an 8px radius (`rounded-md`).
- **Telemetry Chips & Badges**: Verdict tags, status indicators, and numeric badges employ a controlled 6px radius to maintain a structured rectangular stamp aesthetic rather than an overly soft circular pill.
- **Waveform & Matrix Elements**: Confusion matrix cells, probability histogram bars, and audio level meter segments employ crisp 2px corners (`rounded-xs`) for clean edge-to-edge alignment.

## Components

### 1. Buttons & Controls
- **Primary Action**: Solid `#1D4ED8` fill, `#FFFFFF` text, 8px radius, height 40px, font weight 500. Focus ring: 2px offset with 2px stroke in `#2563EB`. Hover: `#1E40AF`.
- **Secondary / Utility**: Surface `#FFFFFF`, border 1px solid `#E2E8F0`, text `#0F172A`. Hover: `#F8FAFC` and border `#CBD5E1`.
- **Destructive / Stop**: Solid `#DC2626` background, `#FFFFFF` text. Used for real-time monitoring termination ("Stop listening", "End call").

### 2. Verdict Badges & Status Chips
- **Geometry**: Height 28px, 6px border radius, inline-flex with 8px horizontal padding, 6px internal gap between icon and label.
- **Implementation**:
  - *Likely Real*: `#ECFDF5` background, `#A7F3D0` border, `#065F46` text, with SVG checkmark.
  - *Uncertain*: `#FFFBEB` background, `#FDE68A` border, `#92400E` text, with SVG warning triangle.
  - *Likely Synthetic*: `#FEF2F2` background, `#FECACA` border, `#991B1B` text, with SVG dimensional cross.

### 3. Probability Gauge Component
- Horizontal track spanning 0.00 to 1.00 fake probability, height 12px, background `#E2E8F0` with 6px radius.
- **Decision Threshold Marker**: 2px wide vertical rule (`#0F172A`) intersecting the track at the configured model split point (e.g., 0.50).
- **Uncertainty Region**: Shaded background block (`#FDE68A` with 30% alpha) flanking the decision threshold marker to visibly demarcate the inconclusive decision window.
- **Current Reading Indicator**: 4px wide rounded pin indicator positioned along the track, color-coded dynamically to the matching semantic verdict token.

### 4. Tabular Data Tables
- Header row with `#F8FAFC` background, 1px bottom border `#CBD5E1`, text uppercase 11px font weight 600 `#64748B`.
- Row height: 48px fixed. Hover state `#F1F5F9`. Cell divider hairlines in `#F1F5F9`.
- Numeric data columns right-aligned utilizing `label-numeric` (tabular JetBrains Mono).

### 5. Rolling Timeline Chart Container
- Frame: White card with 12px radius, 1px border `#E2E8F0`, padding 16px.
- Grid canvas: Inset `#FAFAFA` with horizontal guide-lines at 0.0, 0.5, and 1.0 probability.
- Real-time window plotting: Solid line (`#2563EB`) with shaded underfill, accompanied by a horizontal dashed line (`#94A3B8`) indicating decision threshold, and an ambient highlighted band covering the uncertain range.

### 6. Advisory Alert Banners
- Non-modal, full-width container positioned at the top of active streaming panes.
- Styling for synthetic detection: Border-l 4px solid `#DC2626`, background `#FEF2F2`, 1px border `#FECACA`, text `#991B1B`. Dismissible icon right-aligned.