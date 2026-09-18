"""
contact_handler.py

Lambda function behind API Gateway that receives contact-form submissions
from the portfolio site. It does two things with each submission:
  1. Writes it to DynamoDB, so there's a permanent record even if you miss
     the notification.
  2. Publishes it to an SNS topic. Subscribe your email (and/or phone
     number, for SMS) to that topic so submissions reach you directly —
     this is the "text me" part of the site.

Environment variables:
  TOPIC_ARN   - ARN of the SNS topic to publish to (set by template.yaml)
  TABLE_NAME  - DynamoDB table name to log submissions to (set by template.yaml)
"""

import json
import os
import re
import time
import uuid
import boto3

sns = boto3.client("sns")
dynamodb = boto3.resource("dynamodb")
TOPIC_ARN = os.environ["TOPIC_ARN"]
TABLE_NAME = os.environ["TABLE_NAME"]
table = dynamodb.Table(TABLE_NAME)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# CORS: restrict this to your actual site origin once it's live, e.g.
# "https://your-bucket.s3-website-us-east-1.amazonaws.com" or your custom domain.
CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Allow-Methods": "OPTIONS,POST",
}


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": CORS_HEADERS,
        "body": json.dumps(body),
    }


def handler(event, context):
    # Preflight
    if event.get("requestContext", {}).get("http", {}).get("method") == "OPTIONS":
        return _response(200, {})

    try:
        data = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return _response(400, {"error": "invalid_json"})

    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip()
    message = (data.get("message") or "").strip()

    if not name or not email or not message:
        return _response(400, {"error": "missing_fields"})
    if not EMAIL_RE.match(email):
        return _response(400, {"error": "invalid_email"})
    if len(message) > 5000:
        return _response(400, {"error": "message_too_long"})

    submission_id = str(uuid.uuid4())
    submitted_at = int(time.time())

    try:
        table.put_item(
            Item={
                "id": submission_id,
                "name": name,
                "email": email,
                "message": message,
                "submitted_at": submitted_at,
            }
        )
    except Exception:
        # Don't fail the whole request just because logging failed — the
        # person emailing you still matters more than the DB write.
        pass

    subject = f"Portfolio contact from {name}"[:100]
    body_text = f"From: {name} <{email}>\n\n{message}\n\n(id: {submission_id})"

    sns.publish(TopicArn=TOPIC_ARN, Subject=subject, Message=body_text)

    return _response(200, {"ok": True})
