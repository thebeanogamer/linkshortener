import decimal
from datetime import date
from os import environ

import boto3
import jinja2
from linkshortener.shortener import connect, headers
from linkshortener.lambda_types import LambdaContext, LambdaDict
from mypy_boto3 import ses


def generate() -> str:
    """Generate the analytics page"""
    db = connect()
    page = (
        jinja2.Environment(
            loader=jinja2.FileSystemLoader(searchpath="./linkshortener/templates/"),
            autoescape=jinja2.select_autoescape(
                enabled_extensions=("html", "xml"), default_for_string=True
            ),
        )
        .get_template("email_template.html")
        .render(
            date=date.today(), links=sorted(db.scan()["Items"], key=lambda x: x["code"])
        )
    )
    for i in db.scan()["Items"]:
        db.update_item(
            Key={"code": i["code"]},
            UpdateExpression="set uses.recent = :val",
            ExpressionAttributeValues={":val": decimal.Decimal(0)},
        )
    return page


def view(event: LambdaDict, context: LambdaContext) -> LambdaDict:
    """View the analytics page in browser"""
    return {
        "statusCode": 200,
        "body": generate(),
        "headers": {**{"Content-Type": "text/html"}, **headers},
    }


def summary(event: LambdaDict, context: LambdaContext) -> LambdaDict:
    """Send an email summary"""
    if event.get("httpMethod") is None:
        db = connect()
        new = False
        for i in db.scan()["Items"]:
            if i["uses"]["recent"] != 0:
                new = True
        if not new:
            raise Exception("No new uses")
    client: ses.Client = boto3.client("ses", region_name=environ.get("SES_REGION"))
    client.send_email(
        Destination={"ToAddresses": [environ.get("ADMIN_CONTACT", "")]},
        Message={
            "Body": {
                "Html": {"Charset": "UTF-8", "Data": generate()},
                "Text": {
                    "Charset": "UTF-8",
                    "Data": "This email must be viewed with HTML",
                },
            },
            "Subject": {
                "Charset": "UTF-8",
                "Data": f"Link Shortener Summary - {date.today()}",
            },
        },
        Source=f"Link Shortener <noreply@{environ.get('DOMAIN')}>",
    )
    return {"statusCode": 200, "headers": headers}
