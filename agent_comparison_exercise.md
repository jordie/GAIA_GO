# Agent Comparison Coding Exercise

## Challenge: Implement a Smart Task Prioritizer

Create a Python function that prioritizes tasks based on multiple criteria.

### Requirements:

1. **Function signature:**
   ```python
   def prioritize_tasks(tasks: list[dict]) -> list[dict]:
       """
       Sort tasks by priority score (high to low).

       Each task is a dict with:
       - 'name': str
       - 'urgency': int (1-10, 10 is most urgent)
       - 'importance': int (1-10, 10 is most important)
       - 'effort': int (hours estimated)
       - 'deadline': str (YYYY-MM-DD format, optional)

       Priority score = urgency * 2 + importance * 1.5 - (effort * 0.1)

       If deadline is within 48 hours, add 5 to priority score.

       Returns: list of tasks sorted by priority score (descending)
       """
   ```

2. **Include error handling** for invalid inputs

3. **Add 3 test cases** demonstrating the function works correctly

4. **Bonus points** for:
   - Clean, readable code
   - Type hints
   - Docstrings
   - Edge case handling

### Example Test Case:
```python
tasks = [
    {'name': 'Fix bug', 'urgency': 8, 'importance': 7, 'effort': 2, 'deadline': '2026-02-11'},
    {'name': 'Write docs', 'urgency': 3, 'importance': 6, 'effort': 4, 'deadline': None},
    {'name': 'Deploy', 'urgency': 9, 'importance': 10, 'effort': 1, 'deadline': '2026-02-12'},
]

result = prioritize_tasks(tasks)
# 'Deploy' should be first (urgency*2 + importance*1.5 - effort*0.1 + deadline bonus)
```

### Evaluation Criteria:
1. Correctness (40%) - Does it work?
2. Code quality (30%) - Clean, readable, maintainable?
3. Testing (20%) - Good test coverage?
4. Performance (10%) - Efficient implementation?
