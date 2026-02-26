# PR Provider Attribution - Quick Reference

## Record a PR
```bash
python3 scripts/track_pr_attribution.py --pr <NUM> \
  --title "PR Title" \
  --branch "branch-name" \
  --review-provider claude --review-session pr_review1
```

## View PR Attribution
```bash
# Single PR
python3 scripts/track_pr_attribution.py --pr <NUM> --view

# All PRs
gaia --pr-attribution
```

## Cost Analysis
- Claude: $3.00/hr (high quality review)
- Codex: $0.87/hr (cost-effective implementation)
- Ollama: $0.00/hr (free local testing)

## Provider Selection Guide
- **Code Review**: Use Claude for complex/security-critical PRs
- **Implementation**: Use Codex for routine features, Ollama for cost
- **Testing**: Use Ollama for all integration testing (free)

## API Usage
```bash
# Track PR task
curl -X POST http://localhost:8080/api/pr-attribution/track \
  -H "Content-Type: application/json" \
  -d '{
    "pr_id": 42,
    "session": "pr_review1",
    "provider": "claude",
    "task_type": "review"
  }'

# Get PR attribution
curl http://localhost:8080/api/pr-attribution/42

# Get cost summary
curl http://localhost:8080/api/pr-attribution/cost-summary
```
