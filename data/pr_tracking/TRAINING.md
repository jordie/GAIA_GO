# PR Provider Attribution System - Training Guide

## System Overview
This system tracks which AI provider (Claude, Codex, Ollama) worked on each
pull request stage, enabling cost optimization and performance analysis.

## Key Concepts

### Workflow Stages
1. **Code Review** - High-quality analysis (Claude recommended)
2. **Implementation** - Writing code and tests (Codex/Ollama)
3. **Integration Testing** - Quality assurance (Ollama recommended)

### Provider Specialization
- **Claude**: Security-critical, complex, architectural reviews
- **Codex**: Standard implementation, good quality/cost ratio
- **Ollama**: Fast local testing, zero cost, high utilization

### Cost Model
- Claude: $3.00/hour (premium quality)
- Codex: $0.87/hour (value option)
- Ollama: $0.00/hour (unlimited free local)

## Common Workflows

### Feature Development
1. Claude reviews design (30 min)
2. Codex implements feature (2 hrs)
3. Ollama tests integration (1 hr)
Total: $2.37 vs $19.50 all-Claude = 60% savings

### Bug Fix (Urgent)
1. Claude reviews critical fix (15 min)
2. Codex implements (30 min)
3. Ollama verifies (free)
Total: $1.18 vs $4.50 all-Claude = 74% savings

### Database Optimization
1. Claude reviews design (45 min)
2. Ollama implements locally (free)
3. Ollama tests performance (free)
Total: $2.25 vs $6.75 all-Claude = 67% savings

## Best Practices
- Use Claude for security/architecture reviews
- Use Codex for standard implementation
- Always use Ollama for testing (100% free)
- Track provider attribution for every PR
- Review cost reports weekly
- Adjust provider mix based on patterns
