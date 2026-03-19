import json
import os
import re
import uuid
from collections import Counter

import boto3

dynamodb = boto3.resource("dynamodb")
users_table = dynamodb.Table(os.environ["USERS_TABLE"])
subscriptions_table = dynamodb.Table(os.environ["SUBSCRIPTIONS_TABLE"])
reports_table = dynamodb.Table(os.environ["REPORT_DEFINITIONS_TABLE"])

VALID_TIERS = {"free", "basic", "pro"}
VALID_STATUSES = {"active", "cancelled", "expired"}


def response(status_code, body):
    """Helper function to format API responses consistently."""
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }



def create_subscription(event):
    body = json.loads(event.get("body") or "{}")

    for field in ("userId", "tier", "startDate", "endDate"):
        if field not in body:
            return response(400, {"error": f"Missing required field: {field}"})

    tier = body["tier"].lower()
    if tier not in VALID_TIERS:
        return response(400, {"error": f"Invalid tier. Must be one of: {', '.join(VALID_TIERS)}"})

    # Check user exists and is live
    user = users_table.get_item(Key={"userId": body["userId"]}).get("Item")
    if not user:
        return response(404, {"error": "User not found"})
    if user.get("state") == "simulation":
        return response(403, {"error": "Simulation users cannot have subscriptions"}) # sim users are for testing purposes

    # Check no active subscription
    existing = subscriptions_table.query(
        IndexName="userId-index",
        KeyConditionExpression="userId = :uid",
        FilterExpression="#s = :active",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":uid": body["userId"], ":active": "active"},
    ).get("Items", [])
    if existing:
        return response(409, {"error": "User already has an active subscription"})

    subscription = {
        "subscriptionId": str(uuid.uuid4()),
        "userId": body["userId"],
        "tier": tier,
        "status": body.get("status", "active"),
        "startDate": body["startDate"],
        "endDate": body["endDate"],
    }
    subscriptions_table.put_item(Item=subscription)
    return response(201, subscription)


def get_subscription(event, sub_id):
    item = subscriptions_table.get_item(Key={"subscriptionId": sub_id}).get("Item")
    if not item:
        return response(404, {"error": "Subscription not found"})
    return response(200, item)


def update_subscription(event, sub_id):
    item = subscriptions_table.get_item(Key={"subscriptionId": sub_id}).get("Item")
    if not item:
        return response(404, {"error": "Subscription not found"})

    body = json.loads(event.get("body") or "{}")
    allowed = {"tier", "status", "startDate", "endDate"}
    updates = {k: v for k, v in body.items() if k in allowed}

    if "tier" in updates:
        updates["tier"] = updates["tier"].lower()
        if updates["tier"] not in VALID_TIERS:
            return response(400, {"error": f"Invalid tier. Must be one of: {', '.join(VALID_TIERS)}"})

    if "status" in updates:
        if updates["status"] not in VALID_STATUSES:
            return response(400, {"error": f"Invalid status. Must be one of: {', '.join(VALID_STATUSES)}"})

    if not updates:
        return response(400, {"error": "No valid fields to update"})

    expr_parts = []
    expr_names = {}
    expr_values = {}
    for i, (k, v) in enumerate(updates.items()):
        expr_parts.append(f"#f{i} = :v{i}")
        expr_names[f"#f{i}"] = k
        expr_values[f":v{i}"] = v

    subscriptions_table.update_item(
        Key={"subscriptionId": sub_id},
        UpdateExpression="SET " + ", ".join(expr_parts),
        ExpressionAttributeNames=expr_names,
        ExpressionAttributeValues=expr_values,
    )

    updated = subscriptions_table.get_item(Key={"subscriptionId": sub_id}).get("Item")
    return response(200, updated)


def delete_subscription(event, sub_id):
    item = subscriptions_table.get_item(Key={"subscriptionId": sub_id}).get("Item")
    if not item:
        return response(404, {"error": "Subscription not found"})

    subscriptions_table.delete_item(Key={"subscriptionId": sub_id})
    return response(200, {"message": "Subscription deleted"})


def list_subscriptions(event):
    params = event.get("queryStringParameters") or {}

    filter_parts = []
    expr_names = {}
    expr_values = {}
    i = 0

    for field in ("userId", "tier", "status"):
        if field in params:
            expr_names[f"#f{i}"] = field
            expr_values[f":v{i}"] = params[field]
            filter_parts.append(f"#f{i} = :v{i}")
            i += 1

    scan_kwargs = {}
    if filter_parts:
        scan_kwargs["FilterExpression"] = " AND ".join(filter_parts)
        scan_kwargs["ExpressionAttributeNames"] = expr_names
        scan_kwargs["ExpressionAttributeValues"] = expr_values

    items = subscriptions_table.scan(**scan_kwargs).get("Items", [])
    return response(200, {"subscriptions": items, "count": len(items)})



def get_reports(event):
    params = event.get("queryStringParameters") or {}
    report_id = params.get("reportId")

    if report_id:
        # Run a specific report
        report_def = reports_table.get_item(Key={"reportId": report_id}).get("Item")
        if not report_def:
            return response(404, {"error": "Report not found"})
        return run_report(report_def)

    # List available reports
    definitions = reports_table.scan().get("Items", [])

    if not definitions:
        return response(200, {"message": "No reports defined", "reports": []})

    # Run all reports
    results = []
    for defn in definitions:
        result = run_report(defn)
        body = json.loads(result["body"])
        results.append(body)

    return response(200, {"reports": results})


def run_report(report_def):
    group_by = report_def.get("groupBy")
    name = report_def.get("name", report_def["reportId"])

    items = subscriptions_table.scan().get("Items", [])
    counts = Counter(item.get(group_by, "unknown") for item in items)

    return response(200, {
        "reportId": report_def["reportId"],
        "name": name,
        "groupBy": group_by,
        "results": dict(counts),
        "total": len(items),
    })


ROUTES = [
    ("POST", r"^/subscriptions$", lambda e, _: create_subscription(e)),
    ("GET", r"^/subscriptions$", lambda e, _: list_subscriptions(e)),
    ("GET", r"^/subscriptions/(?P<id>[^/]+)$", lambda e, m: get_subscription(e, m.group("id"))),
    ("PUT", r"^/subscriptions/(?P<id>[^/]+)$", lambda e, m: update_subscription(e, m.group("id"))),
    ("DELETE", r"^/subscriptions/(?P<id>[^/]+)$", lambda e, m: delete_subscription(e, m.group("id"))),
    ("GET", r"^/reports/subscriptions$", lambda e, _: get_reports(e)),
]


def handler(event, context):
    method = event.get("httpMethod", "")
    path = event.get("path", "")

    for route_method, pattern, func in ROUTES:
        if method == route_method:
            match = re.match(pattern, path)
            if match:
                return func(event, match)

    return response(404, {"error": "Not found"})
