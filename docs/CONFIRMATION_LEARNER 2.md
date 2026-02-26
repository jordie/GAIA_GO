# Confirmation Learner

The Confirmation Learner tracks auto_confirm_worker behavior and learns from patterns to improve over time.

## What It Learns

The learner tracks:

1. **Operation Statistics** - Success rates for each operation type
   - Total confirmations per operation
   - Success/failure counts
   - Success percentage

2. **Prompt Patterns** - Most common confirmation patterns
   - Pattern types (do_you_want_to, accept_edits, bash_command, etc.)
   - Frequency of each pattern
   - When patterns were last seen

3. **Best Responses** - What key responses work best
   - Option 1, 2, 3, Enter, etc.
   - Which response succeeds most for each operation

## Using the Learner

### View Statistics

```bash
python3 workers/confirmation_learner.py --stats
```

Shows operation success rates:
```
Operation          | Total |     Success | Rate
accept_edits       |    45 |          45 | 100.0%
bash               |   128 |         125 | 97.7%
confirm            |    34 |          33 | 97.1%
edit               |    78 |          76 | 97.4%
```

### View Top Patterns

```bash
python3 workers/confirmation_learner.py --patterns
```

Shows most frequent confirmation patterns:
```
Pattern             (Operation)    Occurrences
bash_command        (bash)                85
do_you_want_to      (confirm)             42
accept_edits        (accept_edits)        45
```

### Get Best Response for Operation

```bash
python3 workers/confirmation_learner.py --best bash
```

Output:
```
Best response for 'bash': 2
```

This means option "2" (don't ask again) is most successful for bash operations.

### Export Learnings

```bash
python3 workers/confirmation_learner.py --export
```

Creates `/tmp/confirmation_learnings.json` with complete data:
```json
{
  "exported_at": "2026-02-17T10:30:45.123456",
  "stats": {
    "operations": [
      {
        "type": "bash",
        "total": 128,
        "successful": 125,
        "success_rate": "97.7%"
      }
    ]
  },
  "top_patterns": [
    {
      "pattern": "bash_command",
      "operation": "bash",
      "occurrences": 85,
      "last_seen": "2026-02-17 10:28:45"
    }
  ]
}
```

## Database

Learning data is stored in SQLite:
- **Location:** `/tmp/auto_confirm_learner.db`
- **Tables:**
  - `confirmation_patterns` - Each confirmation attempt
  - `operation_stats` - Per-operation statistics
  - `prompt_variations` - Pattern tracking

## Integration with auto_confirm_worker

When auto_confirm_worker confirms a prompt, it records:
- Session name
- Operation type
- Prompt text
- Response key used (1, 2, Enter)
- Success status (timestamp)

This data flows automatically to the learner database for analysis.

## Future Improvements

The learner data enables:

1. **Adaptive Response Selection** - Auto-confirm chooses the best option based on success history
2. **Pattern Recognition** - Detect new prompt patterns automatically
3. **Performance Tuning** - Identify which confirmations are slowest/fastest
4. **Failure Analysis** - Track which operations fail and why
5. **Session Learning** - Learn per-session confirmation preferences

## Example: Using Learner Data

Extract operation success rates and decide which operations are risky:

```python
from confirmation_learner import ConfirmationLearner

learner = ConfirmationLearner()
stats = learner.get_stats()

# Find low-success operations
for op in stats['operations']:
    rate = float(op['success_rate'].rstrip('%'))
    if rate < 90:
        print(f"⚠️  {op['type']}: Only {rate}% success - may need review")
```

## Limitations

- Learning is **not** used for decision-making yet (phase 2)
- Confirmation confirmation patterns must still match hardcoded rules
- No cross-session learning (each session treated independently)

## Next Steps

1. ✅ Collect learning data (implemented)
2. ⏳ Analyze patterns to improve detection
3. ⏳ Use success rates to prioritize operations
4. ⏳ Implement adaptive response selection
