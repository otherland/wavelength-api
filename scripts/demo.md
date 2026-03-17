# Demo

API=https://kuk31tcuue.execute-api.eu-north-1.amazonaws.com/v1

## Create a subscription

```bash
curl -s -X POST $API/subscriptions \
  -d '{"userId":"user-1","tier":"pro","startDate":"2026-03-17","endDate":"2027-03-17"}'
```

## Simulation user (should get 403)

```bash
curl -s -X POST $API/subscriptions \
  -d '{"userId":"user-5","tier":"free","startDate":"2026-03-17","endDate":"2027-03-17"}'
```

## Duplicate active sub (should get 409)

```bash
curl -s -X POST $API/subscriptions \
  -d '{"userId":"user-1","tier":"basic","startDate":"2026-03-17","endDate":"2027-03-17"}'
```

## Create a few more

```bash
curl -s -X POST $API/subscriptions \
  -d '{"userId":"user-2","tier":"basic","startDate":"2026-03-17","endDate":"2027-03-17"}'

curl -s -X POST $API/subscriptions \
  -d '{"userId":"user-3","tier":"free","startDate":"2026-03-17","endDate":"2027-03-17"}'

curl -s -X POST $API/subscriptions \
  -d '{"userId":"user-4","tier":"pro","startDate":"2026-03-17","endDate":"2027-03-17"}'
```

## List all

```bash
curl -s $API/subscriptions
```

## Filter by tier

```bash
curl -s "$API/subscriptions?tier=pro"
```

## Get one (paste ID from above)

```bash
curl -s $API/subscriptions/SUB_ID
```

## Update

```bash
curl -s -X PUT $API/subscriptions/SUB_ID \
  -d '{"tier":"basic"}'
```

## Delete

```bash
curl -s -X DELETE $API/subscriptions/SUB_ID
```

## Report

```bash
curl -s $API/reports/subscriptions
```
