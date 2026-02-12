from django.test import TestCase, RequestFactory
from unittest.mock import patch
from rest_framework_simplejwt.exceptions import TokenError

from users.models import CustomUser
from core.auth.constants import ACCESS_TOKEN, SCOPE_TOKEN
from core.auth.utils import (
    get_token_from_cookies,
    get_token_from_header,
    check_token_validity,
)
from core.auth.tokens import ScopeTokenPurpose, ScopeToken
from tests.helpers.setup_mock_token import TokenFactory
from tests.helpers.setup_mock_accounts import create_test_users, ACTIVE_USER_USERNAME


class TestGetTokenFunctions(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_get_token_from_header_success(self):
        request = self.factory.get("/", headers={"Authorization": f"Bearer token"})
        result = get_token_from_header(request)
        self.assertEqual(result, ("token", ACCESS_TOKEN))

    def test_get_token_from_header_fail(self):
        request = self.factory.get("/")
        result = get_token_from_header(request)
        self.assertEqual(result, (None, None))

    def test_get_token_from_cookies_success(self):
        request = self.factory.get("/")
        request.COOKIES = {ACCESS_TOKEN: "token"}
        result = get_token_from_cookies(request, [ACCESS_TOKEN])
        self.assertEqual(result, ("token", ACCESS_TOKEN))

    def test_get_token_from_cookies_success_w_priority_order(self):
        request = self.factory.get("/")
        request.COOKIES = {SCOPE_TOKEN: "token"}
        result = get_token_from_cookies(request, [ACCESS_TOKEN, SCOPE_TOKEN])
        self.assertEqual(result, ("token", SCOPE_TOKEN))


class TestVerifyTokenFunctions(TestCase):
    def setUp(self):
        create_test_users()
        self.active_user = CustomUser.objects.get(username=ACTIVE_USER_USERNAME)

    @patch("core.auth.utils.BaseRedis.exists", return_value=False)
    def test_access_token_valid(self, mock_blacklist_token_exist):
        token = TokenFactory.valid_token(ACCESS_TOKEN, ACTIVE_USER_USERNAME)
        result = check_token_validity(token, ACCESS_TOKEN)
        self.assertIsNotNone(result)
        self.assertEqual(result.get("user_id"), self.active_user.id)

    @patch("core.auth.utils.ScopeTokenRedis.exists", return_value=False)
    def test_scope_token_valid(self, mock_blacklist_token_exist):
        token = TokenFactory.valid_token(
            SCOPE_TOKEN, ACTIVE_USER_USERNAME, [ScopeTokenPurpose.PASSWORD_VERIFY_SCOPE]
        )
        result = check_token_validity(token, SCOPE_TOKEN)
        self.assertIsNotNone(result)
        self.assertEqual(result.get("user_id"), self.active_user.id)

    @patch("core.auth.utils.BaseRedis.exists")
    def test_token_invalid(self, mock_blacklist_token_exist):
        token = TokenFactory.invalid_signature()
        with self.assertRaises(TokenError):
            check_token_validity(token, ACCESS_TOKEN)
        mock_blacklist_token_exist.assert_not_called()

    @patch("core.auth.utils.BaseRedis.exists", return_value=True)
    def test_token_blacklist(self, mock_blacklist_token_exist):
        token = TokenFactory.valid_token(ACCESS_TOKEN, ACTIVE_USER_USERNAME)
        with self.assertRaises(TokenError) as context:
            check_token_validity(token, ACCESS_TOKEN)
        self.assertEqual(str(context.exception), "Token is blacklisted")
        mock_blacklist_token_exist.assert_called_once()

    def test_scope_token_verify_scope_success(self):
        token = ScopeToken.for_user(
            self.active_user, scope=ScopeTokenPurpose.PASSWORD_VERIFY_SCOPE
        )
        token.verify_scope([ScopeTokenPurpose.PASSWORD_VERIFY_SCOPE])

    def test_verify_scope_mismatch_raises_token_error(self):
        token = ScopeToken.for_user(
            self.active_user, scope=ScopeTokenPurpose.PASSWORD_VERIFY_SCOPE
        )
        with self.assertRaises(TokenError) as context:
            token.verify_scope([ScopeTokenPurpose.SECURITY_QUESTION_VERIFY_SCOPE])
        self.assertEqual(str(context.exception), "Token scope mismatch")
