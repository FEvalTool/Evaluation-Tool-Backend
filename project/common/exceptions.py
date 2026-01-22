from rest_framework.exceptions import APIException
from drf_standardized_errors.formatter import ExceptionFormatter
from drf_standardized_errors.types import ErrorResponse


class Conflict(APIException):
    status_code = 409
    default_detail = "Resource conflict"
    default_code = "conflict"


class CustomExceptionFormatter(ExceptionFormatter):
    def format_error_response(self, error_response: ErrorResponse):
        error_message = error_response.errors[0].detail
        error_code = error_response.errors[0].code
        error_details = []
        if error_response.type == "validation_error":
            error_code = "validation"
            error_message = "Invalid request body/params"
            for error in error_response.errors:
                error_details.append({error.attr: error.detail})
        return {
            "code": error_code,
            "message": error_message,
            **({"error": error_details} if len(error_details) != 0 else {}),
        }
