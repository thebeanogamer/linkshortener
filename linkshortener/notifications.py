from linkshortener.shortener import connect
import boto3
from botocore.exceptions import ClientError
from os import environ
from datetime import date
import jinja2
import decimal


def generate(event):
    db = connect(event)
    page = (
        jinja2.Environment(
            loader=jinja2.FileSystemLoader(searchpath="./linkshortener/templates/")
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
    client = boto3.client("ses", region_name=environ.get("AWS_REGION"))
    client.send_email(
        Destination={"ToAddresses": []},
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
        Source=True,
    )
