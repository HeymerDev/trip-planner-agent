"""Fixtures: DynamoDB simulada con moto y un helper que arma eventos HTTP API v2 como API Gateway."""

import importlib
import json
import os
import sys
from pathlib import Path

import boto3
import pytest
from moto import mock_aws

os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-2")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")
os.environ["TABLE_NAME"] = "tripplanner-main"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

USER_A = "11111111-aaaa-bbbb-cccc-000000000001"
USER_B = "22222222-aaaa-bbbb-cccc-000000000002"


@pytest.fixture(autouse=True)
def dynamo():
    """Tabla limpia por prueba; recarga `common` para descartar el recurso cacheado."""
    with mock_aws():
        boto3.client("dynamodb").create_table(
            TableName="tripplanner-main",
            BillingMode="PAY_PER_REQUEST",
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
            ],
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
        )
        import common

        common._dynamodb = None
        yield


def call(module: str, route_key: str, *, sub: str | None = USER_A, body=None, path=None, query=None, raw_body=None):
    """Invoca el handler de una Lambda con un evento equivalente al de API Gateway."""
    handler = importlib.import_module(module).handler
    event = {
        "routeKey": route_key,
        "pathParameters": path or {},
        "queryStringParameters": query,
        "requestContext": {"authorizer": {"jwt": {"claims": {"sub": sub}}}} if sub else {},
    }
    if raw_body is not None:
        event["body"] = raw_body
    elif body is not None:
        event["body"] = json.dumps(body)
    result = handler(event, None)
    parsed = json.loads(result["body"]) if result.get("body") else None
    return result["statusCode"], parsed


def make_trip(sub=USER_A, **overrides):
    body = {
        "origin": "Bogota",
        "destination": "Cartagena",
        "startDate": "2026-12-10",
        "endDate": "2026-12-13",
        "travelers": 3,
        "budgetCOP": 5_000_000,
    }
    body.update(overrides)
    status, data = call("trips", "POST /trips", sub=sub, body=body)
    assert status == 201, data
    return data


def top_up(amount, sub=USER_A):
    status, data = call("wallet", "POST /wallet/topup", sub=sub, body={"amountCOP": amount})
    assert status == 201, data
    return data
