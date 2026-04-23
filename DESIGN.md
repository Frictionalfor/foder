# Foder Website — Design Document

Complete specification for the foder landing page.
Built with React + Vite + Tailwind CSS + Framer Motion.

---

## Brand Identity

**Name:** Foder
**Tagline:** Your local AI coding agent. No cloud. No keys. Just code.
**Sub-tagline:** Runs entirely on your machine with Ollama.
**Author:** Frictionalfor
**GitHub:** https://github.com/Frictionalfor/foder
**GitHub Profile:** https://github.com/Frictionalfor

---

## Color System

### Primary Palette (default — Green theme)
```
Background:     #0a0a0a   (near black)
Surface:        #111111   (card backgrounds)
Border:         #1a1a1a   (subtle borders)
Accent:         #4ADE80   (green — primary CTA, highlights)
Accent Light:   #BBF7D0   (light green — text on dark)
Accent Dark:    #166534   (deep green — borders, shadows)
Text Primary:   #ffffff
Text Secondary: #9ca3af   (gray-400)
Text Dim:       #6b7280   (gray-500)
```

### All 6 Themes (match foder CLI themes exactly)
```
green:  #4ADE80 / #BBF7D0 / #166534
teal:   #06B6D4 / #67E8F9 / #164E63
amber:  #F59E0B / #FDE68A / #78350F
rose:   #FB7185 / #FECDD3 / #9F1239
blue:   #38BDF8 / #BAE6FD / #075985
lime:   #A3E635 / #D9F99D / #3F6212
```

### Typography
```
Font:       JetBrains Mono (monospace — everything)
Fallback:   Fira Code, Consolas, monospace
Import:     Google Fonts
Sizes:
  Hero title:    clamp(3rem, 8vw, 7rem)
  Section title: 2.5rem
  Body:          1rem
  Small:         0.875rem
  Code:          0.9rem
```

---

## Page Structure & Sections

### 1. Navigation Bar
- Fixed top, blur backdrop (`backdrop-blur-md bg-black/60`)
- Left: ASCII logo `◆ foder` in accent color, links to top
- Center: links — Features, Demo, Install, Themes
- Right: GitHub star button (shows star count via API), "Get Started" CTA button
- On scroll: border-bottom appears with subtle glow
- Mobile: hamburger menu with slide-down drawer

**Animation:** fade-in + slide-down on load (0.3s ease)

---

### 2. Hero Section
Full viewport height. Dark background with animated grid.

**Background:**
- CSS grid pattern: `repeating-linear-gradient` creating a subtle dot/line grid
- Animated gradient orbs: 2-3 large blurred circles in accent color, slowly drifting (`animation: float 8s ease-in-out infinite`)
- Particle effect: 20-30 small dots floating upward slowly

**Content (centered):**
```
[animated ASCII logo — see below]

Your local AI coding agent.
No cloud. No keys. Just code.

[subtitle in dim color]
Powered by Ollama · Runs on your machine · Open source

[two CTA buttons]
  [Get Started →]   [View on GitHub ↗]

[install command box]
  pip install foder
  [copy icon]
```

**ASCII Logo Animation:**
- The foder logo renders character by character (typewriter effect, 20ms per char)
- Each row has a different color matching the theme gradient
- After render: subtle pulse glow animation on the whole logo
- Logo:
```
  ███████  ██████  ██████  ███████ ██████
  ██      ██    ██ ██   ██ ██      ██   ██
  █████   ██    ██ ██   ██ █████   ██████
  ██      ██    ██ ██   ██ ██      ██   ██
  ██       ██████  ██████  ███████ ██   ██
```

**CTA Buttons:**
- Primary: solid accent color, hover → scale(1.05) + glow shadow
- Secondary: outlined, hover → fill with accent at 20% opacity
- Both: `border-radius: 6px`, `padding: 12px 28px`

**Install Box:**
- Dark surface card, monospace font
- `$ pip install foder` with syntax highlight ($ in dim, command in accent)
- Copy button: clipboard icon, on click → checkmark + "Copied!" for 2s
- Subtle border glow on hover

**Scroll indicator:** animated bouncing arrow at bottom of hero

---

### 3. Stats Bar
Full-width strip between hero and features.

```
[  42 Tests  ]  [  6 Themes  ]  [  5 Tools  ]  [  0 Cloud  ]  [  100% Local  ]
```

- Numbers animate counting up when scrolled into view (0 → final value, 1.5s)
- Separated by vertical dividers
- Background: slightly lighter than page (`#111111`)
- Border top/bottom: `1px solid #1a1a1a`

---

### 4. Features Section

**Title:** `What foder can do`
**Subtitle:** `A complete coding agent that lives in your terminal`

**Grid:** 3 columns on desktop, 2 on tablet, 1 on mobile

**Feature Cards (9 total):**

| Icon | Title | Description |
|------|-------|-------------|
| ◆ | Local LLM | Powered by Ollama. qwen2.5-coder, llama3, any model you pull. |
| ▸ | File Operations | Read, write, create files and directories. All scoped to your workspace. |
| $ | Shell Execution | Run terminal commands directly. Risky commands ask for confirmation. |
| ~ | Session Memory | Conversation saved across sessions. Resume where you left off. |
| ⚙ | 6 Color Themes | Green, Teal, Amber, Rose, Blue, Lime. Persisted across sessions. |
| @ | File Injection | @filename injects file content into your prompt automatically. |
| ◈ | /pin Command | Pin files to every prompt. Never type @file again. |
| ↩ | /undo | Revert any file write instantly. |
| ≋ | /snapshot | Save workspace state. See exactly what changed. |

**Card Design:**
- Background: `#111111`
- Border: `1px solid #1a1a1a`
- Border-radius: `12px`
- Padding: `24px`
- Icon: large, in accent color, top-left
- Hover: border color → accent, subtle glow, `translateY(-4px)` (0.2s ease)
- Entrance: staggered fade-in + slide-up as they scroll into view (50ms delay between cards)

---

### 5. Live Demo Terminal Section

**Title:** `See it in action`
**Subtitle:** `Watch foder build real projects`

**Terminal Window:**
- Realistic macOS-style terminal chrome (3 colored dots: red/yellow/green)
- Title bar: `foder — ~/projects/myapp`
- Dark background: `#0d0d0d`
- Border: `1px solid #2a2a2a`
- Border-radius: `12px`
- Box shadow: `0 25px 50px rgba(0,0,0,0.5)`
- Font: JetBrains Mono, 14px

**Demo Sequences (auto-play, loop):**

Sequence 1 — Create Python file:
```
qwen2.5-coder ❙ foder ❯ make a password generator in python
  ▸ write  password_gen.py
  ◆ foder  Created password_gen.py. Run: python3 password_gen.py
qwen2.5-coder ❙ foder ❯ python3 password_gen.py
  $ python3 password_gen.py
  Generated: xK#9mP2$vL@nQ7
  ✓  0.12s
```

Sequence 2 — Build HTML app:
```
qwen2.5-coder ❙ foder ❯ create a todo app in vanilla HTML CSS JS
  ▸ write  index.html
  ▸ write  style.css
  ▸ write  app.js
  ◆ foder  Todo app created. Open index.html in your browser.
```

Sequence 3 — Git workflow:
```
qwen2.5-coder ❙ foder ❯ /git
  branch   main
  changes
    M  src/App.js
    ?  style.css
  recent commits
    a3f2c1 add dark mode toggle
```

**Typing animation:** each character types at 40ms, commands pause 800ms before executing, results appear instantly.

**Tab buttons above terminal:** "Python" | "HTML/CSS/JS" | "Git" — click to jump to that sequence.

---

### 6. Themes Showcase Section

**Title:** `6 themes. Pick yours.`
**Subtitle:** `All themes persist across sessions`

**Layout:** 6 theme cards in a 3x2 grid (2x3 on mobile)

**Each Theme Card:**
- Mini terminal preview showing the foder prompt in that theme's colors
- Theme name below
- Click → entire website switches to that theme (accent color changes everywhere)
- Active theme: glowing border in that theme's accent color
- Hover: scale(1.03), border brightens

**Theme switching animation:**
- CSS custom properties (`--accent`, `--accent-light`, `--accent-dark`) update
- All colored elements transition: `transition: color 0.3s, background-color 0.3s, border-color 0.3s`

---

### 7. Install Section

**Title:** `Get started in 30 seconds`

**Three tabs:** Linux/macOS | Windows | Manual

**Linux/macOS:**
```bash
git clone https://github.com/Frictionalfor/foder.git
cd foder
bash install.sh
```

**Windows:**
```powershell
git clone https://github.com/Frictionalfor/foder.git
cd foder
powershell -ExecutionPolicy Bypass -File install.ps1
```

**Manual:**
```bash
pip install -e .
```

**Then:**
```bash
ollama pull qwen2.5-coder:3b
foder
```

**Code blocks:**
- Dark background, syntax highlighted
- Copy button top-right of each block
- Language label top-left (bash / powershell)

**Below install:** "Requires Python 3.10+ and Ollama" with links to both.

---

### 8. Commands Reference Section

**Title:** `Everything at your fingertips`

**Two-column table:**

| Command | What it does |
|---------|-------------|
| `/switch` | Change model mid-session |
| `/theme` | Pick a color theme |
| `/git` | Show git status |
| `/pin @file` | Pin file to every prompt |
| `/undo` | Revert last file write |
| `/diff` | Show what changed |
| `/snapshot` | Save workspace state |
| `/cost` | Session stats + token usage |
| `/arch` | Architecture diagram |
| `!!` | Re-run last shell command |
| `@filename` | Inject file into prompt |
| `\` at end of line | Multi-line input |

**Design:** monospace font, accent color for commands, dim for descriptions.
Hover on each row: subtle highlight.

---

### 9. About / Author Section

**Title:** `Built by a developer, for developers`

**Content:**
- Short paragraph about foder's origin
- Author card:
  - Avatar (GitHub profile picture via `https://github.com/Frictionalfor.png`)
  - Name: Frictionalfor
  - Bio: "17-year-old developer building tools that make coding faster"
  - Links: GitHub profile, Twitter/X (if available)

**GitHub Stats (live via GitHub API):**
- Stars count
- Forks count
- Last updated
- Language: Python

**Displayed as:** small stat pills below the repo card

---

### 10. Footer

**Layout:** 3 columns

**Column 1 — Brand:**
```
◆ foder
Your local AI coding agent.
v0.1.0
```

**Column 2 — Links:**
```
GitHub Repo
GitHub Profile
README
CHANGELOG
TRY_THIS
```

**Column 3 — Community:**
```
Report a Bug (GitHub Issues)
Request a Feature
Star on GitHub
```

**Bottom bar:**
```
Made with ◆ by Frictionalfor · MIT License · 2026
```

---

## Animations & Transitions — Full Spec

### Page Load
1. Nav fades in (0ms, 300ms duration)
2. Hero logo types out character by character (300ms delay, 20ms/char)
3. Hero text fades up (800ms delay, 500ms duration)
4. Hero buttons fade up (1100ms delay, 400ms duration)
5. Install box fades up (1300ms delay, 400ms duration)

### Scroll Animations (Framer Motion `whileInView`)
- All sections: `initial={{ opacity: 0, y: 40 }}` → `animate={{ opacity: 1, y: 0 }}`
- Duration: 0.6s, ease: "easeOut"
- Feature cards: staggered 0.05s between each
- Stats numbers: count-up animation triggered on viewport entry

### Hover States
- Cards: `translateY(-4px)`, border glow, 0.2s ease
- Buttons: `scale(1.05)`, glow shadow, 0.15s ease
- Nav links: accent color underline slides in from left
- Theme cards: `scale(1.03)`, 0.2s ease
- Table rows: background `rgba(accent, 0.05)`

### Terminal Demo
- Cursor blinks at 1s interval
- Characters type at 40ms each
- Command pause: 600ms before "executing"
- Tool call lines appear with 100ms delay between each
- Loop: 3s pause between sequences

### Theme Switching
- All CSS custom properties transition simultaneously
- Duration: 0.4s
- Easing: ease-in-out
- Gradient orbs in hero also change color

### Scroll Behavior
- Smooth scroll: `scroll-behavior: smooth`
- Section offset for fixed nav: `scroll-margin-top: 80px`
- Progress bar at top of page (thin accent-colored line)

---

## Responsive Breakpoints

```
Mobile:   < 640px   (sm)
Tablet:   640-1024px (md)
Desktop:  > 1024px  (lg)
```

- Nav: hamburger on mobile
- Hero: logo smaller on mobile, buttons stack vertically
- Features: 1 col mobile, 2 col tablet, 3 col desktop
- Themes: 2 col mobile, 3 col tablet, 6 col desktop
- Terminal: full width on mobile, max-width 800px on desktop
- Footer: stacked on mobile, 3 col on desktop

---

## Performance

- Fonts: preloaded via `<link rel="preload">`
- Images: none (pure CSS/SVG)
- GitHub API: cached in localStorage for 1 hour
- Animations: `will-change: transform` on animated elements
- Code splitting: Vite handles automatically
- Target: Lighthouse score > 90

---

## Deployment

**GitHub Pages:**
```bash
npm run build
# deploy dist/ to gh-pages branch
```

**Vercel (recommended):**
- Connect GitHub repo
- Build command: `npm run build`
- Output dir: `dist`
- Auto-deploys on push to main

**Custom domain:** optional, set in Vercel dashboard

---

## File Structure

```
website/
├── index.html
├── package.json
├── vite.config.js
├── tailwind.config.js
├── postcss.config.js
├── src/
│   ├── main.jsx
│   ├── App.jsx
│   ├── index.css          (Tailwind + custom CSS vars)
│   └── components/
│       ├── Nav.jsx
│       ├── Hero.jsx
│       ├── StatsBar.jsx
│       ├── Features.jsx
│       ├── Terminal.jsx
│       ├── Themes.jsx
│       ├── Install.jsx
│       ├── Commands.jsx
│       ├── About.jsx
│       └── Footer.jsx
```

---

## Links to Include

| Label | URL |
|-------|-----|
| GitHub Repo | https://github.com/Frictionalfor/foder |
| GitHub Profile | https://github.com/Frictionalfor |
| Report Bug | https://github.com/Frictionalfor/foder/issues |
| New Feature | https://github.com/Frictionalfor/foder/issues/new |
| Releases | https://github.com/Frictionalfor/foder/releases |
| Ollama | https://ollama.com |
| Python | https://python.org |
