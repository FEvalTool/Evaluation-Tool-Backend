from django.test import TestCase, RequestFactory
from rest_framework.exceptions import AuthenticationFailed, NotAuthenticated, NotFound

from users.models import CustomUser
from core.auth.authentication import CustomTokenAuthentication, configure_auth
from core.auth.tokens import ScopeTokenPurpose
from core.auth.constants import ACCESS_TOKEN, SCOPE_TOKEN
from tests.helpers.setup_mock_token import TokenFactory
from tests.helpers.setup_mock_accounts import create_test_users, ACTIVE_USER_USERNAME


class TestCustomTokenAuthentication(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.auth = CustomTokenAuthentication()
        create_test_users()
        self.active_user = CustomUser.objects.get(username=ACTIVE_USER_USERNAME)

    def test_header_token_full_flow(self):
        self.auth.use_header = True
        token = TokenFactory.valid_token(
            token_type=ACCESS_TOKEN,
            username=ACTIVE_USER_USERNAME,
        )
        request = self.factory.get("/", headers={"Authorization": f"Bearer {token}"})

        user, _ = self.auth.authenticate(request)

        self.assertEqual(user.id, self.active_user.id)

    def test_access_token_full_flow(self):
        self.auth.use_header = False
        self.auth.cookie_priority = [ACCESS_TOKEN]
        token = TokenFactory.valid_token(
            token_type=ACCESS_TOKEN,
            username=ACTIVE_USER_USERNAME,
        )
        request = self.factory.get("/")
        request.COOKIES = {ACCESS_TOKEN: token}

        user, _ = self.auth.authenticate(request)

        self.assertEqual(user.id, self.active_user.id)

    def test_scope_token_full_flow(self):
        self.auth.use_header = False
        self.auth.cookie_priority = [SCOPE_TOKEN]
        self.auth.valid_scopes = [ScopeTokenPurpose.PASSWORD_VERIFY_SCOPE]
        token = TokenFactory.valid_token(
            token_type=SCOPE_TOKEN,
            scope=ScopeTokenPurpose.PASSWORD_VERIFY_SCOPE,
            username=ACTIVE_USER_USERNAME,
        )
        request = self.factory.get("/")
        request.COOKIES = {SCOPE_TOKEN: token}

        user, _ = self.auth.authenticate(request)

        self.assertEqual(user.id, self.active_user.id)

    def test_no_token_raises_not_authenticated(self):
        request = self.factory.get("/")
        request.COOKIES = {}
        self.auth.cookie_priority = ["access"]

        with self.assertRaises(NotAuthenticated):
            self.auth.authenticate(request)

    def test_optional_with_no_token_returns_none(self):
        request = self.factory.get("/")
        request.COOKIES = {}
        self.auth.optional = True
        self.auth.cookie_priority = ["access"]

        user, token = self.auth.authenticate(request)

        self.assertIsNone(user)
        self.assertIsNone(token)

    def test_invalid_token(self):
        self.auth.use_header = True
        token = TokenFactory.invalid_signature()
        request = self.factory.get("/", headers={"Authorization": f"Bearer {token}"})

        with self.assertRaises(AuthenticationFailed):
            self.auth.authenticate(request)

    def test_user_not_found(self):
        self.auth.use_header = True
        token = TokenFactory.unknown_user(token_type=ACCESS_TOKEN)
        request = self.factory.get("/", headers={"Authorization": f"Bearer {token}"})

        with self.assertRaises(NotFound):
            self.auth.authenticate(request)


class TestConfigureAuth(TestCase):
    def test_configure_auth_sets_correct_attributes(self):
        AuthClass = configure_auth(
            cookie_priority=["access", "scope"],
            use_header=True,
            valid_scopes=["PASSWORD_VERIFY_SCOPE"],
            optional=True,
        )
        self.assertEqual(AuthClass.cookie_priority, ["access", "scope"])
        self.assertTrue(AuthClass.use_header)
        self.assertEqual(AuthClass.valid_scopes, ["PASSWORD_VERIFY_SCOPE"])
        self.assertTrue(AuthClass.optional)
