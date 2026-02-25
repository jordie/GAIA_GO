# LLM Metrics Setup Guide

This guide explains how to set up and use the new LLM metrics tracking system.

## What's New

The architect dashboard now includes comprehensive LLM provider metrics tracking:

1. **Provider Status Monitoring** - Track health and availability of Ollama, LocalAI, Claude, and OpenAI
2. **Usage Metrics** - Monitor requests, tokens, success rates, and response times
3. **Cost Tracking** - Calculate actual costs and estimate savings from using local LLMs
4. **Trend Analysis** - View daily usage and cost trends

## Files Added

### Database Migration
- `migrations/013_llm_metrics.sql` - Creates LLM metrics tables

### Service Layer
- `services/llm_metrics.py` - Core metrics tracking service
- `services/llm_metrics_routes.py` - API endpoints blueprint

### Documentation
- `docs/LLM_METRICS_API.md` - Complete API documentation

### Testing & Utilities
- `run_llm_migration.py` - Script to run the database migration
- `test_llm_api.py` - Test suite for the metrics service

## Setup Instructions

### 1. Run the Database Migration

First, apply the migration to create the required tables:

```bash
cd /Users/jgirmay/Desktop/gitrepo/pyWork/architect

# Option A: Using Python script
python3 run_llm_migration.py

# Option B: Using sqlite3 directly
sqlite3 data/architect.db < migrations/013_llm_metrics.sql
```

Expected output:
```
✓ Migration applied successfully
  Database: data/architect.db
  Migration: migrations/013_llm_metrics.sql

✓ Created 4 tables:
  - llm_costs_daily (0 rows)
  - llm_provider_health (4 rows)
  - llm_providers (4 rows)
  - llm_requests (0 rows)
```

### 2. Verify the Installation

Run the test suite to verify everything is working:

```bash
python3 test_llm_api.py
```

Expected output:
```
LLM Metrics Service Tests
============================================================

TEST: Get All Providers
============================================================
Found 4 providers:

  Ollama (Local)
    Type: local
    Priority: 1
    Enabled: 1
    Available: 1
    Circuit State: closed
    Requests: 0

  LocalAI
    Type: local
    Priority: 2
    ...

TEST SUMMARY
============================================================
  ✓ PASS: Providers
  ✓ PASS: Metrics
  ✓ PASS: Costs
  ✓ PASS: Record Request
  ✓ PASS: Trends

  5/5 tests passed
```

### 3. Start the Dashboard

The new API endpoints are automatically registered when you start the dashboard:

```bash
# Start the dashboard
./deploy.sh

# Or with HTTPS
./deploy.sh --ssl
```

Look for this line in the startup logs:
```
✓ Registered blueprint: llm_metrics
```

### 4. Test the API Endpoints

Test the endpoints using curl:

```bash
# Login first (replace with your credentials)
curl -c cookies.txt -X POST http://localhost:8080/login \
  -H "Content-Type: application/json" \
  -d '{"username": "architect", "password": "peace5"}'

# Get all providers
curl -b cookies.txt http://localhost:8080/api/llm/providers | jq

# Get metrics (last 7 days)
curl -b cookies.txt http://localhost:8080/api/llm/metrics | jq

# Get costs (last 30 days)
curl -b cookies.txt http://localhost:8080/api/llm/costs | jq

# Get system health
curl -b cookies.txt http://localhost:8080/api/llm/health | jq
```

## API Endpoints

All endpoints are documented in `docs/LLM_METRICS_API.md`. Quick reference:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/llm/providers` | GET | List all providers with health status |
| `/api/llm/metrics` | GET | Get usage metrics (requests, tokens, success rate) |
| `/api/llm/costs` | GET | Cost tracking with estimated savings |
| `/api/llm/trends` | GET | Daily usage and cost trends |
| `/api/llm/record` | POST | Record an LLM request |
| `/api/llm/providers/<id>/enable` | POST | Enable/disable a provider |
| `/api/llm/health` | GET | Overall system health |

## Integration with Existing Services

### Update LLM Provider to Record Metrics

Modify `services/llm_provider.py` to record metrics after each request:

```python
from services.llm_metrics import LLMMetricsService

class UnifiedLLMClient:
    def create(self, **kwargs):
        provider = 'claude'  # or ollama, openai, etc.
        model = kwargs.get('model', 'claude-sonnet-4-5')
        start_time = time.time()

        try:
            # Make request
            response = self._make_request(provider, **kwargs)

            # Record success
            LLMMetricsService.record_request(
                provider_name=provider,
                model=model,
                status='success',
                prompt_tokens=response.usage.input_tokens,
                completion_tokens=response.usage.output_tokens,
                duration_seconds=time.time() - start_time
            )

            return response

        except Exception as e:
            # Record failure
            LLMMetricsService.record_request(
                provider_name=provider,
                model=model,
                status='failed',
                error_message=str(e),
                duration_seconds=time.time() - start_time
            )
            raise
```

### Update Local LLM Service

Modify `services/local_llm_service.py` to track Ollama requests:

```python
from services.llm_metrics import LLMMetricsService

class LocalLLMService:
    def _call_ollama(self, prompt, system=None, temperature=0.7, stream=False):
        start_time = time.time()

        try:
            response = requests.post(f"{self.ollama_host}/api/generate", ...)
            duration = time.time() - start_time

            if response.status_code == 200:
                result = response.json()

                # Record success
                LLMMetricsService.record_request(
                    provider_name='ollama',
                    model=self.ollama_model,
                    status='success',
                    prompt_tokens=0,  # Ollama doesn't return token counts
                    completion_tokens=result.get('eval_count', 0),
                    duration_seconds=duration,
                    endpoint='/api/generate'
                )

                return LLMResponse(...)

            else:
                # Record failure
                LLMMetricsService.record_request(
                    provider_name='ollama',
                    model=self.ollama_model,
                    status='failed',
                    error_message=f"HTTP {response.status_code}",
                    duration_seconds=duration
                )
                return LLMResponse(success=False, ...)

        except Exception as e:
            LLMMetricsService.record_request(
                provider_name='ollama',
                model=self.ollama_model,
                status='failed',
                error_message=str(e),
                duration_seconds=time.time() - start_time
            )
            raise
```

## Example Usage

### Get Cost Savings Report

```python
from services.llm_metrics import LLMMetricsService

# Get 30-day cost summary
costs = LLMMetricsService.get_cost_summary(days=30)

print(f"Last 30 days:")
print(f"  Total Cost: ${costs['total_cost_usd']:.2f}")
print(f"  Total Requests: {costs['total_requests']}")
print(f"  Local Requests: {costs['local_requests']} ({costs['local_requests']/costs['total_requests']*100:.1f}%)")
print(f"  Remote Requests: {costs['remote_requests']}")
print(f"\n  If all requests used Claude:")
print(f"    Hypothetical Cost: ${costs['hypothetical_claude_cost_usd']:.2f}")
print(f"    Actual Cost: ${costs['total_cost_usd']:.2f}")
print(f"    Savings: ${costs['estimated_savings_usd']:.2f} ({costs['savings_percentage']:.1f}%)")
```

Output:
```
Last 30 days:
  Total Cost: $45.23
  Total Requests: 500
  Local Requests: 450 (90.0%)
  Remote Requests: 50

  If all requests used Claude:
    Hypothetical Cost: $225.73
    Actual Cost: $45.23
    Savings: $180.50 (79.9%)
```

### Monitor Provider Health

```python
from services.llm_metrics import LLMMetricsService

providers = LLMMetricsService.get_all_providers()

for provider in providers:
    status = "✓" if provider['is_available'] else "✗"
    success_rate = 0
    if provider['total_requests']:
        success_rate = (provider['successful_requests'] / provider['total_requests']) * 100

    print(f"{status} {provider['display_name']}")
    print(f"   Status: {provider['circuit_state']}")
    print(f"   Success Rate: {success_rate:.1f}%")
    print(f"   Avg Response: {provider['avg_response_time_ms']:.0f}ms")
```

Output:
```
✓ Ollama (Local)
   Status: closed
   Success Rate: 98.7%
   Avg Response: 523ms

✓ Claude (Anthropic)
   Status: closed
   Success Rate: 96.0%
   Avg Response: 1234ms

✗ OpenAI GPT-4
   Status: open
   Success Rate: 45.2%
   Avg Response: 2500ms
```

## Troubleshooting

### Migration fails with "table already exists"

This is safe to ignore if you've already run the migration. The migration uses `CREATE TABLE IF NOT EXISTS`.

### No data showing in metrics

Ensure you're recording requests using `LLMMetricsService.record_request()` or via the `/api/llm/record` endpoint.

### Provider shows as unavailable

Check the circuit breaker state:
- `closed` = healthy
- `half_open` = recovering
- `open` = unavailable (circuit tripped)

Reset by updating the health record:
```sql
UPDATE llm_provider_health
SET circuit_state = 'closed', failure_count = 0
WHERE provider_id = 1;
```

## Next Steps

1. **Add Dashboard Panel**: Create a UI panel to visualize metrics
2. **Set Up Monitoring**: Configure alerts when costs exceed thresholds
3. **Integration**: Update all LLM calls to record metrics
4. **Cost Budgets**: Set monthly cost budgets and track against them
5. **Reports**: Generate monthly cost and usage reports

## Reference

- **API Documentation**: `docs/LLM_METRICS_API.md`
- **Local LLM Guide**: `docs/LOCAL_LLM_INFRASTRUCTURE.md`
- **Source Code**:
  - Service: `services/llm_metrics.py`
  - Routes: `services/llm_metrics_routes.py`
  - Migration: `migrations/013_llm_metrics.sql`

## Support

For issues or questions:
1. Check the test suite: `python3 test_llm_api.py`
2. Review API docs: `docs/LLM_METRICS_API.md`
3. Check logs: `/tmp/architect_dashboard.log`

---

**Date**: 2026-02-07
**Author**: Claude Code
**Version**: 1.0.0
