# Architecture

## Overview

```
Client  --->  API Gateway  --->  Lambda (Python)  --->  DynamoDB
(cURL)  <---  (REST, proxy+) <---                 <---  - users
                                                        - subscriptions
                                                        - report_definitions
```

## Components

| Component | Service | What it does |
|-----------|---------|--------------|
| API Gateway | REST API with `{proxy+}` | Receives all HTTP traffic, forwards to Lambda |
| Lambda | Python 3.12, single function | Routing, CRUD, validation, reporting |
| DynamoDB | 3 tables, PAY_PER_REQUEST | Stores users, subscriptions, and report configs |
| IAM | 1 role, 1 policy | Lambda can read/write DynamoDB and write CloudWatch logs. Nothing else. |

## Data model

### users
| Field | Type | Notes |
|-------|------|-------|
| userId (PK) | String | Partition key |
| name | String | |
| email | String | |
| state | String | `live` or `simulation` |

### subscriptions
| Field | Type | Notes |
|-------|------|-------|
| subscriptionId (PK) | String | UUID |
| userId (GSI) | String | Global secondary index for lookups by user |
| tier | String | free, basic, pro |
| status | String | active, cancelled, expired |
| startDate | String | ISO date |
| endDate | String | ISO date |

### report_definitions
| Field | Type | Notes |
|-------|------|-------|
| reportId (PK) | String | e.g. "by-tier" |
| name | String | Human-readable label |
| groupBy | String | Which subscription field to group by |

## Design decisions

**Single Lambda with `{proxy+}`** - API Gateway forwards everything to one function. Routing happens in Python via a regex table. If I needed per-route throttling or auth I'd define individual resources, but there's no reason to here.

**DynamoDB over RDS** - the data is simple key-value, no joins needed. DynamoDB means no VPC, no connection pooling, and it fits within free tier. If the data became relational or the queries got complex, I'd move to Aurora Serverless.

**PAY_PER_REQUEST billing** - no need to guess capacity for a demo. Scales to zero when idle.

## Reporting

Reports are driven by config, not code. Each item in the `report_definitions` table specifies a field to group subscriptions by. The Lambda reads the definition, scans subscriptions, and counts.

To add a new report without redeploying:
1. Insert an item into `wavelength-report-definitions` (e.g. `{"reportId": "by-status", "name": "Subscriptions by status", "groupBy": "status"}`)
2. Hit `GET /reports/subscriptions`
3. The new report shows up in the response

I went with runtime aggregation over DynamoDB rather than Athena or Redshift. Athena would mean exporting to S3 first and waiting seconds for each query - overkill for a table with a handful of rows. Redshift is a warehouse. Wrong scale entirely. If the dataset grew to millions of records, I'd pipe data to S3 and use Athena, but the config-driven pattern would stay the same.
