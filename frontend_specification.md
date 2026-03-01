# Frontend Specification Document
## AI Assistant Interface: Claude-Gemini Hybrid Design

---

## 1. Executive Overview

### 1.1 Design Philosophy
This frontend specification describes a next-generation AI assistant interface that combines:
- **Claude's elegance**: Clean, minimal aesthetic with warm amber accents, generous whitespace, and typography-focused design
- **Gemini's versatility**: Multi-agent capabilities, model selection, and conversation branching
- **Kimi's agent ecosystem**: Specialized AI agents for different tasks and workflows

### 1.2 Core Principles
1. **Clarity First**: Every element serves a purpose; no decorative noise
2. **Warm Minimalism**: Clean interfaces with human-friendly amber/coral warmth
3. **Conversational Flow**: Natural dialogue patterns with contextual awareness
4. **Agent Transparency**: Clear indication of which agent is active and why
5. **Progressive Disclosure**: Advanced features available but not overwhelming

---

## 2. Visual Design System

### 2.1 Color Palette

#### Primary Colors
| Token | Hex | Usage |
|-------|-----|-------|
| `--amber-50` | `#FFFBEB` | Light backgrounds, hover states |
| `--amber-100` | `#FEF3C7` | Selected states, highlights |
| `--amber-200` | `#FDE68A` | Borders, accents |
| `--amber-400` | `#FBBF24` | Primary accent, buttons |
| `--amber-500` | `#F59E0B` | Active states, links |
| `--amber-600` | `#D97706` | Primary brand color |

#### Neutral Colors
| Token | Hex | Usage |
|-------|-----|-------|
| `--gray-50` | `#F9FAFB` | Page background |
| `--gray-100` | `#F3F4F6` | Card backgrounds |
| `--gray-200` | `#E5E7EB` | Borders, dividers |
| `--gray-400` | `#9CA3AF` | Placeholder text |
| `--gray-600` | `#4B5563` | Secondary text |
| `--gray-800` | `#1F2937` | Primary text |
| `--gray-900` | `#111827` | Headings, emphasis |

#### Semantic Colors
| Token | Hex | Usage |
|-------|-----|-------|
| `--agent-coder` | `#3B82F6` | Code/Technical agent |
| `--agent-creative` | `#EC4899` | Creative/Writing agent |
| `--agent-research` | `#10B981` | Research/Analysis agent |
| `--agent-data` | `#8B5CF6` | Data/Visualization agent |
| `--agent-general` | `#F59E0B` | General assistant (default) |

### 2.2 Typography

#### Font Stack
```css
--font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
--font-mono: 'JetBrains Mono', 'Fira Code', 'SF Mono', Consolas, monospace;
--font-display: 'Inter', sans-serif; /* For headings */
```

#### Type Scale
| Level | Size | Weight | Line Height | Letter Spacing | Usage |
|-------|------|--------|-------------|----------------|-------|
| H1 | 2.5rem (40px) | 700 | 1.2 | -0.02em | Page titles |
| H2 | 2rem (32px) | 600 | 1.25 | -0.01em | Section headers |
| H3 | 1.5rem (24px) | 600 | 1.3 | 0 | Card titles |
| H4 | 1.25rem (20px) | 600 | 1.4 | 0 | Subsection headers |
| Body Large | 1.125rem (18px) | 400 | 1.6 | 0 | Primary content |
| Body | 1rem (16px) | 400 | 1.6 | 0 | Default text |
| Body Small | 0.875rem (14px) | 400 | 1.5 | 0 | Secondary text |
| Caption | 0.75rem (12px) | 500 | 1.4 | 0.01em | Labels, metadata |
| Code | 0.875rem (14px) | 400 | 1.6 | 0 | Inline code |

### 2.3 Spacing System

#### Base Unit: 4px
| Token | Value | Usage |
|-------|-------|-------|
| `--space-1` | 4px | Tight spacing |
| `--space-2` | 8px | Icon padding |
| `--space-3` | 12px | Compact elements |
| `--space-4` | 16px | Default padding |
| `--space-5` | 20px | Card padding |
| `--space-6` | 24px | Section gaps |
| `--space-8` | 32px | Large sections |
| `--space-10` | 40px | Page margins |
| `--space-12` | 48px | Major sections |

### 2.4 Border Radius
| Token | Value | Usage |
|-------|-------|-------|
| `--radius-sm` | 4px | Buttons, inputs |
| `--radius-md` | 8px | Cards, containers |
| `--radius-lg` | 12px | Modals, panels |
| `--radius-xl` | 16px | Large cards |
| `--radius-full` | 9999px | Pills, avatars |

### 2.5 Shadows
| Token | Value | Usage |
|-------|-------|-------|
| `--shadow-sm` | `0 1px 2px rgba(0,0,0,0.05)` | Subtle elevation |
| `--shadow-md` | `0 4px 6px -1px rgba(0,0,0,0.1)` | Cards |
| `--shadow-lg` | `0 10px 15px -3px rgba(0,0,0,0.1)` | Modals, dropdowns |
| `--shadow-amber` | `0 4px 14px rgba(245,158,11,0.25)` | Primary button glow |

---

## 3. Layout Architecture

### 3.1 Overall Structure
```
┌─────────────────────────────────────────────────────────────────┐
│  SIDEBAR (240px)    │  MAIN CONTENT AREA (flex: 1)              │
│  ─────────────────  │  ───────────────────────────────────────  │
│  ┌─────────────┐   │  ┌─────────────────────────────────────┐  │
│  │   LOGO      │   │  │         HEADER (56px)               │  │
│  │  (Agent     │   │  │  [Model Selector] [Agent Badge]     │  │
│  │   Hub)      │   │  └─────────────────────────────────────┘  │
│  └─────────────┘   │                                           │
│                    │  ┌─────────────────────────────────────┐  │
│  ┌─────────────┐   │  │                                     │  │
│  │ NEW CHAT    │   │  │      CONVERSATION AREA              │  │
│  │   (+)       │   │  │                                     │  │
│  └─────────────┘   │  │   [Message Stream]                  │  │
│                    │  │   [Agent Switch Indicators]         │  │
│  CONVERSATIONS     │  │   [Code Blocks]                     │  │
│  ──────────────    │  │   [File Attachments]                │  │
│  [Today]           │  │                                     │  │
│    - Project Alpha │  └─────────────────────────────────────┘  │
│    - Research Q    │                                           │
│  [Yesterday]       │  ┌─────────────────────────────────────┐  │
│    - Code Review   │  │         INPUT AREA                  │  │
│    - Brainstorm    │  │  ┌─────────────────────────────┐   │  │
│  [Previous 7 Days] │  │  │  [Attach] [Text Input] [Send]│   │  │
│    - ...           │  │  └─────────────────────────────┘   │  │
│                    │  │  [Agent Suggestion Chips]          │  │
│  ──────────────    │  └─────────────────────────────────────┘  │
│  [Settings]        │                                           │
│  [Help]            │                                           │
└────────────────────┴───────────────────────────────────────────┘
```

### 3.2 Responsive Breakpoints
| Breakpoint | Width | Layout Changes |
|------------|-------|----------------|
| Mobile | < 640px | Sidebar collapses to drawer, single column |
| Tablet | 640-1024px | Condensed sidebar (72px icons only) |
| Desktop | 1024-1440px | Full layout as specified |
| Large | > 1440px | Max-width container (1200px), centered |

### 3.3 Grid System
- **Container Max Width**: 1200px for content
- **Conversation Width**: 768px (optimal reading width)
- **Sidebar Width**: 240px (full), 72px (collapsed)
- **Gutter**: 24px

---

## 4. Component Specifications

### 4.1 Sidebar

#### Structure
```
┌────────────────────────┐
│  [LOGO] Agent Hub      │  ← 56px height
├────────────────────────┤
│  [+] New Conversation  │  ← Primary action button
├────────────────────────┤
│  TODAY                 │  ← Section header (uppercase, 11px)
│  [icon] Project Alpha  │  ← Conversation item
│  [icon] Research Q...  │  ← Truncated at 24 chars
│                        │
│  YESTERDAY             │
│  [icon] Code Review    │
│  [icon] Brainstorm...  │
│                        │
│  PREVIOUS 7 DAYS       │
│  [icon] ...            │
├────────────────────────┤
│  [icon] Settings       │  ← Footer actions
│  [icon] Help & FAQ     │
└────────────────────────┘
```

#### Styling
- Background: `--gray-50`
- Border-right: 1px solid `--gray-200`
- Padding: `--space-3` (12px)
- Conversation item hover: `--amber-50` background
- Active conversation: `--amber-100` background, left border 3px `--amber-500`

#### Behavior
- Collapses to icon-only on tablet (72px)
- Becomes slide-out drawer on mobile
- Supports drag-to-reorder conversations
- Context menu on right-click (Rename, Delete, Archive)

### 4.2 Header

#### Structure
```
┌────────────────────────────────────────────────────────────────┐
│ [Model: Claude 3.5 Sonnet ▼]    [Agent: General ▼]   [Share]  │
└────────────────────────────────────────────────────────────────┘
```

#### Model Selector Dropdown
```
┌─────────────────────────────────┐
│  Select Model                   │
├─────────────────────────────────┤
│  [star] Claude 3.5 Sonnet      │ ← Recommended (default)
│      Most capable model         │
│                                 │
│  Claude 3.5 Haiku              │ ← Fast option
│      Fast, cost-effective       │
│                                 │
│  Claude 3 Opus                 │ ← Complex tasks
│      Deep reasoning, coding     │
└─────────────────────────────────┘
```

#### Agent Selector Dropdown
```
┌─────────────────────────────────┐
│  Select Agent                   │
├─────────────────────────────────┤
│  [A] Auto-Route (Recommended)  │ ← Default
│      Automatically selects best │
│      agent for your task        │
│                                 │
│  ── Specialized Agents ──       │
│  [C] Coder                      │
│      Code, debugging, technical │
│                                 │
│  [W] Writer                     │
│      Creative writing, editing  │
│                                 │
│  [R] Researcher                 │
│      Analysis, summaries, facts │
│                                 │
│  [D] Data Analyst               │
│      Charts, data visualization │
│                                 │
│  [L] Learner                    │
│      Explanations, tutoring     │
└─────────────────────────────────┘
```

### 4.3 Conversation Area

#### Message Structure
```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  [Avatar] User Message                                       │
│  ─────────────────────────────────────────────────────────  │
│  This is the user's input text. It can be multiple lines    │
│  and may include code, formatting, or other content.        │
│                                                             │
│                                    [Edit] [Copy] [Delete]   │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  [Agent Badge: Coder] AI Response                           │
│  ─────────────────────────────────────────────────────────  │
│  Here's the solution to your problem:                       │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 1  function calculateTotal(items) {                 │   │
│  │ 2    return items.reduce((sum, item) => {           │   │
│  │ 3      return sum + (item.price * item.quantity);   │   │
│  │ 4    }, 0);                                         │   │
│  │ 5  }                                                │   │
│  └─────────────────────────────────────────────────────┘   │
│  [Copy] [Insert at cursor] [Explain this code]              │
│                                                             │
│  Let me explain how this works...                           │
│                                                             │
│                                    [Copy] [Regenerate] [👍] │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

#### Message Bubble Styling

**User Messages:**
- Background: Transparent (no bubble)
- Text color: `--gray-900`
- Font weight: 400
- Max width: 100%

**AI Messages:**
- Background: White
- Border: 1px solid `--gray-100`
- Border radius: `--radius-lg` (12px)
- Shadow: `--shadow-sm`
- Padding: `--space-5` (20px)

#### Agent Indicator Badge
```
┌────────────────────────┐
│ [icon] Agent Name [▼]  │
└────────────────────────┘
```
- Position: Top-left of AI message
- Background: Agent color at 10% opacity
- Text: Agent color, `--font-caption` size
- Click to see agent capabilities or switch

### 4.4 Code Block Component

#### Structure
```
┌────────────────────────────────────────────────────────────────┐
│ typescript                              [Copy] [Download] [▶] │  ← Header
├────────────────────────────────────────────────────────────────┤
│ 1  import { useState } from 'react';                           │
│ 2                                                              │
│ 3  function Counter() {                                        │
│ 4    const [count, setCount] = useState(0);                    │
│ 5    return (                                                  │
│ 6      <button onClick={() => setCount(c => c + 1)}>          │
│ 7        Count: {count}                                        │
│ 8      </button>                                               │
│ 9    );                                                        │
│ 10 }                                                           │
└────────────────────────────────────────────────────────────────┘
```

#### Styling
- Background: `#1E1E1E` (VS Code dark)
- Border radius: `--radius-md`
- Font: `--font-mono`
- Line numbers: `--gray-500`, right-aligned
- Syntax highlighting: VS Code Dark+ theme

### 4.5 Input Area

#### Structure
```
┌────────────────────────────────────────────────────────────────┐
│ [📎]  Type your message...                          [➤] [🎤]  │
└────────────────────────────────────────────────────────────────┘
         ↑                                               ↑
    Attach button                                   Send button
```

#### Expanded State (Focused)
```
┌────────────────────────────────────────────────────────────────┐
│  ┌──────────────────────────────────────────────────────────┐ │
│  │  [📎] Type your message...                               │ │
│  │                                                          │ │
│  │  Shift+Enter for new line                                │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                                │
│  Suggested: [Summarize] [Explain like I'm 5] [Give examples]  │
│                                                                │
│  [Claude 3.5 Sonnet] [Auto-Route Agent]              [➤ Send] │
└────────────────────────────────────────────────────────────────┘
```

#### Styling
- Container: White background, `--shadow-lg` when focused
- Border: 1px solid `--gray-200`, transitions to `--amber-400` on focus
- Border radius: `--radius-xl` (16px)
- Min height: 56px
- Max height: 200px (auto-expands)

### 4.6 Agent Switch Indicator

When agents collaborate on a response:
```
┌────────────────────────────────────────────────────────────────┐
│  [Researcher] Found 5 relevant sources...                      │
│  ─────────────────────────────────────────────────────────────│
│  [Coder] Generating code solution...                           │
│  ─────────────────────────────────────────────────────────────│
│  [Writer] Formatting final response...                         │
│  ─────────────────────────────────────────────────────────────│
│  [General] Here's what I found:                                │
│  ...                                                           │
└────────────────────────────────────────────────────────────────┘
```

Each agent switch shows:
- Agent avatar/icon
- Agent name with color coding
- Brief status/action description
- Progress indicator (if loading)

---

## 5. Agent System Interface

### 5.1 Agent Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER INPUT                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ROUTER AGENT (Default)                       │
│         Analyzes intent and routes to specialized agent         │
└─────────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
   │   CODER     │    │   WRITER    │    │  RESEARCHER │
   │   (Blue)    │    │   (Pink)    │    │   (Green)   │
   └─────────────┘    └─────────────┘    └─────────────┘
          │                   │                   │
          └───────────────────┼───────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    RESPONSE COMPOSER                            │
│         Combines outputs into cohesive response                 │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 Agent Cards

#### Agent Selection Grid
```
┌─────────────────────────────────────────────────────────────────┐
│  Choose an Agent                                                │
│  Select the best agent for your task, or let us auto-route      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │    [AUTO]    │  │    [CODE]    │  │   [WRITE]    │          │
│  │              │  │              │  │              │          │
│  │ Auto-Route   │  │    Coder     │  │    Writer    │          │
│  │ Recommended  │  │              │  │              │          │
│  │              │  │ Code, debug, │  │ Creative     │          │
│  │ Let us pick  │  │ technical    │  │ writing,     │          │
│  │ the best     │  │ tasks        │  │ editing      │          │
│  │ agent        │  │              │  │              │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  [SEARCH]    │  │   [DATA]     │  │   [LEARN]    │          │
│  │              │  │              │  │              │          │
│  │  Researcher  │  │Data Analyst  │  │   Learner    │          │
│  │              │  │              │  │              │          │
│  │ Facts,       │  │ Charts,      │  │ Explanations,│          │
│  │ analysis,    │  │ visualiza-   │  │ tutoring,    │          │
│  │ summaries    │  │ tion         │  │ learning     │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### Agent Card Styling
- Size: 160px x 200px
- Border: 1px solid `--gray-200`
- Border radius: `--radius-lg`
- Hover: `--shadow-md`, border color agent color
- Selected: 2px border agent color, `--shadow-amber`
- Icon: 48px, agent color background at 10%

### 5.3 Agent Capabilities Panel

When clicking an agent badge:
```
┌─────────────────────────────────────────────────────────────────┐
│  [Coder] Agent Details                                    [×]   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────┐                                                      │
│  │  [</>] │  Coder Agent                                        │
│  └────────┘  Specialized in code generation and technical tasks   │
│                                                                  │
│  Capabilities:                                                   │
│  ✓ Write code in 20+ languages                                  │
│  ✓ Debug and fix errors                                         │
│  ✓ Explain code concepts                                        │
│  ✓ Generate tests                                               │
│  ✓ Optimize performance                                         │
│                                                                  │
│  Best for:                                                       │
│  • Writing functions and scripts                                │
│  • Debugging errors                                             │
│  • Code reviews                                                 │
│  • Learning programming concepts                                │
│                                                                  │
│  [Switch to Coder]  [Keep Current Agent]                        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. Conversation Features

### 6.1 Message Actions

#### Hover Actions (per message)
```
┌─────────────────────────────────────────────────────────────────┐
│  Message content here...                                        │
│                                          [Copy] [Edit] [Share]  │
└─────────────────────────────────────────────────────────────────┘
```

#### Context Menu (right-click)
```
┌─────────────────────────┐
│  Copy                   │
│  Copy as Markdown       │
│  ─────────────────────  │
│  Edit Message           │
│  Delete Message         │
│  ─────────────────────  │
│  Regenerate Response    │
│  Change Agent           │
│  ─────────────────────  │
│  Quote in New Chat      │
└─────────────────────────┘
```

### 6.2 Branching Conversations

When user edits a previous message:
```
┌─────────────────────────────────────────────────────────────────┐
│  [Original conversation continues here]                         │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  [Branch icon] This conversation has a branch          │   │
│  │  View original path →                                   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  [Edited message - new branch starts here]                      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 6.3 File Attachments

#### Attachment Preview
```
┌─────────────────────────────────────────────────────────────────┐
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ [📄] document.pdf                    [×]  2.4 MB       │   │
│  │  12 pages • PDF                                          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ [🖼️] screenshot.png                  [×]  856 KB       │   │
│  │  1920×1080 • PNG                                         │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

#### Supported File Types
| Type | Icon | Preview | Max Size |
|------|------|---------|----------|
| PDF | 📄 | Thumbnail + page count | 32MB |
| Image | 🖼️ | Full preview | 20MB |
| Code | 📋 | Syntax highlighted | 1MB |
| Document | 📝 | Text extraction | 32MB |
| Spreadsheet | 📊 | Table preview | 32MB |
| Audio | 🎵 | Waveform + transcript | 50MB |

---

## 7. Special Components

### 7.1 Thinking/Reasoning Display

For models that show reasoning:
```
┌─────────────────────────────────────────────────────────────────┐
│  [Thinking...] ▼                                                │
│  ─────────────────────────────────────────────────────────────  │
│  Let me work through this step by step:                         │
│  1. First, I need to understand what the user is asking...      │
│  2. The key concepts here are...                                │
│  [Show 5 more steps]                                            │
│                                                                  │
│  Final Answer:                                                  │
│  Based on my analysis...                                        │
└─────────────────────────────────────────────────────────────────┘
```

### 7.2 Tool Usage Indicators

When agents use tools:
```
┌─────────────────────────────────────────────────────────────────┐
│  [🔍] Searching the web...                                      │
│  [📊] Analyzing data...                                         │
│  [💻] Running code...                                           │
│  [🌐] Fetching from API...                                      │
└─────────────────────────────────────────────────────────────────┘
```

Each shows:
- Animated icon
- Tool name
- Brief description
- Progress state
- Cancel button (if applicable)

### 7.3 Suggestion Chips

Context-aware suggestions after responses:
```
┌─────────────────────────────────────────────────────────────────┐
│  Suggested follow-ups:                                          │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐               │
│  │ Tell me more│ │ Give me an  │ │ How does    │               │
│  │ about that  │ │ example     │ │ this compare│               │
│  └─────────────┘ └─────────────┘ └─────────────┘               │
└─────────────────────────────────────────────────────────────────┘
```

---

## 8. Empty States

### 8.1 New Conversation
```
┌─────────────────────────────────────────────────────────────────┐
│                                                                  │
│                         [LOGO]                                  │
│                                                                  │
│              How can I help you today?                          │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  [💡] Brainstorm ideas                                  │   │
│  │  [📝] Help me write                                     │   │
│  │  [💻] Code something                                    │   │
│  │  [📊] Analyze data                                      │   │
│  │  [🔍] Research a topic                                  │   │
│  └─────────────────────────────────────────────────────────┐   │
│                                                                  │
│  Or start typing below...                                       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 8.2 Loading State
```
┌─────────────────────────────────────────────────────────────────┐
│                                                                  │
│                    [Animated Logo]                              │
│                                                                  │
│                 Kimi is thinking...                             │
│                                                                  │
│              This may take a moment                             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 8.3 Error State
```
┌─────────────────────────────────────────────────────────────────┐
│                                                                  │
│                    [⚠️ Icon]                                    │
│                                                                  │
│              Something went wrong                               │
│                                                                  │
│         We couldn't generate a response.                        │
│         Please try again or rephrase your question.             │
│                                                                  │
│              [Try Again] [Start New Chat]                       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 9. Animations & Interactions

### 9.1 Micro-interactions

| Element | Trigger | Animation |
|---------|---------|-----------|
| Button hover | Mouse enter | Scale 1.02, shadow increase |
| Button click | Mouse down | Scale 0.98 |
| Message appear | New message | Fade in + slide up (200ms) |
| Typing indicator | AI responding | Bouncing dots |
| Code block | Expand/collapse | Height transition (300ms) |
| Sidebar | Collapse/expand | Width transition (250ms) |
| Toast notification | New event | Slide in from right |

### 9.2 Typing Indicator
```
┌─────────────────────────────────────────────────────────────────┐
│  Kimi is responding  ● ● ●                                      │
└─────────────────────────────────────────────────────────────────┘
```
- Three dots with staggered bounce animation
- Color: `--amber-500`
- Duration: 1.4s loop

### 9.3 Page Transitions
- Fade between conversations: 150ms
- New message slide: 200ms ease-out
- Agent switch indicator: 300ms with color transition

---

## 10. Accessibility

### 10.1 Keyboard Navigation
| Key | Action |
|-----|--------|
| `Tab` | Navigate between interactive elements |
| `Shift+Tab` | Navigate backwards |
| `Enter` | Activate button/select |
| `Escape` | Close modal/dropdown |
| `Ctrl+K` | Open command palette |
| `Ctrl+N` | New conversation |
| `Ctrl+/` | Show keyboard shortcuts |
| `↑` (in input) | Edit last message |

### 10.2 Screen Reader Support
- All icons have `aria-label`
- Agent switches announced with `aria-live`
- Message roles: `role="log"` with `aria-live="polite"`
- Loading states announced
- Focus management for modals

### 10.3 Visual Accessibility
- Minimum contrast ratio: 4.5:1
- Focus indicators: 2px solid `--amber-500`
- Reduced motion support: `@media (prefers-reduced-motion)`
- Font size scaling: All sizes in rem

---

## 11. Technical Implementation Notes

### 11.1 Tech Stack Recommendations
```
Frontend Framework: React 18+ or Vue 3
Styling: Tailwind CSS + CSS Variables
State Management: Zustand / Pinia
Animation: Framer Motion / Vue Transitions
Icons: Lucide React / Heroicons
Code Highlighting: PrismJS / Shiki
Markdown: react-markdown / marked
```

### 11.2 Performance Guidelines
- Virtualize long conversation lists (react-window)
- Lazy load code block syntax highlighting
- Debounce input at 150ms
- Use Intersection Observer for message loading
- Implement optimistic UI for message sending

### 11.3 State Structure
```typescript
interface ConversationState {
  id: string;
  title: string;
  messages: Message[];
  model: ModelType;
  activeAgent: AgentType;
  createdAt: Date;
  updatedAt: Date;
}

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  agent?: AgentType;
  attachments?: Attachment[];
  metadata?: {
    tokensUsed?: number;
    latency?: number;
    model?: string;
  };
}
```

---

## 12. Responsive Behavior Summary

| Feature | Desktop | Tablet | Mobile |
|---------|---------|--------|--------|
| Sidebar | Fixed 240px | Icon-only 72px | Drawer (swipe) |
| Conversation width | 768px max | 100% - 48px | 100% - 32px |
| Input | Multi-line | Multi-line | Single-line (expands) |
| Agent selector | Dropdown | Dropdown | Bottom sheet |
| Code blocks | Full features | Horizontal scroll | Horizontal scroll |
| File attachments | Grid | List | List |

---

## 13. Future Enhancements

### 13.1 Planned Features
1. **Voice Input/Output**: Microphone button, speech synthesis
2. **Plugin System**: Extensible agent capabilities
3. **Collaborative Mode**: Multi-user conversations
4. **Custom Agents**: User-defined agent personalities
5. **Conversation Folders**: Organize chats into projects
6. **Export Options**: PDF, Markdown, JSON export
7. **Dark Mode**: Full dark theme support

### 13.2 Experimental Features
1. **Canvas Mode**: Visual workspace for complex tasks
2. **Agent Marketplace**: Community-created agents
3. **Memory System**: Persistent user preferences
4. **Workflow Builder**: Visual agent chaining

---

## Appendix A: Icon Reference

| Icon | Usage | Lucide Name |
|------|-------|-------------|
| [+] | New conversation | `plus` |
| [💬] | Conversation | `message-square` |
| [⚙️] | Settings | `settings` |
| [❓] | Help | `help-circle` |
| [📎] | Attach | `paperclip` |
| [➤] | Send | `send` |
| [🎤] | Voice | `mic` |
| [👤] | User | `user` |
| [🤖] | AI | `bot` |
| [📋] | Copy | `copy` |
| [✏️] | Edit | `edit` |
| [🗑️] | Delete | `trash-2` |
| [↻] | Regenerate | `refresh-cw` |
| [👍] | Thumbs up | `thumbs-up` |
| [👎] | Thumbs down | `thumbs-down` |

---

## Appendix B: Color Tokens (CSS Variables)

```css
:root {
  /* Primary - Amber */
  --amber-50: #FFFBEB;
  --amber-100: #FEF3C7;
  --amber-200: #FDE68A;
  --amber-300: #FCD34D;
  --amber-400: #FBBF24;
  --amber-500: #F59E0B;
  --amber-600: #D97706;
  --amber-700: #B45309;
  --amber-800: #92400E;
  --amber-900: #78350F;

  /* Neutrals */
  --gray-50: #F9FAFB;
  --gray-100: #F3F4F6;
  --gray-200: #E5E7EB;
  --gray-300: #D1D5DB;
  --gray-400: #9CA3AF;
  --gray-500: #6B7280;
  --gray-600: #4B5563;
  --gray-700: #374151;
  --gray-800: #1F2937;
  --gray-900: #111827;

  /* Agent Colors */
  --agent-coder: #3B82F6;
  --agent-writer: #EC4899;
  --agent-researcher: #10B981;
  --agent-data: #8B5CF6;
  --agent-learner: #F97316;
  --agent-general: #F59E0B;
}
```

---

*Document Version: 1.0*
*Last Updated: 2026-03-01*
*Author: Frontend Design Team*
