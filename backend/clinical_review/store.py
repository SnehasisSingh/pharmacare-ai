
"""DynamoDB case persistence; never log patient narratives or draft content."""

import os
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError


TABLE = os.environ["PHARMACARE_CASES_TABLE"]
_table = boto3.resource("dynamodb").Table(TABLE)


def now():
    return datetime.now(timezone.utc).isoformat()


def create_case(item):
    _table.put_item(
        Item=item,
        ConditionExpression="attribute_not_exists(case_id)"
    )


def get_case(case_id):
    return _table.get_item(
        Key={"case_id": case_id},
        ConsistentRead=True
    ).get("Item")


def pending_cases(limit=50):
    result = _table.query(
        IndexName="StatusCreatedIndex",
        KeyConditionExpression=Key("status").eq("PENDING_REVIEW"),
        Limit=min(limit, 50),
        ScanIndexForward=True
    )
    return result.get("Items", [])


def decide(case_id, expected_version, decision, reviewer_id, approved_text):
    status = "APPROVED" if decision == "approve" else "REJECTED"

    try:
        result = _table.update_item(
            Key={"case_id": case_id},
            UpdateExpression=(
                "SET #s=:status, reviewer_id=:reviewer, "
                "reviewed_at=:now, approved_text=:text, version=:next"
            ),
            ConditionExpression="#s=:pending AND version=:version",
            ExpressionAttributeNames={
                "#s": "status"
            },
            ExpressionAttributeValues={
                ":status": status,
                ":pending": "PENDING_REVIEW",
                ":version": expected_version,
                ":next": expected_version + 1,
                ":reviewer": reviewer_id,
                ":now": now(),
                ":text": approved_text if status == "APPROVED" else ""
            },
            ReturnValues="ALL_NEW"
        )

        return result["Attributes"]

    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return None
        raise
