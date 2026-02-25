# LLM Metrics API Documentation

API endpoints for tracking and analyzing LLM provider usage, costs, and health metrics.

## Overview

The LLM Metrics API provides comprehensive tracking of all LLM requests across different providers (Ollama, LocalAI, Claude, OpenAI), enabling:

- **Usage Monitoring**: Track requests, tokens, and success rates per provider
- **Cost Analysis**: Calculate actual costs and estimate savings from local LLMs
- **Health Monitoring**: Track provider availability and circuit breaker states
- **Trend Analysis**: View daily usage and cost trends over time

## Authentication

All endpoints require authentication via session cookie or API key.

```bash
# Using session cookie
curl -b session.txt http://localhost:8080/api/llm/providers

# Using API key
curl -H "X-API-Key: your-api-key" http://localhost:8080/api/llm/providers
```

---

## Endpoints

### 1. GET /api/llm/providers

Get all LLM providers with their current status and health.

**Response:**

```json
{
  "success": true,
  "providers": [
    {
      "id": 1,
      "name": "ollama",
      "display_name": "Ollama (Local)",
      "provider_type": "local",
      "base_url": "http://localhost:11434",
      "is_enabled": 1,
      "priority": 1,
      "timeout_seconds": 60,
      "circuit_breaker_threshold": 5,
      "circuit_breaker_timeout": 300,
      "is_available": 1,
      "circuit_state": "closed",
      "failure_count": 0,
      "total_requests": 150,
      "successful_requests": 148,
      "failed_requests": 2,
      "avg_response_time_ms": 523.4,
      "last_success_at": "2026-02-07 19:00:00",
      "last_failure_at": null,
      "status": "healthy"
    },
    {
      "id": 3,
      "name": "claude",
      "display_name": "Claude (Anthropic)",
      "provider_type": "remote",
      "base_url": "https://api.anthropic.com",
      "is_enabled": 1,
      "priority": 3,
      "is_available": 1,
      "circuit_state": "closed",
      "total_requests": 50,
      "successful_requests": 48,
      "failed_requests": 2,
      "avg_response_time_ms": 1234.5,
      "status": "healthy"
    }
  ]
}
```

**Status Values:**
- `healthy`: Circuit closed, provider available
- `recovering`: Circuit half-open, testing recovery
- `unavailable`: Circuit open, provider down
- `unknown`: No health data available

---

### 2. GET /api/llm/metrics

Get usage metrics per provider with filtering options.

**Query Parameters:**
- `provider` (optional): Filter by provider name (e.g., "ollama", "claude")
- `days` (optional): Number of days to look back (default: 7)

**Examples:**

```bash
# All providers, last 7 days
GET /api/llm/metrics

# Specific provider, last 30 days
GET /api/llm/metrics?provider=ollama&days=30

# All providers, last 90 days
GET /api/llm/metrics?days=90
```

**Response:**

```json
{
  "success": true,
  "metrics": [
    {
      "provider_id": 1,
      "provider_name": "ollama",
      "display_name": "Ollama (Local)",
      "provider_type": "local",
      "total_requests": 150,
      "successful_requests": 148,
      "failed_requests": 2,
      "timeout_requests": 0,
      "total_tokens": 1500000,
      "prompt_tokens": 500000,
      "completion_tokens": 1000000,
      "total_cost_usd": 0.0,
      "avg_duration_seconds": 0.52,
      "fallback_count": 5,
      "success_rate": 98.67,
      "first_request_at": "2026-02-01 10:00:00",
      "last_request_at": "2026-02-07 19:00:00"
    },
    {
      "provider_id": 3,
      "provider_name": "claude",
      "display_name": "Claude (Anthropic)",
      "provider_type": "remote",
      "total_requests": 50,
      "successful_requests": 48,
      "failed_requests": 2,
      "total_tokens": 750000,
      "prompt_tokens": 250000,
      "completion_tokens": 500000,
      "total_cost_usd": 8.25,
      "avg_duration_seconds": 1.23,
      "fallback_count": 0,
      "success_rate": 96.0
    }
  ],
  "days": 7
}
```

---

### 3. GET /api/llm/costs

Get cost tracking with estimated savings from using local LLMs.

**Query Parameters:**
- `days` (optional): Number of days to look back (default: 30)

**Examples:**

```bash
# Last 30 days
GET /api/llm/costs

# Last 90 days
GET /api/llm/costs?days=90
```

**Response:**

```json
{
  "success": true,
  "costs": {
    "total_cost_usd": 45.23,
    "total_tokens": 15000000,
    "total_requests": 500,
    "local_requests": 450,
    "remote_requests": 50,
    "estimated_savings_usd": 180.50,
    "hypothetical_claude_cost_usd": 225.73,
    "savings_percentage": 79.97,
    "providers": [
      {
        "id": 1,
        "name": "ollama",
        "display_name": "Ollama (Local)",
        "provider_type": "local",
        "request_count": 450,
        "prompt_tokens": 4500000,
        "completion_tokens": 9000000,
        "total_tokens": 13500000,
        "actual_cost_usd": 0.0
      },
      {
        "id": 3,
        "name": "claude",
        "display_name": "Claude (Anthropic)",
        "provider_type": "remote",
        "request_count": 50,
        "prompt_tokens": 500000,
        "completion_tokens": 1000000,
        "total_tokens": 1500000,
        "actual_cost_usd": 45.23
      }
    ],
    "days": 30
  }
}
```

**Cost Calculation:**
- Local providers (Ollama, LocalAI): $0.00
- Claude Sonnet 4.5: $3.00/1M input tokens, $15.00/1M output tokens
- OpenAI GPT-4: $5.00/1M input tokens, $15.00/1M output tokens
- Savings = (Hypothetical Claude cost for all requests) - (Actual cost paid)

---

### 4. GET /api/llm/trends

Get daily usage and cost trends over time.

**Query Parameters:**
- `days` (optional): Number of days to look back (default: 30)

**Examples:**

```bash
# Last 30 days
GET /api/llm/trends

# Last 7 days
GET /api/llm/trends?days=7
```

**Response:**

```json
{
  "success": true,
  "trends": [
    {
      "date": "2026-02-07",
      "provider_name": "ollama",
      "display_name": "Ollama (Local)",
      "total_requests": 25,
      "successful_requests": 24,
      "total_tokens": 250000,
      "total_cost_usd": 0.0
    },
    {
      "date": "2026-02-07",
      "provider_name": "claude",
      "display_name": "Claude (Anthropic)",
      "total_requests": 5,
      "successful_requests": 5,
      "total_tokens": 75000,
      "total_cost_usd": 3.75
    },
    {
      "date": "2026-02-06",
      "provider_name": "ollama",
      "display_name": "Ollama (Local)",
      "total_requests": 30,
      "successful_requests": 29,
      "total_tokens": 300000,
      "total_cost_usd": 0.0
    }
  ],
  "days": 30
}
```

---

### 5. POST /api/llm/record

Record an LLM request for metrics tracking.

**Request Body:**

```json
{
  "provider": "ollama",
  "model": "llama3.2",
  "status": "success",
  "prompt_tokens": 150,
  "completion_tokens": 300,
  "duration_seconds": 0.52,
  "error_message": null,
  "is_fallback": false,
  "original_provider": null,
  "session_id": "session-123",
  "endpoint": "/api/generate",
  "user_id": "user-1",
  "metadata": {
    "temperature": 0.7,
    "max_tokens": 500
  }
}
```

**Required Fields:**
- `provider`: Provider name (ollama, localai, claude, openai)
- `model`: Model name (llama3.2, claude-sonnet-4-5, gpt-4, etc.)
- `status`: Request status (success, failed, timeout)

**Optional Fields:**
- `prompt_tokens`: Number of input tokens (default: 0)
- `completion_tokens`: Number of output tokens (default: 0)
- `duration_seconds`: Request duration (default: 0.0)
- `error_message`: Error message if failed
- `is_fallback`: Whether this was a fallback attempt
- `original_provider`: If fallback, which provider failed first
- `session_id`: Session or workflow ID
- `endpoint`: API endpoint used
- `user_id`: User ID making request
- `metadata`: Additional metadata (JSON object)

**Response:**

```json
{
  "success": true,
  "message": "Request recorded"
}
```

**Error Responses:**

```json
{
  "success": false,
  "error": "Provider name required"
}
```

---

### 6. POST /api/llm/providers/<provider_id>/enable

Enable or disable a provider.

**Request Body:**

```json
{
  "enabled": true
}
```

**Response:**

```json
{
  "success": true,
  "message": "Provider enabled"
}
```

---

### 7. GET /api/llm/health

Get overall LLM system health summary.

**Response:**

```json
{
  "success": true,
  "health": {
    "total_providers": 4,
    "healthy_providers": 3,
    "degraded_providers": 1,
    "unavailable_providers": 0,
    "local_providers_available": 2,
    "remote_providers_available": 1,
    "has_fallback": true
  }
}
```

**Health Indicators:**
- `healthy_providers`: Providers with circuit closed and available
- `degraded_providers`: Providers in half-open circuit state (recovering)
- `unavailable_providers`: Providers with circuit open or unavailable
- `has_fallback`: Whether multiple providers are available for failover

---

## Integration Examples

### Python Client

```python
import requests

class LLMMetricsClient:
    def __init__(self, base_url, api_key):
        self.base_url = base_url
        self.headers = {'X-API-Key': api_key}

    def get_providers(self):
        """Get all providers."""
        response = requests.get(
            f"{self.base_url}/api/llm/providers",
            headers=self.headers
        )
        return response.json()

    def get_metrics(self, provider=None, days=7):
        """Get provider metrics."""
        params = {'days': days}
        if provider:
            params['provider'] = provider

        response = requests.get(
            f"{self.base_url}/api/llm/metrics",
            headers=self.headers,
            params=params
        )
        return response.json()

    def get_costs(self, days=30):
        """Get cost summary."""
        response = requests.get(
            f"{self.base_url}/api/llm/costs",
            headers=self.headers,
            params={'days': days}
        )
        return response.json()

    def record_request(self, provider, model, status, **kwargs):
        """Record an LLM request."""
        data = {
            'provider': provider,
            'model': model,
            'status': status,
            **kwargs
        }
        response = requests.post(
            f"{self.base_url}/api/llm/record",
            headers=self.headers,
            json=data
        )
        return response.json()


# Usage
client = LLMMetricsClient('http://localhost:8080', 'your-api-key')

# Get providers
providers = client.get_providers()
print(f"Found {len(providers['providers'])} providers")

# Get metrics
metrics = client.get_metrics(days=7)
for m in metrics['metrics']:
    print(f"{m['display_name']}: {m['total_requests']} requests")

# Get costs
costs = client.get_costs(days=30)
print(f"Total cost: ${costs['costs']['total_cost_usd']}")
print(f"Savings: ${costs['costs']['estimated_savings_usd']}")

# Record a request
client.record_request(
    provider='ollama',
    model='llama3.2',
    status='success',
    prompt_tokens=100,
    completion_tokens=200,
    duration_seconds=0.5
)
```

### JavaScript/Node.js Client

```javascript
class LLMMetricsClient {
  constructor(baseUrl, apiKey) {
    this.baseUrl = baseUrl;
    this.headers = {'X-API-Key': apiKey};
  }

  async getProviders() {
    const response = await fetch(`${this.baseUrl}/api/llm/providers`, {
      headers: this.headers
    });
    return await response.json();
  }

  async getMetrics(provider = null, days = 7) {
    const params = new URLSearchParams({days});
    if (provider) params.append('provider', provider);

    const response = await fetch(
      `${this.baseUrl}/api/llm/metrics?${params}`,
      {headers: this.headers}
    );
    return await response.json();
  }

  async getCosts(days = 30) {
    const response = await fetch(
      `${this.baseUrl}/api/llm/costs?days=${days}`,
      {headers: this.headers}
    );
    return await response.json();
  }

  async recordRequest(provider, model, status, options = {}) {
    const response = await fetch(`${this.baseUrl}/api/llm/record`, {
      method: 'POST',
      headers: {
        ...this.headers,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        provider,
        model,
        status,
        ...options
      })
    });
    return await response.json();
  }
}

// Usage
const client = new LLMMetricsClient('http://localhost:8080', 'your-api-key');

// Get costs
const costs = await client.getCosts(30);
console.log(`Savings: $${costs.costs.estimated_savings_usd}`);

// Record request
await client.recordRequest('ollama', 'llama3.2', 'success', {
  prompt_tokens: 100,
  completion_tokens: 200,
  duration_seconds: 0.5
});
```

---

## Database Schema

### llm_providers

```sql
CREATE TABLE llm_providers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    provider_type TEXT NOT NULL,  -- local, remote
    base_url TEXT,
    is_enabled INTEGER DEFAULT 1,
    priority INTEGER DEFAULT 0,
    timeout_seconds INTEGER DEFAULT 60,
    circuit_breaker_threshold INTEGER DEFAULT 5,
    circuit_breaker_timeout INTEGER DEFAULT 300,
    metadata TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### llm_requests

```sql
CREATE TABLE llm_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_id INTEGER NOT NULL,
    session_id TEXT,
    model TEXT,
    endpoint TEXT,
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    duration_seconds REAL,
    status TEXT NOT NULL,
    error_message TEXT,
    cost_usd REAL DEFAULT 0.0,
    is_fallback INTEGER DEFAULT 0,
    original_provider_id INTEGER,
    user_id TEXT,
    request_metadata TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (provider_id) REFERENCES llm_providers(id)
);
```

### llm_provider_health

```sql
CREATE TABLE llm_provider_health (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_id INTEGER NOT NULL,
    is_available INTEGER DEFAULT 1,
    failure_count INTEGER DEFAULT 0,
    last_failure_at TIMESTAMP,
    last_success_at TIMESTAMP,
    circuit_state TEXT DEFAULT 'closed',
    total_requests INTEGER DEFAULT 0,
    successful_requests INTEGER DEFAULT 0,
    failed_requests INTEGER DEFAULT 0,
    avg_response_time_ms REAL DEFAULT 0.0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (provider_id) REFERENCES llm_providers(id),
    UNIQUE(provider_id)
);
```

### llm_costs_daily

```sql
CREATE TABLE llm_costs_daily (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    total_requests INTEGER DEFAULT 0,
    successful_requests INTEGER DEFAULT 0,
    failed_requests INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    total_cost_usd REAL DEFAULT 0.0,
    estimated_savings_usd REAL DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (provider_id) REFERENCES llm_providers(id),
    UNIQUE(provider_id, date)
);
```

---

## Troubleshooting

### Provider not found

```json
{
  "success": false,
  "error": "Provider ollama not found"
}
```

**Solution**: Check that the migration was run and providers were inserted.

```sql
SELECT * FROM llm_providers;
```

### Database locked errors

**Solution**: The database uses WAL mode with connection pooling. Ensure you're using the `get_connection()` context manager.

### Missing metrics

**Solution**: Ensure requests are being recorded via the `/api/llm/record` endpoint. Check the `llm_requests` table.

---

## Next Steps

1. **Integrate with LLM Provider Service**: Update `services/llm_provider.py` to call `/api/llm/record` after each request
2. **Add Dashboard Panel**: Create UI panel to visualize metrics and costs
3. **Set Up Alerts**: Configure alerts when costs exceed thresholds or providers go down
4. **Export Reports**: Add CSV/PDF export for cost reports
5. **Rate Limiting**: Implement per-provider rate limits based on metrics

---

**Last Updated**: 2026-02-07
**Maintainer**: Architect Dashboard Team
