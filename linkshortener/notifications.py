import decimal
from datetime import date
from os import environ

import boto3
import jinja2
from linkshortener.shortener import connect


def generate(event):
    db = connect(event)
    page = (
        jinja2.Environment(
            loader=jinja2.FileSystemLoader(searchpath="./linkshortener/templates/"),
            autoescape=jinja2.select_autoescape(
                enabled_extensions=("html", "xml"), default_for_string=True
            ),
        )
        .get_template("email_template.html")
        .render(date=date.today(), links=db.scan()["Items"])
    )
    for i in db.scan()["Items"]:
        db.update_item(
            Key={"code": i["code"]},
            UpdateExpression="set uses.recent = :val",
            ExpressionAttributeValues={":val": decimal.Decimal(0)},
        )
    return page


def view(event, context):
    return {
        "statusCode": 200,
        "body": generate(event),
        "headers": {"Content-Type": "text/html"},
    }


def summary(event, context):
    if event.get("httpMethod") is None:
        db = connect()
        new = False
        for i in db.scan():
            if i["uses"]["recent"] != 0:
                new = True
        if not new:
            raise Exception("No new uses")
    client = boto3.client("ses", region_name=environ.get("SES_REGION"))
    client.send_email(
        Destination={"ToAddresses": [environ.get("ADMIN_CONTACT")]},
        Message={
            "Body": {
                "Html": {"Charset": "UTF-8", "Data": generate(event)},
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
    return {"statusCode": 200}
