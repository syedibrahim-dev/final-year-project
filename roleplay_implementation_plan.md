# AI Roleplay Module - Phased Implementation Plan
## Direct LLM Calls Approach

---

## PHASE 1: Foundation & Database (Week 1)

### Step 1.1: Database Schema
**Files to Create**: `models/roleplay.py`

Create 4 SQLAlchemy models:
1. `RoleplayPersona` - Stores persona configurations
2. `RoleplaySession` - Tracks practice sessions
3. `RoleplayMessage` - Conversation transcript
4. `RoleplayEvaluation` - Performance feedback

**Database Migration**:
- Run `alembic` or manually create tables
- Add foreign keys to existing `users` and `organizations` tables

### Step 1.2: Seed Pre-defined Personas
**Files to Create**: `data/personas.json` + seed script

Define 5 personas in JSON:
```json
{
  "name": "The Budget Hunter",
  "description": "Price-sensitive customer...",
  "personality_traits": {"patience": "medium", "price_sensitivity": "high"},
  "common_objections": ["Too expensive", "Competitor offers cheaper"],
  "tone": "casual",
  "difficulty": "beginner"
}
```

Create seed function to populate `roleplay_personas` table.

---

## PHASE 2: Conversation Engine (Week 2)

### Step 2.1: Prompt Builder
**Files to Create**: `roleplay/prompts.py`

Create functions:
- `build_persona_system_prompt(persona)` - Generates system prompt from persona config
- `format_conversation_history(messages)` - Formats messages for context
- `build_customer_prompt(persona, history, trainee_msg)` - Complete prompt assembly

**Key Logic**:
```python
def build_customer_prompt(persona, history, trainee_msg):
    system = f"""You are {persona.name}. {persona.description}
    
    Personality: {persona.personality_traits}
    Common objections: {persona.common_objections}
    Tone: {persona.tone}
    
    Stay in character. Respond in 2-4 sentences."""
    
    history_text = "\n".join([f"{msg.sender}: {msg.text}" for msg in history])
    
    return system, history_text, trainee_msg
```

### Step 2.2: Ollama Integration
**Files to Create**: `roleplay/llm_client.py`

Create wrapper for direct Ollama calls:
- `generate_customer_response(persona, history, trainee_msg)` - Non-streaming
- `stream_customer_response(persona, history, trainee_msg)` - Streaming generator

**Technical Details**:
- Use `requests` library to call Ollama HTTP API directly
- Endpoint: `POST http://localhost:11434/api/chat`
- Handle streaming chunks for real-time UI

### Step 2.3: Session Management Service
**Files to Create**: `services/roleplay_service.py`

Core functions:
- `create_session(trainee_id, org_id, persona_id)` → Returns session_id
- `add_message(session_id, sender, text)` → Saves to DB, returns message_id
- `get_conversation_history(session_id)` → Returns list of messages
- `generate_ai_response(session_id, trainee_message)` → Calls LLM, saves response

**Flow**:
```
trainee sends message
  ↓
save to roleplay_messages
  ↓
load persona + history
  ↓
call generate_customer_response()
  ↓
save AI response to roleplay_messages
  ↓
return response to frontend
```

---

## PHASE 3: Backend API Routes (Week 2-3)

### Step 3.1: Persona Routes
**Files to Create**: `routes/roleplay.py`

Endpoints:
- `GET /orgs/{org_id}/roleplay/personas` - List all personas
- `GET /orgs/{org_id}/roleplay/personas/{id}` - Get persona details

### Step 3.2: Session Routes
**Files to Create**: `routes/roleplay.py` (same file)

Endpoints:
- `POST /orgs/{org_id}/roleplay/sessions/start`
  - Body: `{"persona_id": 1}`
  - Creates session, returns session_id
  - Status: `active`

- `POST /roleplay/sessions/{session_id}/message`
  - Body: `{"message": "Hi, I'm interested in your product"}`
  - Saves trainee message
  - Generates AI response
  - Returns: `{"response": "...", "message_id": 123}`

- `GET /roleplay/sessions/{session_id}/messages`
  - Returns full conversation history
  - Used to load chat UI

- `POST /roleplay/sessions/{session_id}/end`
  - Updates status to `completed`
  - Calculates duration
  - Returns: `{"session_id": 1, "status": "completed"}`

---

## PHASE 4: Frontend - Persona Selection (Week 3)

### Step 4.1: Sidebar Navigation
**Files to Modify**: `client/src/components/Sidebar.jsx`

Add new menu item:
```jsx
<NavLink to="/roleplay">
  <Icon name="users" />
  AI Roleplay Practice
</NavLink>
```

### Step 4.2: Persona Selection Page
**Files to Create**: 
- `client/src/pages/RoleplayPersonas.jsx`
- `client/src/components/PersonaCard.jsx`

**Layout**:
- Header: "Choose Your Customer Persona"
- Grid of persona cards (3 columns)
- Each card shows: name, description, difficulty badge
- "Start Practice" button on each card

**API Call**:
```javascript
useEffect(() => {
  fetch(`/orgs/${orgId}/roleplay/personas`)
    .then(res => res.json())
    .then(data => setPersonas(data))
}, [])
```

**On Click "Start Practice"**:
```javascript
const startSession = async (personaId) => {
  const response = await fetch(`/orgs/${orgId}/roleplay/sessions/start`, {
    method: 'POST',
    body: JSON.stringify({ persona_id: personaId })
  })
  const { session_id } = await response.json()
  navigate(`/roleplay/session/${session_id}`)
}
```

---

## PHASE 5: Frontend - Chat Interface (Week 4)

### Step 5.1: Chat Page
**Files to Create**:
- `client/src/pages/RoleplayChat.jsx`
- `client/src/components/ChatMessage.jsx`
- `client/src/components/ChatInput.jsx`

**Components**:

1. **Message List** (scrollable)
   - Displays `roleplay_messages` in chat bubble format
   - Trainee messages: right-aligned, blue
   - AI customer messages: left-aligned, gray

2. **Input Box** (bottom)
   - Text area + Send button
   - "End Session" button (red, top-right corner)

3. **Typing Indicator**
   - Shows "Customer is typing..." during LLM generation

**Core Logic**:
```javascript
const [messages, setMessages] = useState([])
const [input, setInput] = useState("")
const [isLoading, setIsLoading] = useState(false)

const sendMessage = async () => {
  if (!input.trim()) return
  
  // Add trainee message to UI immediately
  const traineeMsg = { sender: 'trainee', text: input }
  setMessages(prev => [...prev, traineeMsg])
  setInput("")
  setIsLoading(true)
  
  // Send to backend
  const response = await fetch(`/roleplay/sessions/${sessionId}/message`, {
    method: 'POST',
    body: JSON.stringify({ message: input })
  })
  
  const { response: aiResponse } = await response.json()
  
  // Add AI response to UI
  setMessages(prev => [...prev, { sender: 'ai_customer', text: aiResponse }])
  setIsLoading(false)
}
```

### Step 5.2: End Session Handler
```javascript
const endSession = async () => {
  await fetch(`/roleplay/sessions/${sessionId}/end`, { method: 'POST' })
  navigate(`/roleplay/results/${sessionId}`)
}
```

---

## PHASE 6: Evaluation System (Week 5)

### Step 6.1: Evaluation Prompt Builder
**Files to Create**: `roleplay/evaluation.py`

Function: `build_evaluation_prompt(transcript, persona)`

**Prompt Template**:
```
Analyze this sales conversation between a trainee and a customer.

CUSTOMER PERSONA:
Name: {persona.name}
Description: {persona.description}

TRANSCRIPT:
{formatted_transcript}

Evaluate on these 6 metrics (0-100 each):
1. Rapport Building
2. Active Listening
3. Objection Handling
4. Product Knowledge
5. Closing Effectiveness
6. Conversation Flow

For EACH metric, provide:
- score (integer 0-100)
- justification (1-2 sentences)

Also provide:
- strengths (array of 3 strings with examples)
- improvement_areas (array of 3 actionable items)
- missed_opportunities (array of 2 items)
- overall_summary (3-4 sentences)

Return ONLY valid JSON matching this schema:
{
  "metrics": {
    "rapport_building": {"score": 85, "justification": "..."},
    ...
  },
  "strengths": ["...", "...", "..."],
  "improvement_areas": ["...", "...", "..."],
  "missed_opportunities": ["...", "..."],
  "overall_summary": "..."
}
```

### Step 6.2: Evaluation Service
**Files to Modify**: `services/roleplay_service.py`

Add function: `evaluate_session(session_id)`

**Flow**:
1. Load all messages for session
2. Format as transcript
3. Load persona
4. Build evaluation prompt
5. Call Ollama (with `format: "json"` parameter)
6. Parse JSON response
7. Calculate `overall_score` (average of 6 metrics)
8. Save to `roleplay_evaluations` table
9. Return evaluation data

### Step 6.3: Evaluation Route
**Files to Modify**: `routes/roleplay.py`

Add endpoint:
- `GET /roleplay/sessions/{session_id}/evaluation`
  - Checks if evaluation exists in DB
  - If not, calls `evaluate_session()` (runs in background if slow)
  - Returns evaluation JSON

---

## PHASE 7: Frontend - Results Page (Week 5-6)

### Step 7.1: Results Page
**Files to Create**:
- `client/src/pages/RoleplayResults.jsx`
- `client/src/components/ScoreCircle.jsx`
- `client/src/components/MetricRadarChart.jsx`

**Layout**:

1. **Header Section**
   - Overall score (large circle, center)
   - Session metadata (persona name, date, duration)

2. **Metrics Breakdown** (radar chart)
   - 6-point radar showing all metrics
   - Use Chart.js or Recharts

3. **Feedback Sections** (expandable cards)
   - **Strengths** (green)
   - **Improvement Areas** (orange)
   - **Missed Opportunities** (blue)

4. **Transcript Viewer**
   - Full conversation with line-by-line display
   - Highlight key moments mentioned in feedback

5. **Action Buttons**
   - "Practice Again with Same Persona"
   - "Try Different Persona"
   - "Back to Dashboard"

**API Call**:
```javascript
useEffect(() => {
  fetch(`/roleplay/sessions/${sessionId}/evaluation`)
    .then(res => res.json())
    .then(data => setEvaluation(data))
}, [sessionId])
```

---

## PHASE 8: Admin Dashboard - Basic (Week 6)

### Step 8.1: Session History Table
**Files to Create**: `client/src/pages/admin/RoleplaySessions.jsx`

**Features**:
- Table with columns: Trainee Name, Persona, Date, Duration, Score
- Filters: Date range, Trainee, Persona
- Click row → view full transcript + evaluation

**API Endpoint** (create in backend):
- `GET /admin/orgs/{org_id}/roleplay/sessions`
  - Query params: `?trainee_id=123&from_date=...&to_date=...`
  - Returns paginated list of sessions with evaluation scores

### Step 8.2: Analytics Dashboard
**Files to Create**: `client/src/pages/admin/RoleplayAnalytics.jsx`

**Metrics to Display**:
- Total sessions (this month)
- Average overall score (team-wide)
- Most practiced persona
- Bar chart: Average score by metric
- Line chart: Score trends over time

---

## PHASE 9: Polish & Testing (Week 7)

### Step 9.1: Error Handling
- Add try-catch blocks around all LLM calls
- Handle Ollama being down gracefully
- Show user-friendly error messages in frontend

### Step 9.2: Performance Optimization
- Add loading states for all async operations
- Implement message streaming (if needed)
- Add pagination to conversation history (if very long)

### Step 9.3: Testing
- Test with all 5 pre-defined personas
- Test custom persona creation (Phase 10 feature)
- Verify evaluation scores are reasonable
- Test admin dashboard with multiple trainees

---

## PHASE 10: Advanced Features (Week 8+)

### Step 10.1: Custom Persona Creation
**Backend**:
- New endpoint: `POST /orgs/{org_id}/roleplay/personas/custom`
- Body: `{"description": "A customer who is very technical..."}`
- LLM extracts structured attributes from description
- Saves as new persona

**Frontend**:
- Add "Create Custom Persona" button on persona selection page
- Modal with text area for description
- After creation, auto-redirect to session with new persona

### Step 10.2: Real-time Hints (Optional)
- During conversation, show subtle hints
- "Good use of open-ended question!"
- "Customer seems concerned about price - address it"

### Step 10.3: Progress Tracking
- Track scores over multiple sessions
- Show improvement graph on trainee dashboard
- Achievement badges (e.g., "Completed 10 sessions")

---

## File Structure Summary

```
backend/
  models/
    roleplay.py               # New SQLAlchemy models
  services/
    roleplay_service.py       # New conversation + evaluation logic
  roleplay/
    prompts.py                # New prompt builders
    llm_client.py             # New direct Ollama wrapper
    evaluation.py             # New evaluation prompt
  routes/
    roleplay.py               # New API endpoints
  data/
    personas.json             # New seed data

frontend/
  src/
    pages/
      RoleplayPersonas.jsx    # New persona selection
      RoleplayChat.jsx        # New chat interface
      RoleplayResults.jsx     # New results page
      admin/
        RoleplaySessions.jsx  # New admin session list
        RoleplayAnalytics.jsx # New admin analytics
    components/
      PersonaCard.jsx         # New
      ChatMessage.jsx         # New
      ScoreCircle.jsx         # New
      MetricRadarChart.jsx    # New
```

---

## Timeline Estimate

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| 1 | 3 days | Database ready + personas seeded |
| 2 | 4 days | Conversation engine working |
| 3 | 3 days | API endpoints functional |
| 4 | 2 days | Persona selection UI |
| 5 | 4 days | Chat interface working |
| 6 | 4 days | Evaluation system complete |
| 7 | 4 days | Results page polished |
| 8 | 3 days | Admin dashboard MVP |
| 9 | 3 days | Testing + bug fixes |
| 10 | 5+ days | Advanced features |

**Total**: ~5-6 weeks for full MVP (Phases 1-9)

---

## Next Steps

1. Review this plan
2. Confirm approach
3. I'll start with **Phase 1: Database Schema** when you're ready
