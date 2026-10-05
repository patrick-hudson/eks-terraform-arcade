"""Atomic counter lab. Atomic updates are deliberately NOT idempotent."""
import os
import re


def lambda_handler(event, context):
    counter = event.get("counter", "interview")
    if not isinstance(counter, str) or not re.fullmatch(r"[a-z0-9-]{1,32}", counter):
        return {"statusCode": 400, "error": "counter must be 1-32 lowercase letters, digits or hyphens"}
    table_name = os.environ["TABLE_NAME"]
    import boto3
    result = boto3.client("dynamodb").update_item(
        TableName=table_name,
        Key={"pk": {"S": counter}},
        UpdateExpression="ADD visits :one",
        ExpressionAttributeValues={":one": {"N": "1"}},
        ReturnValues="UPDATED_NEW",
    )
    return {"statusCode": 200, "counter": counter, "visits": int(result["Attributes"]["visits"]["N"])}
