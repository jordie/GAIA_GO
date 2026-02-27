# Admin Dashboard Guide

Comprehensive guide for using and developing the GAIA_GO Reputation System Admin Dashboard.

## Table of Contents

1. [Overview](#overview)
2. [Dashboard Sections](#dashboard-sections)
3. [API Endpoints](#api-endpoints)
4. [Usage Guide](#usage-guide)
5. [Development](#development)
6. [Troubleshooting](#troubleshooting)

## Overview

The Admin Dashboard provides real-time monitoring and management of the reputation system, with comprehensive analytics, reporting, and system monitoring capabilities.

### Key Features

- **Real-time Metrics**: Live dashboard with key performance indicators
- **Appeals Management**: Browse, filter, and manage appeals
- **Analytics**: Trend analysis, pattern detection, and statistical insights
- **ML Predictions**: Monitor prediction accuracy and model performance
- **Negotiation Monitoring**: Track active negotiations and sentiment analysis
- **Reports**: Generate daily/weekly/monthly reports with export options
- **System Monitoring**: Database and performance metrics

### Technology Stack

- **Frontend**: HTML5, CSS3, JavaScript (ES6+)
- **Visualization**: Chart.js for data visualization
- **Backend**: Go with Gin framework
- **Database**: SQLite with GORM

## Dashboard Sections

### 1. Overview

The main dashboard shows key metrics at a glance:

| Metric | Description |
|--------|-------------|
| Total Appeals | All-time appeal count |
| Pending Review | Appeals awaiting action |
| Approved Today | Appeals approved in last 24 hours |
| Avg Resolution | Average hours to resolve appeals |
| Approval Rate | Percentage of appeals approved |
| Active Negotiations | Number of ongoing negotiations |

**Automatic Refresh**: Dashboard data refreshes every 60 seconds

### 2. Appeals Management

Browse and manage all appeals with filtering and pagination.

**Features:**
- Filter by status (pending, reviewing, approved, denied)
- Filter by priority (high, medium, low)
- Paginated listing (50 items per page)
- View appeal details
- Update appeal priority
- Add reviewer notes

**Table Columns:**
- ID: Appeal unique identifier
- User ID: User who submitted appeal
- Status: Current appeal status (color-coded badges)
- Reason: Appeal reason description
- Created: Date appeal was submitted
- Days Pending: Days waiting for review
- Messages: Number of negotiation messages
- Actions: View detail button

### 3. Analytics

Analyze appeal patterns and trends.

#### Trends Tab
- 30-day submission/approval/denial chart
- Line chart showing daily counts
- Identifies patterns in appeal volume

#### Patterns Tab
- Most common appeal reasons
- Approval rate by reason
- Helps identify systemic issues

#### Distribution Tab
- Pie chart of appeal reason distribution
- Percentage breakdown

### 4. ML Predictions

Monitor ML model performance.

**Performance Metrics:**
- Total Predictions: Number of predictions made
- Average Confidence: Mean prediction confidence score
- Accuracy: Percentage of correct predictions
- Average Latency: Mean prediction time (ms)

**Recent Predictions Table:**
- Prediction type (approval_probability, recovery_timeline, etc.)
- User ID
- Confidence percentage
- Predicted value
- Creation timestamp

### 5. Negotiation Monitoring

Track active negotiations and sentiment.

**Table Shows:**
- Appeal ID: Associated appeal
- Messages: Number of messages in negotiation
- Duration: How long negotiation has been active
- Average Sentiment: Sentiment score (-1 to +1)
- Status: Current status indicator

### 6. Reports

Generate and export reports for analysis.

**Report Types:**
- Daily: Current day metrics
- Weekly: Current week metrics
- Monthly: Current month metrics
- Custom: User-defined date range

**Export Formats:**
- CSV: Spreadsheet-compatible format
- PDF: Formatted report with charts

### 7. System Monitoring

Monitor system health and performance.

**Health Status:**
- System Status: Healthy/Degraded indicator
- Service Status: Appeal, negotiation, ML prediction services
- Database: Connection status and response time

**Performance Metrics:**
- API Response Time (p99): 99th percentile latency
- Database Connections: Active/max connections
- Error Rate: Percentage of errors
- Uptime: System availability percentage

**Database Stats:**
- Size: Database file size in MB
- Tables: Number of tables
- Indexes: Number of indexes

## API Endpoints

### Dashboard Overview

```
GET /api/admin/dashboard/overview
```

Returns key metrics for the dashboard.

**Response:**
```json
{
  "total_appeals": 1250,
  "pending_appeals": 45,
  "approved_today": 12,
  "avg_resolution_time_hours": 24.5,
  "approval_rate": 0.68,
  "active_negotiations": 23,
  "avg_negotiation_time_hours": 12.3,
  "system_health": "healthy",
  "timestamp": "2024-02-27T10:30:00Z"
}
```

### Dashboard Summary

```
GET /api/admin/dashboard/summary
```

Returns summary counts by type.

**Response:**
```json
{
  "appeals": {
    "pending": 45,
    "reviewing": 12,
    "approved": 800,
    "denied": 393
  },
  "negotiation": {
    "active_count": 23
  },
  "predictions": {
    "total": 1200
  }
}
```

### Key Metrics

```
GET /api/admin/dashboard/key-metrics?range=24h|7d|30d
```

Returns time-filtered metrics.

**Parameters:**
- `range`: Time range (24h, 7d, 30d) - default: 24h

**Response:**
```json
{
  "submission_rate": 5.2,
  "approval_rate": 0.65,
  "avg_processing_time_minutes": 240,
  "error_rate": 0.001,
  "system_uptime": "99.9%",
  "total_appeals_period": 125,
  "time_range": "24h"
}
```

### List Appeals

```
GET /api/admin/appeals?page=1&limit=50&status=pending&priority=high
```

Returns paginated, filtered appeal list.

**Parameters:**
- `page`: Page number (default: 1)
- `limit`: Items per page (default: 50)
- `status`: Filter by status (optional)
- `priority`: Filter by priority (optional)

**Response:**
```json
{
  "appeals": [
    {
      "id": 1,
      "user_id": 123,
      "status": "pending",
      "reason": "Unfair suspension",
      "created_at": "2024-02-27T10:00:00Z",
      "priority": 1,
      "days_pending": 3,
      "message_count": 5
    }
  ],
  "page": 1,
  "limit": 50,
  "total": 125
}
```

### Analytics Trends

```
GET /api/admin/analytics/trends?days=30
```

Returns trend data for specified period.

**Parameters:**
- `days`: Number of days to analyze (default: 30)

**Response:**
```json
{
  "submissions": [
    { "date": "2024-02-27", "count": 15 },
    { "date": "2024-02-26", "count": 12 }
  ],
  "approvals": [
    { "date": "2024-02-27", "count": 10 }
  ],
  "denials": [
    { "date": "2024-02-27", "count": 2 }
  ],
  "period_days": 30,
  "start_date": "2024-01-28"
}
```

### Analytics Patterns

```
GET /api/admin/analytics/patterns
```

Returns pattern analysis.

**Response:**
```json
{
  "top_reasons": [
    {
      "reason": "Unfair suspension",
      "count": 125,
      "approval_rate": 0.68
    },
    {
      "reason": "Bug in system",
      "count": 89,
      "approval_rate": 0.92
    }
  ],
  "total_patterns": 2
}
```

### ML Predictions Accuracy

```
GET /api/admin/predictions/accuracy
```

Returns prediction model performance.

**Response:**
```json
{
  "total_predictions": 1200,
  "correct_predictions": 1020,
  "accuracy_percentage": 85.0,
  "avg_confidence": 0.87,
  "avg_latency_ms": 24.5
}
```

### Negotiation Monitoring

```
GET /api/admin/negotiation/active
```

Returns active negotiations.

**Response:**
```json
[
  {
    "appeal_id": 1,
    "message_count": 5,
    "duration_hours": 2.5,
    "avg_sentiment": 0.3,
    "start_time": "2024-02-27T08:00:00Z",
    "last_message": "2024-02-27T10:30:00Z"
  }
]
```

### System Health

```
GET /api/admin/system/health
```

Returns system health status.

**Response:**
```json
{
  "status": "healthy",
  "database": {
    "connected": true,
    "response_time_ms": 5
  },
  "services": {
    "appeal_service": "running",
    "negotiation_service": "running",
    "ml_predictions": "running",
    "notifications": "running"
  },
  "timestamp": "2024-02-27T10:30:00Z"
}
```

### Database Stats

```
GET /api/admin/system/database-stats
```

Returns database information.

**Response:**
```json
{
  "database_size_mb": 45.2,
  "table_count": 15,
  "index_count": 32,
  "page_size": 4096,
  "page_count": 11584,
  "tables": []
}
```

## Usage Guide

### Accessing the Dashboard

1. Navigate to `/admin/dashboard` (requires authentication)
2. Login with admin credentials
3. Dashboard loads automatically with current metrics

### Navigation

Use the sidebar to navigate between sections:
- 📊 Overview: Main dashboard
- 📋 Appeals: Appeal management
- 📈 Analytics: Trends and patterns
- 🤖 Predictions: ML model performance
- 💬 Negotiation: Negotiation tracking
- 📄 Reports: Report generation
- ⚙️ System: System monitoring

### Filtering Appeals

1. Select status from "Status" dropdown
2. Select priority from "Priority" dropdown
3. Click "Apply Filters" button
4. Table updates with filtered results

### Generating Reports

1. Navigate to Reports section
2. Click desired report type button:
   - Daily Report: Today's metrics
   - Weekly Report: Current week metrics
   - Monthly Report: Current month metrics
3. Review report data
4. Export to CSV or PDF using buttons

### Understanding Metrics

**Approval Rate**: Percentage of appeals approved
- Higher is better (system is resolving appeals favorably)
- Track over time for trends

**Average Resolution Time**: Hours to resolve appeals
- Lower is better (faster resolution)
- Indicates efficiency

**Negotiation Duration**: Hours for negotiations
- Shows engagement level
- Longer negotiations indicate complex issues

**ML Confidence**: 0-100%
- Indicates prediction reliability
- Aim for > 80%

## Development

### Adding New Endpoints

1. Create handler function in `admin_dashboard_routes.go`
2. Add route registration in `RegisterAdminDashboardRoutes`
3. Add corresponding JavaScript function in dashboard HTML
4. Update API documentation

### Testing

Run tests:
```bash
# All dashboard tests
go test -v ./pkg/routes -run Dashboard

# Specific test
go test -v ./pkg/routes -run TestGetDashboardOverview

# Benchmarks
go test -bench=Dashboard ./pkg/routes
```

### Performance Optimization

- **Database Queries**: All queries use indexes on frequently filtered columns
- **Pagination**: Default limit of 50 items per page
- **Caching**: Chart.js instances are cached to prevent memory leaks
- **Auto-refresh**: 60-second interval balances data freshness with load

### Extending the Dashboard

1. Add new metric card in HTML
2. Create API endpoint in routes file
3. Create JavaScript loader function
4. Wire up in `loadSectionData` function
5. Add tests for new endpoint

## Troubleshooting

### Dashboard Not Loading

**Symptoms**: Blank page or loading spinner stuck

**Solutions**:
1. Check browser console for JavaScript errors
2. Verify API endpoints are accessible: `curl /api/admin/dashboard/overview`
3. Check server logs for API errors
4. Clear browser cache

### Metrics Not Updating

**Symptoms**: Stale data or "Last updated" timestamp unchanged

**Solutions**:
1. Click "Refresh Data" button
2. Wait for auto-refresh (60 seconds)
3. Check network tab for API call failures
4. Verify database has recent data

### Charts Not Displaying

**Symptoms**: Empty chart containers or error messages

**Solutions**:
1. Verify Chart.js is loaded: Check if CDN is accessible
2. Check browser console for JavaScript errors
3. Verify API returns data in correct format
4. Check data array is not empty

### API Errors

**Common Error Patterns**:
- 404: Endpoint not found - verify URL path
- 500: Server error - check server logs
- Connection refused: API server not running

**Solutions**:
1. Verify API base URL: `/api/admin`
2. Check server is running
3. Review server logs for error details
4. Test API with curl:
```bash
curl http://localhost:8080/api/admin/dashboard/overview
```

### Performance Issues

**Solutions**:
1. Reduce refresh interval if load is high
2. Use pagination for large result sets
3. Check database performance: `PRAGMA analysis`
4. Monitor active connections

## Configuration

### Frontend Configuration

Edit dashboard HTML `<script>` section:

```javascript
const API_BASE = '/api/admin';           // API endpoint
const DEFAULT_LIMIT = 50;               // Pagination limit
const REFRESH_INTERVAL = 60000;         // Auto-refresh interval (ms)
```

### Auto-Refresh Settings

Modify refresh interval:
```javascript
// Current: 60 seconds
setInterval(refreshDashboard, 60000);

// Change to 30 seconds
setInterval(refreshDashboard, 30000);
```

## Security

### Access Control

- Dashboard requires authentication
- All API endpoints should validate user permissions
- Consider implementing role-based access (admin-only)

### Data Privacy

- Don't expose sensitive user data
- Aggregate statistics instead of individual records
- Log all admin actions for audit trail

## Performance Targets

| Metric | Target | Alert |
|--------|--------|-------|
| Dashboard Load | < 2s | > 5s |
| API Response | < 200ms | > 500ms |
| Chart Render | < 1s | > 2s |
| Page Refresh | < 3s | > 5s |

## Related Documentation

- [API Documentation](API.md)
- [Database Schema](../README.md)
- [Testing Guide](TESTING_GUIDE.md)
- [Operations Guide](OPERATIONS_GUIDE.md)

## Support

For issues or feature requests:
1. Check troubleshooting section
2. Review server logs
3. Test with curl
4. Contact development team

## Changelog

### v1.0.0 (2024-02-27)

**Features:**
- Complete admin dashboard implementation
- 35 API endpoints for metrics and reporting
- Real-time data visualization with Chart.js
- Full appeal management interface
- Analytics and trend analysis
- ML prediction monitoring
- System health monitoring
- Report generation with export

**Testing:**
- 16 unit tests
- 3 performance benchmarks
- API endpoint testing
- Database integration tests

**Documentation:**
- Comprehensive guide
- API documentation
- Troubleshooting guide
- Development guide
