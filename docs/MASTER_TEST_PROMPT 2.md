# Master Test Prompt - Comprehensive LLM Evaluation

## Purpose

Single prompt that tests ALL aspects of the development pipeline:
- Code generation quality
- Development flow efficiency
- Environment setup
- Resource allocation
- Tool choices
- Deployment verification
- Load testing
- Cleanup validation

## The Master Prompt

```
Create a fully functional TODO application in ${output_dir} that demonstrates
ALL layers of the development stack in under 300 lines total.

## CRITICAL REQUIREMENTS (Test ALL Aspects)

### 1. Backend API (Flask + SQLite in-memory)
Files: app.py, requirements.txt

Endpoints MUST include:
- GET /health → {"status": "ok", "timestamp": "...", "uptime": seconds}
- GET /api/todos → [{id, text, completed, created_at}, ...]
- POST /api/todos {"text": "..."} → {id, text, completed, created_at}
- PUT /api/todos/<id> {"completed": true/false} → {id, text, completed}
- DELETE /api/todos/<id> → {"success": true}
- GET /api/stats → {total: N, completed: N, active: N}

Requirements:
- CORS enabled (flask-cors)
- SQLite in-memory (no file persistence)
- Proper error handling (400, 404, 500 with JSON messages)
- Request logging (timestamp, method, path, status)
- Health endpoint tracks startup time
- Stats endpoint for monitoring
- Each file under 100 lines

### 2. Frontend UI (Single Page Application)
Files: index.html, app.js, style.css

Must include:
- Input field for new todos
- "Add" button
- Todo list showing:
  - Todo text
  - Checkbox (toggle completion)
  - Delete button (X)
- Stats display: "X of Y completed"
- "Clear Completed" button
- Responsive design (mobile-friendly)
- Loading states (while fetching)
- Error messages (if API fails)
- Auto-refresh on changes

JavaScript requirements:
- Use fetch() for all API calls
- Handle all HTTP error codes
- Update UI without page reload
- Debounce rapid clicks
- Show connection status

CSS requirements:
- Clean, modern design
- Hover states on buttons
- Completed todos have strikethrough
- Mobile-first responsive
- Loading spinner animation

### 3. Testing & Validation
Files: test_api.py, test_load.sh

test_api.py must test:
- Health endpoint returns 200
- Create todo returns valid JSON with id
- List todos returns array
- Update todo changes completion status
- Delete todo removes from list
- Stats endpoint returns correct counts
- Invalid requests return 400
- Missing todos return 404

test_load.sh must:
- Send 10 concurrent POST requests
- Verify all succeeded
- Check health after load
- Time the entire test
- Exit 0 if passed, 1 if failed

### 4. Documentation & Setup
Files: README.md, .env.example

README must include:
- Quick start (3 commands max)
- API documentation (all endpoints)
- Development workflow
- Testing instructions
- Deployment notes
- Troubleshooting common issues

.env.example must show:
- PORT (default: 5050)
- DEBUG (default: false)
- LOG_LEVEL (default: info)

### 5. Code Quality Standards
- Total under 300 lines across ALL files
- No external dependencies except flask, flask-cors
- All functions documented
- Consistent naming (snake_case Python, camelCase JS)
- Error handling on every API call
- No console.log in production code
- No print() except for logging

### 6. Resource Efficiency
- Startup time under 3 seconds
- Memory usage under 50MB
- API response time under 100ms
- No memory leaks (check with load test)

## DEVELOPMENT DECISION TRACKING

As you develop, document your decisions in comments:

```python
# DECISION: Using in-memory SQLite for speed
# TRADE-OFF: Data lost on restart, but faster and simpler
# ALTERNATIVE: Could use SQLite file or PostgreSQL

# DECISION: No authentication for simplicity
# TRADE-OFF: Not production-ready, but testable in 5 min
# NEXT STEP: Add JWT tokens for production

# DECISION: CORS enabled for all origins
# TRADE-OFF: Security risk, but needed for testing
# FIX: Restrict to specific origins in production
```

## FILE STRUCTURE (EXACTLY)

```
${output_dir}/
├── app.py              (< 100 lines)
├── requirements.txt    (2 lines)
├── index.html          (< 80 lines)
├── app.js              (< 80 lines)
├── style.css           (< 40 lines)
├── test_api.py         (< 50 lines)
├── test_load.sh        (< 20 lines)
├── README.md           (< 100 lines)
└── .env.example        (< 10 lines)
```

## VERIFICATION CHECKLIST

Before considering complete, verify:
- [ ] All 5 API endpoints work
- [ ] Health endpoint returns proper status
- [ ] UI loads without errors
- [ ] Can add todos
- [ ] Can toggle completion
- [ ] Can delete todos
- [ ] Stats display correctly
- [ ] Error handling works (try with server off)
- [ ] Mobile responsive (test at 375px width)
- [ ] All tests pass (test_api.py)
- [ ] Load test passes (test_load.sh)
- [ ] Total lines under 300
- [ ] No dependencies beyond flask, flask-cors
- [ ] README has complete instructions
- [ ] Startup time under 3 seconds
- [ ] Memory usage under 50MB

## SUCCESS CRITERIA

MUST achieve ALL of:
1. ✅ Generates in under 2 minutes
2. ✅ Deploys successfully in under 30 seconds
3. ✅ All API endpoints return correct responses
4. ✅ UI is functional and responsive
5. ✅ Handles 10 concurrent requests without errors
6. ✅ All tests pass
7. ✅ Total lines under 300
8. ✅ Memory usage under 50MB
9. ✅ No console errors
10. ✅ README is complete and accurate

## COMMON PITFALLS TO AVOID

❌ Don't create authentication (too slow)
❌ Don't use database files (use in-memory)
❌ Don't add extra features beyond requirements
❌ Don't exceed 100 lines per file
❌ Don't use npm/webpack (keep it simple)
❌ Don't forget error handling
❌ Don't forget CORS headers
❌ Don't forget health endpoint
❌ Don't forget load testing

✅ Do keep it minimal
✅ Do test everything
✅ Do document decisions
✅ Do handle errors properly
✅ Do make it responsive
✅ Do optimize for speed

## GENERATE NOW

Create ALL files in ${output_dir} following these requirements EXACTLY.
Be FAST but COMPLETE. Target: 2 minutes or less.
```

## Usage

### Variable Substitution

The prompt uses these variables:
- `${output_dir}` - Where to create files (e.g., `/tmp/llm_rapid_claude_123`)
- `${max_lines}` - Line limit (default: 300)
- `${port}` - App port (default: 5050)

### Test Suite Integration

In `llm_rapid_full_stack.json`, use:

```json
{
  "variables": {
    "prompt": "[contents of master prompt above with ${output_dir} substituted]"
  }
}
```

### Expected Outcomes

#### Phase 1: Generation (2 min)
- LLM reads and understands requirements
- Makes architectural decisions
- Documents trade-offs in comments
- Generates all 9 files
- Total: ~280 lines

#### Phase 2: Validation (10 sec)
- Verify all files exist
- Count lines (should be ~280)
- Check no extra files created

#### Phase 3: Deployment (30 sec)
- pip install flask flask-cors (10 sec)
- Start app.py in background (5 sec)
- Wait for startup (5 sec)
- Health check returns 200 (5 sec)
- Verify stats endpoint (5 sec)

#### Phase 4: API Testing (20 sec)
- Create 3 todos (6 sec)
- List todos (2 sec)
- Toggle completion (4 sec)
- Delete 1 todo (2 sec)
- Check stats (2 sec)
- Verify error handling (4 sec)

#### Phase 5: UI Testing (30 sec)
- Load page (5 sec)
- Find elements (5 sec)
- Add todo via UI (5 sec)
- Toggle completion (5 sec)
- Delete todo (5 sec)
- Verify stats update (5 sec)

#### Phase 6: Load Testing (30 sec)
- Run test_load.sh (20 sec)
- Verify health after load (5 sec)
- Check memory usage (5 sec)

#### Phase 7: Cleanup (10 sec)
- Kill app process (3 sec)
- Delete all files (5 sec)
- Verify process stopped (2 sec)

#### Phase 8: Verification (5 sec)
- Confirm app not reachable (3 sec)
- Confirm files deleted (2 sec)

**Total**: 4 minutes 45 seconds

## Evaluation Metrics

### Speed Score (40 points)
- < 2 min: 40 points
- 2-3 min: 30 points
- 3-4 min: 20 points
- 4-5 min: 10 points
- > 5 min: 0 points

### Completeness Score (30 points)
- All 9 files: 30 points
- 7-8 files: 20 points
- 5-6 files: 10 points
- < 5 files: 0 points

### Quality Score (20 points)
- All tests pass: 20 points
- Most tests pass: 15 points
- Some tests pass: 10 points
- No tests pass: 0 points

### Resource Score (10 points)
- < 300 lines: 5 points
- < 50MB memory: 5 points

**Total**: 100 points
**Passing**: ≥70 points

## LLM Comparison

Run this prompt against all LLMs:

| LLM | Speed | Complete | Quality | Resource | Total |
|-----|-------|----------|---------|----------|-------|
| Claude | ? | ? | ? | ? | ? |
| Codex | ? | ? | ? | ? | ? |
| Claude-Architect | ? | ? | ? | ? | ? |
| Comet | ? | ? | ? | ? | ? |
| Ollama | ? | ? | ? | ? | ? |
| AnythingLLM | ? | ? | ? | ? | ? |

### Analysis Questions

After testing all providers:

1. **Which is fastest?** (Speed Score)
2. **Which is most complete?** (Completeness Score)
3. **Which has best quality?** (Quality Score)
4. **Which is most efficient?** (Resource Score)
5. **Which is best overall?** (Total Score)

### Decision-Making Insights

From DECISION comments in generated code:

- What trade-offs did each LLM consider?
- Did they document alternatives?
- Did they explain reasoning?
- Did they note production considerations?
- How deep was their architectural thinking?

## Test Variations

### Variation 1: Minimal (5 min target)
- TODO app as described
- 300 lines
- No auth, in-memory only

### Variation 2: Moderate (15 min target)
- Calculator with history
- 500 lines
- Add login, session management

### Variation 3: Complex (30 min target)
- Blog with CRUD + comments
- 1000 lines
- Full auth, database file, deployment

## Next Steps

1. **Run Variation 1** (this prompt) across all LLMs
2. **Analyze results** (which LLM is best for what?)
3. **Iterate prompt** based on findings
4. **Test Variation 2** with winning LLMs
5. **Document patterns** for future prompts

---

**Status**: ✅ Ready for testing
**Target**: 5 minutes end-to-end
**Complexity**: Balanced (tests all layers, fast enough)
**Reusable**: Can substitute TODO → Calculator, Blog, etc.
