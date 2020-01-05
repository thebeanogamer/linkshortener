import decimal
import json
import os
import string

import boto3
import botocore

db = boto3.resource(
    "dynamodb",
    endpoint_url="http://localhost:8000",
    region_name="eu-west-2",
    connect_timeout=5,
    retries={"max_attempts": 3},
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
    return "".join([i for i in url if i in string.ascii_letters + string.digits])


def redirect(url):
    response = {"statusCode": 302, "headers": {"Location": url}}
    return response


def shortener(event, context):
    try:
        url = db.get_item(Key={"code": event["pathParameters"]["id"]})["Item"]["url"]
        db.update_item(
            Key={"code": event["pathParameters"]["id"]},
            UpdateExpression="set uses = uses + :val",
            ExpressionAttributeValues={":val": decimal.Decimal(1)},
        )
    except KeyError:
        return fallback(event, context)
    return redirect(url)


def create(event, context):
    try:
        db.put_item(
            Item={
                "code": sanitize(json.loads(event["body"])["code"]),
                "url": json.loads(event["body"])["url"],
                "uses": 0,
            },
            ConditionExpression="attribute_not_exists(code)",
        )
    except botocore.exceptions.ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return {"statusCode": 409}
    return {"statusCode": 200}


def view(event, context):
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
    try:
        db.delete_item(
            Key={"code": sanitize(json.loads(event["body"])["code"])},
            ConditionExpression="attribute_exists(code)",
        )
    except botocore.exceptions.ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return {"statusCode": 404, "body": json.dumps({"error": "Code not found"})}
    return {"statusCode": 200}


def fallback(event, context):
    return redirect("https://blog.daniel-milnes.uk")
