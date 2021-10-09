import decimal
import json
import os
import string

import boto3
import botocore
from botocore.config import Config

headers = {
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
    "X-Content-Type-Options": "nosniff",
    "Cache-Control": "max-age=0; Expires=-1 or Expires: Fri, 01 Jan 1990 00:00:00 GMT\
; no-cache, must-revalidate",
}


def connect():
    return boto3.resource(
        "dynamodb",
        endpoint_url="http://localhost:8000"
        if os.environ.get("STAGE") == "dev"
        else None,
        region_name="eu-west-2",
        config=Config(connect_timeout=5, retries={"max_attempts": 3}),
    ).Table(os.environ["DYNAMODB_TABLE"])


class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            if o % 1 > 0:
                return float(o)
            else:
                return int(o)
        return super(DecimalEncoder, self).default(o)


def sanitize(url):
    # This function sanitizes URLs so they are compliant with RFC3986
    return "".join([i for i in url if i in string.ascii_letters + string.digits + "-"])


def redirect(url):
    return {"statusCode": 302, "headers": {**{"Location": url}, **headers}}


def shortener(event, context):
    db = connect()
    try:
        url = db.get_item(Key={"code": event["pathParameters"]["id"]})["Item"]["url"]
        db.update_item(
            Key={"code": event["pathParameters"]["id"]},
            UpdateExpression=(
                "set uses.lifetime = uses.lifetime + :val, "
                "uses.recent = uses.recent + :val"
            ),
            ExpressionAttributeValues={":val": decimal.Decimal(1)},
        )
    except KeyError:
        return fallback(event, context)
    return redirect(url)


def create(event, context):
    db = connect()
    try:
        db.put_item(
            Item={
                "code": sanitize(json.loads(event["body"])["code"]),
                "url": json.loads(event["body"])["url"],
                "uses": {"recent": 0, "lifetime": 0},
            },
            ConditionExpression="attribute_not_exists(code)",
        )
    except botocore.exceptions.ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return {"statusCode": 409, "headers": headers}
    return {"statusCode": 200, "headers": headers}


def view(event, context):
    db = connect()
    if event["queryStringParameters"] is not None and event[
        "queryStringParameters"
    ].get("code") not in (None, ""):
        try:
            codes = db.get_item(
                Key={"code": sanitize(event["queryStringParameters"]["code"])}
            )["Item"]
        except KeyError:
            return {"statusCode": 404, "body": json.dumps({"error": "Code not found"})}
    else:
        codes = db.scan()["Items"]
    return {"statusCode": 200, "body": json.dumps(codes, cls=DecimalEncoder)}


def delete(event, context):
    db = connect()
    try:
        db.delete_item(
            Key={"code": sanitize(json.loads(event["body"])["code"])},
            ConditionExpression="attribute_exists(code)",
        )
    except botocore.exceptions.ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return {
                "statusCode": 404,
                "body": json.dumps({"error": "Code not found"}),
                "headers": headers,
            }
    return {"statusCode": 200, "headers": headers}


def fallback(event, context):
    return redirect(os.environ.get("FALLBACK_URL"))


def robots(event, context):
    return {
        "statusCode": 200,
        "headers": {**{"Content-Type": "text/plain"}, **headers},
        "body": """User-agent: *
Disallow: /""",
    }

def humans(event, context):
    return {
        "statusCode": 200,
        "headers": {**{"Content-Type": "text/plain"}, **headers},
        "body": "Daniel Milnes: github.com/thebeanogamer",
    }

def favicon(event, context):
    return {"statusCode": 404, "headers": headers}
