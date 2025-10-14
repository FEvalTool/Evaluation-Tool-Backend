import jwt
from datetime import datetime, timedelta, timezone
from django.test import TestCase
from django.conf import settings

from users.models import CustomUser
from users.utils import (
    generate_username,
    create_jwt,
    decode_and_verify_jwt,
    verify_is_able_to_set_password,
    verify_is_able_to_set_security_qa,
)
from users.exceptions import TokenValidationException
from users.constants import TokenScope


class UtilsTestCase(TestCase):
    def setUp(self):
        self.secret = settings.SECRET_KEY
        self.algorithm = settings.ALGORITHM
        self.exp_minutes = settings.EXPIRES_MINUTES

    def test_generate_username_unique(self):
        CustomUser.objects.create(
            username="VuTA1",
            name="Trinh Anh Vu",
            phone_number="0987654321",
            dob="2000-01-01",
            identity_number="123456789999",
        )
        username = generate_username("Tran Anh Vu")
        self.assertEqual(username, "VuTA2")

    def test_generate_username_with_extra_spaces(self):
        username = generate_username("  Tran   Anh   Vu  ")
        # No user exists yet, expect VuTA1
        self.assertEqual(username, "VuTA1")

    def test_generate_username_different_name(self):
        username = generate_username("Nguyen Van An")
        self.assertEqual(username, "AnNV1")

    def test_create_jwt_contains_expected_fields(self):
        data = {"username": "testuser", "scope": "test_scope"}
        token = create_jwt(data)

        # Decode token manually to verify payload
        decoded = jwt.decode(token, self.secret, algorithms=[self.algorithm])

        # Payload should contain the same data
        self.assertEqual(decoded["username"], "testuser")
        self.assertEqual(decoded["scope"], "test_scope")

        # Payload should include an expiration field (`exp`)
        self.assertIn("exp", decoded)

        # Expiration should be within a reasonable time window
        exp_datetime = datetime.fromtimestamp(decoded["exp"], tz=timezone.utc)
        expected_exp = datetime.now(timezone.utc) + timedelta(
            minutes=settings.EXPIRES_MINUTES
        )

        # allow for small time difference (< 5 seconds)
        time_diff = abs((expected_exp - exp_datetime).total_seconds())
        self.assertLess(time_diff, 5, "Expiration time deviates too much")

    def test_decode_and_verify_jwt_success(self):
        data = {"username": "testuser"}
        token = jwt.encode(data, self.secret, algorithm=self.algorithm)

        def mock_verify(payload):
            self.assertIn("username", payload)

        decoded = decode_and_verify_jwt(token, mock_verify)
        self.assertEqual(decoded["username"], "testuser")

    def test_decode_and_verify_jwt_expired(self):
        expired_token = jwt.encode(
            {"exp": datetime.utcnow() - timedelta(minutes=1)},
            self.secret,
            algorithm=self.algorithm,
        )

        with self.assertRaises(TokenValidationException) as ctx:
            decode_and_verify_jwt(expired_token, lambda x: x)
        self.assertIn("Token expired", str(ctx.exception))

    def test_decode_and_verify_jwt_invalid_token(self):
        invalid_token = "invalid.jwt.token"
        with self.assertRaises(TokenValidationException) as ctx:
            decode_and_verify_jwt(invalid_token, lambda x: x)
        self.assertIn("Invalid token", str(ctx.exception))

    def test_verify_is_able_to_set_password_valid_scopes(self):
        for scope in [
            TokenScope.PASSWORD_VERIFY_SCOPE,
            TokenScope.SECURITY_QUESTION_VERIFY_SCOPE,
        ]:
            verify_is_able_to_set_password({"scope": scope})

    def test_verify_is_able_to_set_password_invalid_scope(self):
        with self.assertRaises(TokenValidationException):
            verify_is_able_to_set_password({"scope": "INVALID"})

    def test_verify_is_able_to_set_password_missing_scope(self):
        with self.assertRaises(TokenValidationException):
            verify_is_able_to_set_password({})

    def test_verify_is_able_to_set_security_qa_valid_scope(self):
        verify_is_able_to_set_security_qa(
            {"scope": TokenScope.PASSWORD_VERIFY_SCOPE}
        )  # should not raise

    def test_verify_is_able_to_set_security_qa_invalid_scope(self):
        with self.assertRaises(TokenValidationException):
            verify_is_able_to_set_security_qa(
                {"scope": TokenScope.SECURITY_QUESTION_VERIFY_SCOPE}
            )

    def test_verify_is_able_to_set_security_qa_missing_scope(self):
        with self.assertRaises(TokenValidationException):
            verify_is_able_to_set_security_qa({})
