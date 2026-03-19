I read the spec and picked the simplest architecture that met every requirement
    API Gateway, Lambda, DynamoDB, all serverless, all free tier

Used a single Lambda with proxy+ routing 
    rather than separate functions per endpoint
    six endpoints don't justify the overhead

DynamoDB because the data model is flat, no joins needed, and it avoids the connection pooling complexity that comes with a relational database

For reporting extensibility I stored report definitions as items in DynamoDB table
    the Lambda reads them at runtime and aggregates. 
    New report means new database entry, no code change, no redeploy

I kept the IAM policy locked down to just the six DynamoDB actions on the three specific tables - least privilege
I put the whole thing in one Terraform file so it's easy to read top to bottom and deploy in one go
I wrote an improvements doc covering what I'd add for production: auth, pagination, input validation, logging, tests - wanted to show I know the limits of what I built


What I'd change for production

Things I deliberately left out of the demo but would want before this goes live.


Auth

I'd add an API key on the gateway at minimum, or JWT validation in the handler if we need per-user access control.

API Gateway supports API keys natively - just add `api_key_required = true` to the method in Terraform and create a usage plan. 


Pagination

`GET /subscriptions` returns everything. Fine for 6 users, not fine for 10,000. DynamoDB's `scan` returns a `LastEvaluatedKey` when there are more results - pass that back as a cursor and accept it as a query param on the next request.

```
# in list_subscriptions
scan_kwargs["Limit"] = int(params.get("limit", 50))
if "cursor" in params:
    scan_kwargs["ExclusiveStartKey"] = json.loads(params["cursor"])
```


Scans

`list_subscriptions` and `run_report` both scan the whole table. A scan reads every item then filters - so with a million rows and a filter that matches 3, DynamoDB still reads all million and charges for it.

For the list endpoint: add indexes for commonly filtered fields (tier, status) and use `query` instead of `scan`.

For reporting: at scale, move to Postgres where this is just a `GROUP BY`.


Date validation

Dates go straight into DynamoDB without checking the format. Should at least parse them:

```
from datetime import date

try:
    date.fromisoformat(body["startDate"])
except ValueError:
    return response(400, {"error": "startDate must be YYYY-MM-DD"})
```


Logging

No logging beyond what Lambda gives you by default (start, end, duration). Should log business rule rejections and errors so there's a trail when something goes wrong in production.

```
import logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# then in create_subscription:
logger.info(f"Creating subscription for user {body['userId']}, tier {tier}")
```


Tests

Zero tests. At minimum I'd want:
- Unit tests for the business rules (simulation user blocked, duplicate active blocked)
- Integration test that hits the live API and checks the response codes


Webhook listening to subscriptions

I'd want something event-driven so the API doesn't slow down waiting for the webhook. 
I'd look at what DynamoDB offers for change notifications and trigger a separate function from that.

