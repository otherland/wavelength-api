# What I'd change for production

Things I deliberately left out of the demo but would want before this goes live.


## Auth

The API is open. Anyone with the URL can hit it. In production I'd add an API key on the gateway at minimum, or JWT validation in the handler if we need per-user access control.

API Gateway supports API keys natively - just add `api_key_required = true` to the method in Terraform and create a usage plan.


## Pagination

`GET /subscriptions` returns everything. Fine for 6 users, not fine for 10,000. DynamoDB's `scan` returns a `LastEvaluatedKey` when there are more results - pass that back as a cursor and accept it as a query param on the next request.

```python
# in list_subscriptions
scan_kwargs["Limit"] = int(params.get("limit", 50))
if "cursor" in params:
    scan_kwargs["ExclusiveStartKey"] = json.loads(params["cursor"])
```


## Scans

`list_subscriptions` and `run_report` both scan the whole table. A scan reads every item then filters - so with a million rows and a filter that matches 3, DynamoDB still reads all million and charges for it.

For the list endpoint: add GSIs for commonly filtered fields (tier, status) and use `query` instead of `scan`.

For reporting: at scale, export to S3 and use Athena, or move to Postgres where this is just a `GROUP BY`.


## Date validation

Dates go straight into DynamoDB without checking the format. Should at least parse them:

```python
from datetime import date

try:
    date.fromisoformat(body["startDate"])
except ValueError:
    return response(400, {"error": "startDate must be YYYY-MM-DD"})
```


## Logging

No logging beyond what Lambda gives you by default (start, end, duration). Should log business rule rejections and errors so there's a trail when something goes wrong in production.

```python
import logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# then in create_subscription:
logger.info(f"Creating subscription for user {body['userId']}, tier {tier}")
```


## Tests

Zero tests. At minimum I'd want:
- Unit tests for the business rules (simulation user blocked, duplicate active blocked)
- Integration test that hits the live API and checks the response codes
