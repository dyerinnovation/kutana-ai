# Why Zoom, Google Meet, and Teams Haven't Enabled Agent Participation

> The incumbent meeting platforms have the distribution, the infrastructure, and the engineering talent. So why hasn't one of them built native AI agent participation? The answer is technical, but mostly strategic.

---

## Technical Barriers

### WebRTC Complexity
Real-time audio mixing for multi-agent scenarios is genuinely hard. WebRTC was designed for human-to-human video calls — symmetric low-latency streams between a small number of peers. Adding server-side AI participants that receive, process, and emit audio in real time requires:

- SFU (Selective Forwarding Unit) architecture to route audio to agents without mixing it for all participants
- Per-agent audio tracks with independent encode/decode pipelines
- Echo cancellation and acoustic isolation between agents
- Sub-150ms round trip for natural-feeling turn management

Platforms have SFU infrastructure, but it's optimized for human video calls, not AI agent pipelines with LLM inference in the loop.

### Each Platform Has a Different API
Zoom, Meet, and Teams each have fundamentally different bot/developer APIs:

- **Zoom:** Meeting SDK (screen share injection model), no native audio bot API. Bot users join via screen share + virtual microphone — a hack that captures rendered video, not raw audio streams.
- **Google Meet:** Never had a proper programmatic join API for non-human participants. The Meet REST API manages meetings but does not support joining a call as a participant.
- **Teams:** Bot Framework SDK exists, but it's designed for chat bots, not audio participants. Meeting bots receive transcription events, not raw audio. Speaking requires injecting audio via a convoluted media session model.

Building a unified agent experience across all three would require maintaining three separate integration paths, each with distinct limitations, auth models, and breakage risks.

### Real-Time Audio Mixing for Multi-Agent Is Expensive
When multiple AI agents are in a room, each agent needs to hear all other participants' audio (to follow the conversation) but not its own output (acoustic echo). Platforms have never had to solve this at scale — human participants do echo cancellation locally in their browser/app. Server-side agent participants require mixing infrastructure that the platforms have never built or tested.

---

## Business Barriers

### Platforms Want Their OWN AI to Be the Only AI in the Room

This is the core strategic reason. Every major platform has bet its AI future on a captive AI assistant:

- **Zoom AI Companion** — transcription, meeting summaries, smart chapters, chat assistance ($5.99/user/month add-on, or included in paid plans)
- **Gemini in Meet** — Google's full-stack AI: real-time notes, translations, background effects, Q&A, "take notes for me"
- **Microsoft Copilot in Teams** — Microsoft's most strategic AI product; Teams is the distribution vehicle for Copilot monetization across the M365 suite

Each of these AI assistants is a significant and growing revenue line. Opening the platform to third-party agents — Claude, GPT, open-source agents — would:

1. **Cannibalize AI revenue.** If users bring their own Claude agent to a Zoom meeting, they don't need Zoom AI Companion.
2. **Commoditize the meeting platform.** The AI layer is how these platforms justify premium pricing and differentiate from each other. Open it, and Zoom becomes a dumb pipe.
3. **Cede control of the data.** Third-party agents receiving raw audio and transcript data would undermine the data moats these platforms are building.

The strategic incentive is the opposite of openness: lock users into the platform's AI ecosystem, not enable portability.

---

## Active Bot Discouragement

### Zoom: Crackdown Since 2024
Zoom has systematically tightened restrictions on bot accounts:
- Increased detection and blocking of automated participants using virtual cameras/microphones
- Terms of Service updates that explicitly prohibit "automated participants" without Zoom's explicit authorization
- Rate limiting and behavioral fingerprinting that flags bot-like join patterns
- Removal of features that bots relied on (screen share injection paths changed)

Companies like Recall.ai spend significant engineering effort staying ahead of Zoom's bot detection. It's a cat-and-mouse game.

### Google Meet: Never Had a Proper Bot API
Google Meet's developer story for bot participation has never existed in a stable form. The Meet API covers scheduling and management but explicitly does not support joining as a participant. Google's position has been consistent: agent participation in Meet happens through Google's own AI stack (Gemini), not third-party bots.

### Teams: Chat-First Bot Framework
Teams bots are designed for chat interactions — responding to @mentions, posting adaptive cards, surfacing information. The Teams bot framework does receive meeting transcript events, but audio participation is limited and poorly documented. Microsoft's energy is entirely directed toward Copilot integration, not enabling third-party agent audio.

---

## The Recall.ai Model: Why Fragile Foundations Don't Work

Recall.ai built a business on the premise that "bot-user workarounds" could be productized. Their value proposition: abstract away the Zoom/Meet/Teams API differences behind a single unified API.

The technical approach is a reverse-engineering hack:
- A virtual machine runs the actual Zoom/Meet/Teams client application
- A virtual camera injects a video feed; a virtual microphone injects audio
- Screen capture or accessibility APIs extract the rendered meeting view

This works until it doesn't. Platform updates that change the client application UI, audio routing, or authentication flows break everything. Every Zoom update is a potential breaking change. The business is built on quicksand.

This is not a sustainable foundation for an enterprise product. It's a sign that the incumbent platforms have never offered (and don't want to offer) native agent participation.

---

## Historical Analogy: SIP Was Open, WebRTC Became Walled Gardens

Traditional telephony (SIP/PSTN) was an open protocol. Any phone could call any other phone. The application layer was commoditized and open.

WebRTC promised the same openness for video — and at the transport layer, it delivered. But the meeting platforms that built on WebRTC created closed application layers. Zoom, Meet, and Teams are walled gardens with proprietary signaling, proprietary participant models, and proprietary AI integrations.

The same pattern played out in messaging: SMS was open, iMessage/WhatsApp/Slack became walled gardens. Users got richer features inside each garden; interoperability suffered.

Meeting platforms are following the same trajectory. The question is whether an open platform can build critical mass before the walls fully close — and whether AI agents create a wedge (because users want THEIR agent in meetings, not just the platform's AI).

---

## Kutana's Opportunity

The incumbent platforms' strategic interests are misaligned with open agent participation. They cannot build this — it would undermine their own AI revenue. They won't license it — it reduces platform lock-in. And bot workarounds are getting harder, not easier.

This creates a genuine opening:

1. **Developers** who want to build agents that participate in meetings have no good option on incumbent platforms. Kutana offers a purpose-built alternative.
2. **Users** who want to bring their own AI into meetings are underserved. Platforms force their AI on users; Kutana lets users choose.
3. **Agent-native use cases** — agents talking to agents, agents coordinating work during meetings, multi-agent collaboration — simply don't exist on incumbent platforms and never will.

The walled garden isn't just an obstacle. It's the reason Kutana has a market.
