# Session Status & Question Tracking System

## Problem

**Current State:**
- Architect asking: "Which would you like me to do?" with 5 options
- Foundation asking: "What's blocking you from running this?"
- No way to know what questions sessions are asking
- No visibility into what sessions are waiting for
- No automated response to common questions

**Need:**
- Sessions continuously update their status
- Questions are logged and visible
- System knows when session is blocked
- Other sessions/systems can see what's happening

---

## Solution Design

### Architecture

```
Session (Claude/tmux)
    ↓ stdout/stderr
Go Wrapper (Extractor)
    ↓ detects patterns
Status Database
    ↓ provides
Dashboard + Assigner + Other Systems
```

### Status File per Session

**Location:** `~/.claude/sessions/<session_name>/status.json`

**Format:**
```json
{
  "session": "architect",
  "status": "waiting_input",
  "current_task": "Commit assigner fixes",
  "question": {
    "asked_at": "2026-02-15T10:15:23Z",
    "type": "multiple_choice",
    "prompt": "Which would you like me to do?",
    "options": [
      "Monitor the workers",
      "Check pending tasks",
      "Review session assignments",
      "Run additional diagnostics",
      "Create additional improvements"
    ],
    "waiting_for": "user_choice"
  },
  "context": {
    "working_dir": "/Users/jgirmay/Desktop/gitrepo/pyWork/architect",
    "git_branch": "feature/migration-analysis-performance-0214",
    "last_command": "python3 workers/assigner_worker.py --status"
  },
  "activity": {
    "last_output": "2026-02-15T10:15:23Z",
    "last_input": "2026-02-15T10:14:50Z",
    "idle_duration": 33
  },
  "updated_at": "2026-02-15T10:15:23Z"
}
```

---

## Implementation

### 1. Go Wrapper Pattern Detection

**Add to `go_wrapper/stream/extractor.go`:**

```go
// Question detection patterns
var questionPatterns = []Pattern{
    {
        Type: "question_asked",
        Pattern: regexp.MustCompile(`(?m)^.*\?$`), // Lines ending with ?
    },
    {
        Type: "multiple_choice",
        Pattern: regexp.MustCompile(`(?m)^\s*\d+\.\s+(.+)$`), // Numbered options
    },
    {
        Type: "waiting_input",
        Pattern: regexp.MustCompile(`(?m)^(Which|What|How|Would you like|Do you want)`),
    },
}

// Status update patterns
var statusPatterns = []Pattern{
    {
        Type: "working_on",
        Pattern: regexp.MustCompile(`(?i)(working on|analyzing|processing|creating)`),
    },
    {
        Type: "completed",
        Pattern: regexp.MustCompile(`(?i)(✅|completed|done|finished|ready)`),
    },
    {
        Type: "blocked",
        Pattern: regexp.MustCompile(`(?i)(waiting|blocked|need|require)`),
    },
}
```

**Question Extraction:**
```go
func (e *Extractor) extractQuestion(output string) *Question {
    lines := strings.Split(output, "\n")
    var question string
    var options []string

    for _, line := range lines {
        // Detect question
        if strings.HasSuffix(strings.TrimSpace(line), "?") {
            question = strings.TrimSpace(line)
        }

        // Detect numbered options
        if match := regexp.MustCompile(`^\s*(\d+)\.\s+(.+)$`).FindStringSubmatch(line); match != nil {
            options = append(options, match[2])
        }
    }

    if question != "" {
        return &Question{
            Prompt: question,
            Options: options,
            Type: determineQuestionType(options),
            AskedAt: time.Now(),
        }
    }

    return nil
}
```

**Status File Writer:**
```go
func (e *Extractor) updateSessionStatus(status SessionStatus) {
    statusFile := fmt.Sprintf("~/.claude/sessions/%s/status.json", e.sessionName)

    data, _ := json.MarshalIndent(status, "", "  ")
    ioutil.WriteFile(statusFile, data, 0644)

    // Also POST to API
    http.Post("http://localhost:8080/api/sessions/status", "application/json", bytes.NewReader(data))
}
```

### 2. Continuous Monitoring

**Go wrapper continuously scans output:**
```go
func (e *Extractor) monitorSession() {
    ticker := time.NewTicker(2 * time.Second)
    defer ticker.Stop()

    for range ticker.C {
        // Capture last 50 lines of output
        output := e.captureRecentOutput(50)

        // Detect current state
        status := e.analyzeOutput(output)

        // Update status file
        e.updateSessionStatus(status)
    }
}

func (e *Extractor) analyzeOutput(output string) SessionStatus {
    status := SessionStatus{
        Session: e.sessionName,
        UpdatedAt: time.Now(),
    }

    // Check for questions
    if q := e.extractQuestion(output); q != nil {
        status.Status = "waiting_input"
        status.Question = q
    }

    // Check for work in progress
    if strings.Contains(output, "Thinking...") || strings.Contains(output, "Analyzing") {
        status.Status = "working"
    }

    // Check for idle (no output for >30s)
    if time.Since(e.lastOutput) > 30*time.Second {
        status.Status = "idle"
    }

    return status
}
```

### 3. Session Status API

**Add to `app.py`:**
```python
@app.route('/api/sessions/status', methods=['GET', 'POST'])
def session_status():
    if request.method == 'POST':
        # Receive status update from wrapper
        status = request.json

        # Store in database
        db.execute("""
            INSERT OR REPLACE INTO session_status
            (session, status, question_json, context_json, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            status['session'],
            status['status'],
            json.dumps(status.get('question')),
            json.dumps(status.get('context'))
        ))

        return {'success': True}

    else:
        # Return all session statuses
        statuses = db.execute("""
            SELECT * FROM session_status
            ORDER BY updated_at DESC
        """).fetchall()

        return {'sessions': [dict(s) for s in statuses]}
```

### 4. Question Auto-Responder

**Automatic responses to common questions:**
```python
class QuestionResponder:
    """Auto-respond to common questions"""

    PATTERNS = {
        r"Which would you like me to do": {
            "type": "delegate",
            "action": "ask_user",  # Forward to user
        },
        r"Should I (commit|push|deploy)": {
            "type": "confirmation",
            "auto_respond": True,
            "response": "yes",  # Auto-approve
        },
        r"Do you want to proceed": {
            "type": "confirmation",
            "auto_respond": True,
            "response": "1",  # Select option 1
        },
    }

    def handle_question(self, session, question):
        for pattern, config in self.PATTERNS.items():
            if re.search(pattern, question['prompt'], re.I):
                if config.get('auto_respond'):
                    # Auto-respond
                    self.send_response(session, config['response'])
                    return True
                elif config['type'] == 'delegate':
                    # Forward to user
                    self.notify_user(session, question)
                    return False

        # Unknown question - log and wait
        logger.info(f"Session {session} asking: {question['prompt']}")
        return False
```

### 5. Dashboard Integration

**Real-time status display:**
```html
<!-- Session Status Panel -->
<div id="session-status">
    <h3>Active Sessions</h3>
    <div id="sessions-container"></div>
</div>

<script>
function updateSessionStatuses() {
    fetch('/api/sessions/status')
        .then(r => r.json())
        .then(data => {
            const container = document.getElementById('sessions-container');
            container.innerHTML = '';

            data.sessions.forEach(session => {
                const div = document.createElement('div');
                div.className = `session-card status-${session.status}`;

                let html = `
                    <h4>${session.session}</h4>
                    <span class="status-badge">${session.status}</span>
                `;

                if (session.question_json) {
                    const q = JSON.parse(session.question_json);
                    html += `
                        <div class="question">
                            <p><strong>Asking:</strong> ${q.prompt}</p>
                            ${q.options ? `
                                <ul>
                                    ${q.options.map((opt, i) => `
                                        <li>
                                            <button onclick="respondToSession('${session.session}', ${i+1})">
                                                ${i+1}. ${opt}
                                            </button>
                                        </li>
                                    `).join('')}
                                </ul>
                            ` : ''}
                        </div>
                    `;
                }

                div.innerHTML = html;
                container.appendChild(div);
            });
        });
}

// Update every 5 seconds
setInterval(updateSessionStatuses, 5000);

function respondToSession(session, choice) {
    fetch(`/api/sessions/${session}/respond`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({choice})
    });
}
</script>
```

---

## Usage Examples

### Example 1: Session Asks Question

**Architect output:**
```
Which would you like me to do?
1. Monitor the workers
2. Check pending tasks
3. Review session assignments
```

**Status file updated:**
```json
{
  "session": "architect",
  "status": "waiting_input",
  "question": {
    "prompt": "Which would you like me to do?",
    "options": [
      "Monitor the workers",
      "Check pending tasks",
      "Review session assignments"
    ],
    "type": "multiple_choice"
  }
}
```

**Dashboard shows:**
```
┌─────────────────────────────────┐
│ ARCHITECT                        │
│ Status: ⏸️ Waiting for Input     │
│                                  │
│ Asking: Which would you like me  │
│         to do?                   │
│                                  │
│ [1] Monitor the workers          │
│ [2] Check pending tasks          │
│ [3] Review session assignments   │
└─────────────────────────────────┘
```

### Example 2: Auto-Response

**Foundation output:**
```
Do you want to proceed with the migration?
```

**Auto-responder detects:**
```python
# Match pattern: "Do you want to proceed"
# Auto-respond: "yes"
send_to_session('foundation', 'yes')
```

**Status updated:**
```json
{
  "session": "foundation",
  "status": "working",
  "last_question_handled": "auto_approved_proceed"
}
```

### Example 3: Multiple Sessions Dashboard

```
┌─────────────────────────────────────────────────────────────┐
│ SESSION STATUS DASHBOARD                                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ ARCHITECT          ⏸️ Waiting for Input                      │
│ Question: Which would you like me to do?                    │
│ [Respond]                                                    │
│                                                              │
│ FOUNDATION         ⚙️ Working                                │
│ Task: Performance validation                                │
│ Last: Running benchmarks... (2m ago)                        │
│                                                              │
│ CODEX              💤 Idle                                   │
│ Last activity: 15m ago                                      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Integration with Assigner

**Assigner checks session status before assignment:**
```python
def can_assign_task(session_name):
    """Check if session is ready for new task"""

    status = get_session_status(session_name)

    # Don't assign if waiting for input
    if status['status'] == 'waiting_input':
        return False

    # Don't assign if busy
    if status['status'] == 'working':
        return False

    # Only assign if idle
    return status['status'] == 'idle'
```

---

## Benefits

1. **Visibility:** See what each session is doing in real-time
2. **Automation:** Auto-respond to common questions
3. **Coordination:** Sessions know what others are doing
4. **Debugging:** Track question patterns, identify issues
5. **Efficiency:** Don't assign tasks to busy sessions

---

## Implementation Plan

### Phase 1: Basic Status Tracking
1. Create status file structure
2. Go wrapper writes status every 5s
3. Simple status: idle/working/waiting

### Phase 2: Question Detection
1. Add question extraction patterns
2. Detect multiple choice options
3. Log questions to status file

### Phase 3: Auto-Response
1. Define common question patterns
2. Implement auto-responder
3. Forward unknown questions to user

### Phase 4: Dashboard Integration
1. Display session statuses
2. Show questions with click-to-respond
3. Real-time updates via SSE

---

## Quick Start

**1. Create status directory:**
```bash
mkdir -p ~/.claude/sessions/{architect,foundation,codex}
```

**2. Add to go wrapper:**
```go
// In main loop
go monitorSession(sessionName)
```

**3. View status:**
```bash
cat ~/.claude/sessions/architect/status.json
```

**4. Check all sessions:**
```bash
curl http://localhost:8080/api/sessions/status | jq
```

---

This creates a **continuous status system** where sessions automatically report their state and questions!
