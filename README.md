# Wavelength

Subscription API for a music streaming service. Built on AWS with Terraform.

## Architecture

API Gateway (REST) > Lambda (Python 3.12) > DynamoDB

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full diagram and data model.

## Prerequisites

- AWS CLI with a configured profile (default: `principal-task`)
- Terraform >= 1.5
- Python 3 with boto3 (`pip install boto3`)

## Deploy

```bash
cd terraform
terraform init
terraform plan
terraform apply
```

The output includes the API URL.

## Seed test data

```bash
python3 scripts/seed.py
```

Adds 6 users (4 live, 2 simulation) and 1 report definition.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | /subscriptions | Create a subscription |
| GET | /subscriptions/{id} | Get one |
| PUT | /subscriptions/{id} | Update |
| DELETE | /subscriptions/{id} | Delete |
| GET | /subscriptions | List, with optional filters (userId, tier, status) |
| GET | /reports/subscriptions | Run reports |

## Demo

```bash
bash scripts/demo.sh
```

## Business rules

- One active subscription per user
- Simulation users can't subscribe
- Tiers: free, basic, pro

## Time breakdown

| Phase | Time |
|-------|------|
| Discovery and planning | 45min |
| Terraform | 30min |
| Application code | 30min |
| Testing and seed data | 30min |
| Docs and demo prep | 45min |
| **Total** | ~3 hours |

## Teardown

```bash
cd terraform
terraform destroy
```
