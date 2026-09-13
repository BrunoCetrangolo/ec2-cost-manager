"""
Tests básicos con unittest.mock, sin tocar AWS real.

"""

import unittest
from unittest.mock import MagicMock, patch

from ec2_manager import EC2Manager


class TestEC2Manager(unittest.TestCase):

    @patch("ec2_manager.boto3.Session")
    def setUp(self, mock_session):
        self.mock_client = MagicMock()
        mock_session.return_value.client.return_value = self.mock_client
        self.manager = EC2Manager(dry_run=True)

    def test_list_instances_parses_response(self):
        self.mock_client.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-123",
                            "State": {"Name": "running"},
                            "InstanceType": "t2.micro",
                            "Tags": [{"Key": "env", "Value": "dev"}],
                        }
                    ]
                }
            ]
        }
        result = self.manager.list_instances(tag_filter={"env": "dev"})
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "i-123")
        self.assertEqual(result[0]["state"], "running")
        self.assertEqual(result[0]["tags"]["env"], "dev")

    def test_stop_instances_dry_run_does_not_call_api(self):
        self.manager.stop_instances(["i-123"])
        self.mock_client.stop_instances.assert_not_called()

    def test_stop_instances_empty_list_does_nothing(self):
        self.manager.stop_instances([])
        self.mock_client.stop_instances.assert_not_called()


if __name__ == "__main__":
    unittest.main()
