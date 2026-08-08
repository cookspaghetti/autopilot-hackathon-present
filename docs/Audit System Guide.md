# Audit System Guide

## Overview

The AutoPilot template includes a comprehensive audit logging system that provides complete visibility into all system activity. This is critical for:

- **Compliance**: Track all user actions for regulatory requirements
- **Security**: Detect suspicious activity and unauthorized access
- **Debugging**: Trace issues through detailed request/response logs
- **Analytics**: Understand API usage patterns and performance

## Two Modes of Logging

The audit system operates in two complementary modes:

### 1. Middleware Logging (Automatic)

**What it does**: Automatically logs EVERY HTTP request to the API.

**How it works**: The `AuditMiddleware` intercepts all requests before they reach your endpoints and logs them after the response is sent.

**What's captured**:
- HTTP method (GET, POST, PUT, DELETE)
- Endpoint path
- Query parameters
- Request body (masked for sensitive data)
- Response status code (200, 404, 500, etc.)
- Response time in milliseconds
- User info (extracted from JWT token)
- Client IP and user agent

**Benefits**:
- Zero code changes required
- 100% coverage of all API calls
- Perfect for compliance and debugging
- Performance monitoring built-in

**Configuration**:
```bash
# Disable middleware logging (not recommended)
AUDIT_MIDDLEWARE_ENABLED=false

# Add custom paths to exclude
AUDIT_EXCLUDE_PATHS=/custom/path,/another/path

# Limit body size to log (bytes, default 10KB)
AUDIT_MAX_BODY_SIZE=10240
```

### 2. Custom Logging (Manual)

**What it does**: Provides rich, business-context-aware logging for important events.

**How it works**: Developers call the audit service directly to log meaningful events.

**Example**:
```python
from app.services.audit import audit

# Log a user approval
await audit.log_user_action(
    action="user.approve",
    actor=current_user,
    target_user_id=user_id,
    target_user_email="john@example.com",
    description="Approved user for standard access",
)

# Log a settings change
await audit.log_settings_change(
    actor=current_user,
    setting_key="approved_domains",
    old_value="example.com",
    new_value="example.com,acme.com",
    request=request,
)

# Log a security event
await audit.log_security_event(
    action="security.access_denied",
    description="User attempted to access admin panel without permission",
    actor=current_user,
    request=request,
)
```

## Sensitive Data Handling

The audit system automatically masks sensitive data:

### Masked Fields
- `password`
- `secret`
- `token`
- `key`
- `authorization`
- `api_key`
- `apikey`
- `access_token`
- `refresh_token`
- `client_secret`
- `private_key`
- `credential`

### Example
```json
// Original request body
{
  "email": "user@example.com",
  "password": "super-secret-123",
  "api_key": "sk-abc123"
}

// Logged as
{
  "email": "user@example.com",
  "password": "***MASKED***",
  "api_key": "***MASKED***"
}
```

### Body Truncation
Request and response bodies are truncated to 10KB (configurable) to prevent database bloat.

## Excluded Paths

The following paths are excluded from middleware logging:
- `/health` - Health checks
- `/ready` - Readiness checks
- `/api/health` - API health checks
- `/api/ready` - API readiness checks
- `/_next/*` - Next.js internal routes
- `/static/*` - Static files
- `/favicon*` - Favicon requests
- `/api/admin/audit*` - Audit endpoint itself (prevents recursion)

## API Endpoints

### List Audit Logs
```
GET /api/admin/audit
```

Query parameters:
- `page`, `page_size` - Pagination
- `category` - Filter by category (auth, user_management, admin, settings, api, security)
- `action` - Filter by action name
- `actor_email` - Filter by who performed the action
- `success` - Filter by success status (true/false)
- `severity` - Filter by severity (debug, info, warning, error, critical)
- `start_date`, `end_date` - Date range filter
- `search` - Search in description
- `http_method` - Filter by HTTP method (GET, POST, etc.)
- `response_status` - Filter by HTTP status code
- `is_middleware` - Filter by source (true=auto, false=custom)

### Get Audit Statistics
```
GET /api/admin/audit/stats
```

Returns:
- Total events, events today, events this week
- Breakdown by category and action
- Recent errors count
- Breakdown by HTTP method and status code
- Average response time
- Middleware vs custom log counts

### Export Audit Logs
```
GET /api/admin/audit/export?format=csv
GET /api/admin/audit/export?format=xlsx
```

Supports same filters as list endpoint. Max 100,000 rows per export.

### Get Single Log
```
GET /api/admin/audit/{id}
```

### Get Logs by Resource
```
GET /api/admin/audit/resource/{resource_type}/{resource_id}
```

Example: Get all actions on a specific user
```
GET /api/admin/audit/resource/user/abc123
```

### Get Logs by Actor
```
GET /api/admin/audit/actor/{email}
```

Example: Get all actions by an admin
```
GET /api/admin/audit/actor/admin@example.com
```

## Categories

| Category | Description | Example Actions |
|----------|-------------|-----------------|
| `auth` | Authentication events | login, logout, register |
| `user_management` | User CRUD operations | approve, reject, revoke, delete |
| `admin` | Admin-specific actions | bulk operations, config changes |
| `settings` | Configuration changes | domain updates, feature toggles |
| `api` | API access (middleware) | GET /api/items, POST /api/users |
| `security` | Security events | access denied, rate limit |
| `data` | Business data operations | create item, update record |
| `system` | System events | startup, shutdown |
| `error` | Error events | exceptions, failures |

## Severity Levels

| Severity | Use Case |
|----------|----------|
| `debug` | Development/troubleshooting |
| `info` | Normal operations (default) |
| `warning` | Notable events, bulk operations |
| `error` | Failed operations |
| `critical` | Security breaches, system failures |

## Database Schema

```sql
CREATE TABLE audit_logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Who
    actor_id VARCHAR(255),
    actor_email VARCHAR(255),
    actor_ip VARCHAR(45),
    actor_user_agent TEXT,
    
    -- What
    action VARCHAR(100) NOT NULL,
    category VARCHAR(50) NOT NULL,
    severity VARCHAR(20) DEFAULT 'info',
    
    -- On What
    resource_type VARCHAR(100),
    resource_id VARCHAR(255),
    resource_name VARCHAR(255),
    
    -- Details
    description TEXT NOT NULL,
    extra_data JSON,
    
    -- Result
    success VARCHAR(10) DEFAULT 'true',
    error_message TEXT,
    
    -- Context
    request_id VARCHAR(100),
    session_id VARCHAR(255),
    endpoint VARCHAR(255),
    
    -- Middleware-specific
    http_method VARCHAR(10),
    request_body TEXT,
    query_params TEXT,
    response_status INTEGER,
    response_time_ms FLOAT,
    response_body TEXT,
    is_middleware BOOLEAN DEFAULT FALSE
);

-- Indexes for common queries
CREATE INDEX ix_audit_logs_timestamp ON audit_logs(timestamp);
CREATE INDEX ix_audit_logs_actor_email ON audit_logs(actor_email);
CREATE INDEX ix_audit_logs_action ON audit_logs(action);
CREATE INDEX ix_audit_logs_category ON audit_logs(category);
CREATE INDEX ix_audit_logs_http_method ON audit_logs(http_method);
CREATE INDEX ix_audit_logs_response_status ON audit_logs(response_status);
CREATE INDEX ix_audit_logs_endpoint ON audit_logs(endpoint);
```

## Best Practices

### When to Add Custom Audit Logs

Add custom audit logs for:
1. **Admin actions** - User approval, role changes, bulk operations
2. **Security events** - Access denied, suspicious activity
3. **Configuration changes** - Settings updates, feature toggles
4. **Business-critical operations** - Payments, data exports, deletions

### Action Naming Convention

Use dot notation: `{resource}.{action}`

Examples:
- `user.create`, `user.approve`, `user.delete`
- `settings.update`, `settings.domains_update`
- `bulk.delete_domain`, `bulk.reset_users`
- `security.access_denied`, `security.rate_limited`

### Include Context

Always include:
- `actor` - Who performed the action
- `resource_type` and `resource_id` - What was affected
- `request` - For IP and endpoint tracking

```python
await audit.log(
    action="item.delete",
    description=f"Deleted item {item.name}",
    actor=current_user,
    resource_type="item",
    resource_id=str(item.id),
    resource_name=item.name,
    request=request,
)
```

## UI Features

The audit logs page (`/admin/audit`) provides:

- **Real-time stats** - Total events, today's events, errors, avg response time
- **Filters** - Category, HTTP method, source (auto/custom), search
- **Export** - CSV and Excel download
- **Pagination** - Navigate through large datasets
- **Color coding** - Visual distinction for methods, categories, status codes

## Troubleshooting

### Logs not appearing?

1. Check `AUDIT_MIDDLEWARE_ENABLED` is not `false`
2. Verify the path is not in `AUDIT_EXCLUDE_PATHS`
3. Check database connection is working
4. Look for errors in backend logs

### Export not working?

1. Ensure `openpyxl` is installed for Excel export
2. Check you have admin role
3. Reduce the limit if memory issues occur

### Performance issues?

1. Add appropriate indexes (see schema above)
2. Archive old logs periodically
3. Reduce `AUDIT_MAX_BODY_SIZE` if bodies are large
4. Consider async background logging for high-traffic APIs

