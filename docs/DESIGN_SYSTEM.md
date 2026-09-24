# StreamFlow Pro — Design System & Visual Specification

**Version:** 1.0.0  
**Theme Model:** Dark-First with Full Light Mode & System Preference Support  
**Design Philosophy:** Modern, Media-Focused, Minimalist, Fast, Restrained Animations  

---

## 1. Visual Identity

StreamFlow Pro is built to feel like a high-end commercial media creation and downloading desktop workstation. It eliminates generic SaaS dashboard tropes, database grids, and excessive rounded cards in favor of content-forward hierarchy, precision typography, and restrained depth.

---

## 2. Design Tokens (CSS Variables)

All components consume CSS design tokens defined at the root. Direct hardcoded hex values in component styling are prohibited.

### 2.1 Color Palette

| Token | Dark Mode Value | Light Mode Value | Description |
| :--- | :--- | :--- | :--- |
| `--background` | `#0B0D12` | `#F8FAFC` | Base application viewport canvas |
| `--surface` | `#12161D` | `#FFFFFF` | Primary content panels, cards, sidebar |
| `--surface-elevated` | `#181D26` | `#F1F5F9` | Modals, dropdowns, floating previews, badges |
| `--border` | `#242B36` | `#E2E8F0` | Subtle hairline dividers and container bounds |
| `--border-focus` | `#6366F1` | `#4F46E5` | Active focus ring indicator |
| `--foreground` | `#F5F7FA` | `#0F172A` | Primary heading and high-contrast text |
| `--foreground-muted` | `#A1A8B3` | `#475569` | Secondary subtitles, metadata, labels |
| `--foreground-subtle` | `#6B7280` | `#94A3B8` | Timestamps, inactive states, placeholder text |
| `--primary` | `#6366F1` | `#4F46E5` | Primary CTA, active navigation, key highlights |
| `--primary-hover` | `#818CF8` | `#4338CA` | Hover state for primary buttons |
| `--success` | `#34D399` | `#059669` | Completed status, engine running |
| `--warning` | `#FBBF24` | `#D97706` | Paused status, retrying, warnings |
| `--danger` | `#F87171` | `#DC2626` | Failed downloads, cancel actions, errors |
| `--accent-cyan` | `#38BDF8` | `#0284C7` | Media progress bar gradient & stream highlights |

---

## 3. Typography Scale

- **Primary Font Family:** `'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif`
- **Monospace Font Family:** `'JetBrains Mono', 'Fira Code', 'Consolas', monospace` (Used for ETA, transfer speed, file sizes, and timecodes)

| Scale | Size | Line Height | Weight | Typical Usage |
| :--- | :--- | :--- | :--- | :--- |
| `text-xs` | 11px (0.6875rem) | 16px | 500 / 600 | Quality badges, micro-labels, duration pills |
| `text-sm` | 13px (0.8125rem) | 20px | 400 / 500 | Metadata, channel names, speed/ETA data |
| `text-base` | 14px (0.875rem) | 22px | 400 / 500 | Body text, input text, table rows |
| `text-md` | 16px (1.000rem) | 24px | 600 | Card titles, section subheadings |
| `text-lg` | 18px (1.125rem) | 26px | 600 / 700 | Navigation headings, modal headers |
| `text-xl` | 22px (1.375rem) | 28px | 700 / 800 | Primary hero title, view titles |

---

## 4. Spacing & Elevation System

- **Hairline Borders:** `1px solid var(--border)`
- **Border Radii:**
  - `rounded-lg`: 8px (Buttons, badges, option menus)
  - `rounded-xl`: 12px (Cards, media preview cards, queue items)
  - `rounded-2xl`: 16px (Modals, main view panels)
  - `rounded-full`: 9999px (Pills, tag badges, status dots)
- **Shadows:**
  - Subdued elevation: `0 4px 12px rgba(0, 0, 0, 0.25)`
  - Elevated modal: `0 20px 48px rgba(0, 0, 0, 0.45)`

---

## 5. Component Guidelines

### 5.1 Primary Download Input (The Hero Element)
- Prominent, central placement on the New Download page.
- Clear visual cues: clipboard paste shortcut (`Ctrl+V`), clear button, instant validation indicator.
- Progressive disclosure: format selection and quality pills appear below upon URL entry.
- Advanced settings (codec, subtitles, metadata embedding) tucked inside an elegant collapsible panel.

### 5.2 Media Queue Row
- Horizontal layout with 16:9 thumbnail preview.
- Title and channel truncated cleanly with tooltip on hover.
- High-precision progress track with animated pulse for active state.
- Tabular figures for transfer speed, ETA, and size to eliminate layout shifting.
- Action buttons: Pause (`⏸`), Resume (`▶`), Cancel (`✕`), Open Folder (`📁`).

### 5.3 Icon System
- **Lucide React** icons exclusively with standard `stroke-width={2}`.
- Zero emoji icons used for UI controls.
- Consistent icon sizing:
  - 14px for micro badges and inline text
  - 16px for button icons and list items
  - 20px for sidebar navigation
