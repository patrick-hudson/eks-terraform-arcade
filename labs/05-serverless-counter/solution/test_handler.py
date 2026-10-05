import os
import sys
import types
import unittest
from unittest.mock import patch
from handler import lambda_handler


class CounterTests(unittest.TestCase):
    def test_invalid_counter_is_rejected_without_aws(self):
        def unexpected_client(name):
            raise AssertionError("Invalid input must not reach DynamoDB")
        fake = types.SimpleNamespace(client=unexpected_client)
        with patch.dict(os.environ, {"TABLE_NAME": "test-counter"}), patch.dict(sys.modules, {"boto3": fake}):
            for value in ("", "Uppercase", "x" * 33, 5, None):
                with self.subTest(value=value):
                    self.assertEqual(lambda_handler({"counter": value}, None)["statusCode"], 400)

    def test_missing_configuration_is_visible(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(KeyError, "TABLE_NAME"):
                lambda_handler({"counter": "demo"}, None)

    def test_response_decodes_dynamodb_number(self):
        def update_item(**request):
            self.assertEqual(request["TableName"], "test-counter")
            self.assertEqual(request["Key"], {"pk": {"S": "demo"}})
            self.assertEqual(request["UpdateExpression"], "ADD visits :one")
            self.assertEqual(request["ExpressionAttributeValues"], {":one": {"N": "1"}})
            self.assertEqual(request["ReturnValues"], "UPDATED_NEW")
            return {"Attributes": {"visits": {"N": "7"}}}
        def client(name):
            self.assertEqual(name, "dynamodb")
            return types.SimpleNamespace(update_item=update_item)
        fake = types.SimpleNamespace(client=client)
        with patch.dict(os.environ, {"TABLE_NAME": "test-counter"}), patch.dict(sys.modules, {"boto3": fake}):
            self.assertEqual(lambda_handler({"counter": "demo"}, None), {"statusCode": 200, "counter": "demo", "visits": 7})


if __name__ == "__main__":
    unittest.main()
