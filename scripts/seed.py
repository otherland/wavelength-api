#!/usr/bin/env python3
import boto3

session = boto3.Session(profile_name="principal-task", region_name="eu-north-1")
dynamodb = session.resource("dynamodb")

users_table = dynamodb.Table("wavelength-users")
reports_table = dynamodb.Table("wavelength-report-definitions")

users = [
    {"userId": "user-1", "name": "Alice Chen", "email": "alice@example.com", "state": "live"},
    {"userId": "user-2", "name": "Bob Marley", "email": "bob@example.com", "state": "live"},
    {"userId": "user-3", "name": "Carol King", "email": "carol@example.com", "state": "live"},
    {"userId": "user-4", "name": "Dave Grohl", "email": "dave@example.com", "state": "live"},
    {"userId": "user-5", "name": "Eve Santos", "email": "eve@example.com", "state": "simulation"},
    {"userId": "user-6", "name": "Frank Ocean", "email": "frank@example.com", "state": "simulation"},
]

for user in users:
    users_table.put_item(Item=user)
    print(f"  Added user: {user['name']} ({user['state']})")

reports = [
    {"reportId": "by-tier", "name": "Users by subscription tier", "groupBy": "tier"},
]

for report in reports:
    reports_table.put_item(Item=report)
    print(f"  Added report: {report['name']}")

print("\nDone.")
