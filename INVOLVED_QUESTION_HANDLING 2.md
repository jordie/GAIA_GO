# Handling Involved Questions from Sessions

## Problem: Question Complexity Levels

### Simple Questions (Auto-answerable):
```
"Do you want to proceed?" → yes
"Should I commit?" → yes
"Continue?" → yes
```

### Involved Questions (Require Context):
```
ARCHITECT:
"Which would you like me to do?
1. Monitor the workers
2. Check pending tasks
3. Review session assignments
4. Run additional diagnostics
5. Create additional improvements"

FOUNDATION:
"What's blocking you from running this command?
- Terminal access issues?
- Claude CLI not installed?
- Different workflow needed?"
```

**Why Involved:**
- Requires understanding current project priorities
- Depends on what user wants to accomplish
- May need clarification or follow-up
- Answer affects workflow direction

---

## Solution: Question Classification System

### Question Categories

```python
class QuestionComplexity(Enum):
    SIMPLE_CONFIRMATION = 1   # yes/no, auto-answer
    SIMPLE_CHOICE = 2          # numbered list, no context needed
    INVOLVED_CHOICE = 3        # numbered list, requires context
    OPEN_ENDED = 4             # free text, needs understanding
    CLARIFICATION = 5          # asking for more info
    STRATEGIC = 6              # affects project direction
```

### Auto-Classification

```python
def classify_question(question: dict) -> QuestionComplexity:
    """Classify question complexity"""

    prompt = question['prompt'].lower()
    options = question.get('options', [])

    # Simple confirmation
    if re.search(r'(do you want|should i|proceed|continue)', prompt):
        return QuestionComplexity.SIMPLE_CONFIRMATION

    # Involved choice - detect by context words
    context_indicators = [
        'which would you like',
        'what should be the next',
        'how do you want to',
        'what priority',
        'which approach'
    ]
    if any(indicator in prompt for indicator in context_indicators):
        return QuestionComplexity.INVOLVED_CHOICE

    # Open-ended - no options provided
    if not options and '?' in prompt:
        return QuestionComplexity.OPEN_ENDED

    # Clarification - asking what's wrong
    if re.search(r"what's (blocking|wrong|the issue)", prompt):
        return QuestionComplexity.CLARIFICATION

    # Strategic - affects direction
    strategic_words = ['priority', 'next steps', 'approach', 'strategy']
    if any(word in prompt for word in strategic_words):
        return QuestionComplexity.STRATEGIC

    # Default
    return QuestionComplexity.SIMPLE_CHOICE
```

---

## Routing Strategy

### Question Router

```python
class QuestionRouter:
    """Routes questions based on complexity"""

    def route_question(self, session: str, question: dict):
        """Decide how to handle question"""

        complexity = classify_question(question)

        if complexity == QuestionComplexity.SIMPLE_CONFIRMATION:
            # Auto-respond
            return self.auto_respond(session, "yes")

        elif complexity == QuestionComplexity.SIMPLE_CHOICE:
            # Use default heuristic (usually option 1)
            return self.auto_respond(session, "1")

        elif complexity == QuestionComplexity.INVOLVED_CHOICE:
            # Route to coordinator or user
            return self.route_to_coordinator(session, question)

        elif complexity in [QuestionComplexity.OPEN_ENDED,
                           QuestionComplexity.CLARIFICATION,
                           QuestionComplexity.STRATEGIC]:
            # Always ask user
            return self.route_to_user(session, question)

    def route_to_coordinator(self, session: str, question: dict):
        """Send to coordinator session for decision"""

        # Post to architect session for decision
        coordinator_task = {
            'type': 'decision_needed',
            'from_session': session,
            'question': question,
            'context': self.get_session_context(session)
        }

        # Send to assigner queue with high priority
        assigner.send_prompt(
            content=f"Decision needed from {session}: {question['prompt']}",
            target_session='architect',
            priority=9,
            metadata=coordinator_task
        )

    def route_to_user(self, session: str, question: dict):
        """Notify user directly"""

        # Show in dashboard
        dashboard.notify_user({
            'type': 'question',
            'session': session,
            'question': question,
            'requires_response': True
        })

        # Log to file
        with open(f"~/.claude/questions/{session}.json", 'w') as f:
            json.dump(question, f, indent=2)
```

---

## Enhanced Status Format

### For Involved Questions

```json
{
  "session": "architect",
  "status": "waiting_decision",
  "question": {
    "complexity": "involved_choice",
    "prompt": "Which would you like me to do?",
    "options": [
      {
        "id": 1,
        "text": "Monitor the workers",
        "context": "Watch logs to verify fixes are working",
        "estimated_time": "5 minutes",
        "dependencies": []
      },
      {
        "id": 2,
        "text": "Check pending tasks",
        "context": "See what tasks are in assigner queue",
        "estimated_time": "2 minutes",
        "dependencies": []
      },
      {
        "id": 3,
        "text": "Review session assignments",
        "context": "Show which sessions have which prompts",
        "estimated_time": "3 minutes",
        "dependencies": []
      },
      {
        "id": 4,
        "text": "Run additional diagnostics",
        "context": "Check other parts of the system",
        "estimated_time": "10 minutes",
        "dependencies": ["need_to_know_what_to_diagnose"]
      },
      {
        "id": 5,
        "text": "Create additional improvements",
        "context": "Enhance other worker components",
        "estimated_time": "30+ minutes",
        "dependencies": ["need_priority_guidance"]
      }
    ],
    "background": {
      "current_task": "Fixed assigner worker stale sessions",
      "completed": ["Cleanup tool", "Documentation", "Preventive fixes"],
      "pending": ["Commit changes", "Choose next task"]
    },
    "routing": {
      "strategy": "coordinator_decision",
      "fallback": "ask_user",
      "timeout_action": "default_to_option_1"
    }
  }
}
```

---

## Context Enrichment

### Add Project Context to Questions

```python
def enrich_question_context(session: str, question: dict) -> dict:
    """Add relevant context to help answer question"""

    # Get session state
    session_state = get_session_state(session)

    # Get recent activity
    recent_work = get_recent_commits(hours=24)

    # Get current priorities
    priorities = get_project_priorities()

    # Get dependencies
    dependencies = analyze_option_dependencies(question['options'])

    return {
        **question,
        'context': {
            'session_state': session_state,
            'recent_work': recent_work,
            'priorities': priorities,
            'dependencies': dependencies,
            'similar_past_decisions': find_similar_decisions(question)
        }
    }
```

---

## Decision Assistant

### Help Answer Involved Questions

```python
class DecisionAssistant:
    """Helps make decisions on involved questions"""

    def suggest_answer(self, question: dict) -> dict:
        """Suggest best option based on context"""

        context = question.get('context', {})
        options = question['options']

        # Score each option
        scored_options = []
        for opt in options:
            score = 0

            # Align with current priorities
            if self.aligns_with_priorities(opt, context['priorities']):
                score += 10

            # Quick wins (low time, high value)
            if opt.get('estimated_time', '').startswith('2-5'):
                score += 5

            # No blocking dependencies
            if not opt.get('dependencies'):
                score += 3

            # Recently similar task succeeded
            if self.recent_success_similar(opt, context['recent_work']):
                score += 7

            scored_options.append({
                'option': opt,
                'score': score,
                'reasoning': self.explain_score(opt, score)
            })

        # Sort by score
        scored_options.sort(key=lambda x: x['score'], reverse=True)

        return {
            'recommended': scored_options[0],
            'all_scores': scored_options,
            'confidence': self.calculate_confidence(scored_options)
        }
```

---

## Dashboard UI for Involved Questions

### Interactive Question Panel

```html
<div class="involved-question" data-session="architect">
    <div class="question-header">
        <span class="session-badge">ARCHITECT</span>
        <span class="complexity-badge">Involved Decision</span>
        <span class="time-badge">2 minutes ago</span>
    </div>

    <div class="question-content">
        <h4>Which would you like me to do?</h4>

        <div class="context-summary">
            <strong>Context:</strong> Just completed assigner fixes (15→0 failed prompts)
        </div>

        <div class="options-list">
            <!-- Option 1 -->
            <div class="option recommended" data-score="18">
                <div class="option-header">
                    <input type="radio" name="arch-choice" value="1" id="opt1">
                    <label for="opt1">
                        <strong>1. Monitor the workers</strong>
                        <span class="score-badge">Recommended (score: 18)</span>
                    </label>
                </div>
                <div class="option-details">
                    <p>Watch logs to verify fixes are working</p>
                    <div class="option-meta">
                        <span>⏱️ ~5 min</span>
                        <span>✅ No dependencies</span>
                        <span>💡 Validates recent work</span>
                    </div>
                </div>
            </div>

            <!-- Option 2 -->
            <div class="option" data-score="12">
                <div class="option-header">
                    <input type="radio" name="arch-choice" value="2" id="opt2">
                    <label for="opt2">
                        <strong>2. Check pending tasks</strong>
                        <span class="score-badge">Score: 12</span>
                    </label>
                </div>
                <div class="option-details">
                    <p>See what tasks are in assigner queue</p>
                    <div class="option-meta">
                        <span>⏱️ ~2 min</span>
                        <span>✅ No dependencies</span>
                    </div>
                </div>
            </div>

            <!-- ... more options ... -->
        </div>

        <div class="action-buttons">
            <button class="btn-primary" onclick="respondToQuestion('architect')">
                Send Response
            </button>
            <button class="btn-secondary" onclick="askAI('architect')">
                Ask AI to Decide
            </button>
            <button class="btn-secondary" onclick="deferQuestion('architect')">
                Decide Later
            </button>
        </div>
    </div>

    <div class="ai-suggestion">
        <strong>💡 AI Recommendation:</strong>
        Option 1 (Monitor workers) - Validates your recent fixes and takes ~5min.
        This aligns with current priority: verify system health.
    </div>
</div>
```

---

## Question History & Learning

### Track Decisions to Learn Preferences

```python
class QuestionHistory:
    """Track questions and answers to learn patterns"""

    def record_decision(self, question: dict, answer: any, outcome: str):
        """Record question, answer, and outcome"""

        db.execute("""
            INSERT INTO question_history
            (session, question_json, answer, outcome, timestamp)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (question['session'], json.dumps(question), answer, outcome))

    def learn_preferences(self, session: str) -> dict:
        """Learn user preferences from past decisions"""

        history = db.execute("""
            SELECT question_json, answer, outcome
            FROM question_history
            WHERE session = ?
            ORDER BY timestamp DESC
            LIMIT 50
        """, (session,)).fetchall()

        patterns = {
            'prefers_quick_wins': 0,
            'prefers_thorough_analysis': 0,
            'prefers_monitoring': 0,
            'prefers_action': 0
        }

        for record in history:
            q = json.loads(record['question_json'])
            a = record['answer']

            # Analyze patterns
            if 'monitor' in q['options'][a].lower():
                patterns['prefers_monitoring'] += 1
            if 'quick' in q['options'][a].lower():
                patterns['prefers_quick_wins'] += 1
            # ... more pattern detection

        return patterns
```

---

## Integration with Existing Systems

### 1. Assigner Integration

```python
# Before assigning task, check for pending questions
def assign_task(session: str, task: dict):
    status = get_session_status(session)

    if status['question'] and status['question']['complexity'] == 'involved_choice':
        # Don't assign - session needs decision first
        logger.info(f"Session {session} has pending involved question, deferring assignment")
        return False

    # Proceed with assignment
    ...
```

### 2. Go Wrapper Integration

```go
// Detect involved questions
func (e *Extractor) detectInvolvedQuestion(output string) *InvolvedQuestion {
    question := e.extractQuestion(output)
    if question == nil {
        return nil
    }

    // Enrich with context
    question.Complexity = classifyComplexity(question)
    question.Context = e.getSessionContext()

    if question.Complexity >= ComplexityInvolved {
        // Notify coordinator
        e.notifyInvolvedQuestion(question)
    }

    return question
}
```

---

## Handling Strategy Summary

| Question Type | Complexity | Strategy | Timeout |
|--------------|------------|----------|---------|
| "Do you want to proceed?" | Simple | Auto: yes | N/A |
| "Choose 1-3" (obvious) | Simple | Auto: 1 | N/A |
| "Which priority?" | Involved | Ask user | 5 min → default |
| "What's blocking you?" | Clarification | Ask user | No timeout |
| "Next strategic direction?" | Strategic | Coordinator | 10 min → ask user |

---

## Implementation Priority

### Phase 1: Classification
- Detect involved vs simple questions
- Log all questions to file
- Manual review of classifications

### Phase 2: Routing
- Route simple → auto-respond
- Route involved → user dashboard
- Add context enrichment

### Phase 3: Decision Support
- Score options
- Show recommendations
- Track decision history

### Phase 4: Learning
- Analyze past decisions
- Predict preferences
- Auto-suggest based on patterns

---

This system handles **involved questions** by:
1. Detecting complexity
2. Adding context
3. Routing appropriately (user/coordinator)
4. Providing decision support
5. Learning from history
