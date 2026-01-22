from django.test import TestCase


def get_error_key_response(response):
    """Retrieving error key list from validation error response"""
    error_item_keys = []
    if "error" in response.json():
        for error in response.json()["error"]:
            error_item_keys.extend(list(error.keys()))
    return error_item_keys


class CustomAPITestCase(TestCase):
    def assertResponseStructure(self, response, has_data=False):
        """
        Validates response structure based on status code.
        - 2xx: checks success response structure
        - 4xx/5xx: checks error response structure

        If has_data == True, check if response has 'data' field
        """
        data = response.json()
        status_code = response.status_code

        # Check success response (2xx)
        if 200 <= status_code < 300:
            self.assertIn(
                "message",
                data,
                f"Success response missing 'message' field (status: {status_code})",
            )
            if has_data:
                self.assertIn(
                    "data",
                    data,
                    f"Success response missing 'data' field (status: {status_code})",
                )

        # Check error response (4xx, 5xx)
        elif 400 <= status_code < 600:
            self.assertIn(
                "message",
                data,
                f"Error response missing 'message' field (status: {status_code})",
            )
            # 'error' is only appear in 400 validation error response
            if status_code == 400:
                self.assertIn(
                    "error",
                    data,
                    f"Error response missing 'error' field (status: {status_code})",
                )

        else:
            self.fail(f"Unexpected status code: {status_code}")

        return data
