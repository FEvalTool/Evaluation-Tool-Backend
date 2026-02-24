import logging
import time

from django.http import JsonResponse
from django.conf import settings
from rest_framework import status
from rest_framework.viewsets import ViewSet
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError, APIException
from rest_framework.parsers import MultiPartParser, FormParser

from core.constants import ErrorTypes, EventType
from core.auth.authentication import configure_auth
from core.storage import AvatarsMediaStorage
from ..validators import AvatarImgValidators

logger = logging.getLogger(__name__)


class AvatarViewSet(ViewSet):
    """
    Viewset for support Account Avatar related APIs
    (Set, Delete)
    """

    parser_classes = [MultiPartParser, FormParser]
    authentication_classes = [
        configure_auth(cookie_priority=[settings.COOKIE_SETTINGS["AUTH_COOKIE_ACCESS"]])
    ]
    storage = AvatarsMediaStorage()

    def _delete_old_avatar(self, old_key):
        """Delete old avatar from S3 if it exists."""
        if old_key:
            self.storage.delete(old_key)

    @action(
        detail=False,
        methods=["patch"],
        url_path="upload",
    )
    def upload(self, request):
        """
        Endpoint to upload account avatar
        """
        try:
            logger.info(
                {
                    "event_type": EventType.UPLOAD_AVATAR,
                    "message": "Begin upload avatar - validate file",
                }
            )
            file = request.FILES.get("image")
            AvatarImgValidators.validate(file)

            logger.info(
                {
                    "event_type": EventType.UPLOAD_AVATAR,
                    "message": "Validate file complete - begin upload",
                }
            )
            user = request.user
            if user.avatar:
                # Delete old avatar image
                self.storage.delete(user.avatar.name)
            # Generate filename with original name + unix timestamp
            original_name = file.name.rsplit(".", 1)[0]  # filename without ext
            ext = file.name.rsplit(".", 1)[-1]
            file.name = f"{original_name}_{int(time.time())}.{ext}"
            # Update avatar
            user.avatar = file
            user.save(update_fields=["avatar"])
            # Return presigned URL
            presigned_url = self.storage.url(user.avatar.name)

            logger.info(
                {
                    "event_type": EventType.UPLOAD_AVATAR,
                    "message": "Complete upload avatar",
                }
            )
            return JsonResponse(
                {
                    "message": "Successfully upload avatar",
                    "data": {"avatar": presigned_url},
                },
            )
        except ValidationError as e:
            logger.error(
                {
                    "event_type": EventType.UPLOAD_AVATAR,
                    "error_type": ErrorTypes.REQUEST_VALIDATION,
                    "error_content": e.detail,
                }
            )
            raise e
        except Exception as e:
            logger.error(
                {
                    "event_type": EventType.UPLOAD_AVATAR,
                    "error_type": ErrorTypes.EXCEPTION,
                    "error_content": str(e),
                }
            )
            raise APIException()

    @action(
        detail=False,
        methods=["delete"],
        url_path="delete",
    )
    def delete(self, request):
        """
        Endpoint to delete account avatar
        """
        try:
            logger.info(
                {
                    "event_type": EventType.DELETE_AVATAR,
                    "message": "Begin delete avatar",
                }
            )
            user = request.user
            if user.avatar:
                # Delete old avatar image
                self.storage.delete(user.avatar.name)
                logger.info(
                    {
                        "event_type": EventType.DELETE_AVATAR,
                        "message": "Delete avatar in S3 success - Update user info",
                    }
                )
                # Update avatar
                logger.info(
                    {
                        "event_type": EventType.DELETE_AVATAR,
                        "message": "Update user info success",
                    }
                )
                user.avatar = None
                user.save(update_fields=["avatar"])
            return JsonResponse(
                {"message": "Successfully delete avatar"},
                status=status.HTTP_204_NO_CONTENT,
            )
        except Exception as e:
            logger.error(
                {
                    "event_type": EventType.DELETE_AVATAR,
                    "error_type": ErrorTypes.EXCEPTION,
                    "error_content": str(e),
                }
            )
            raise APIException()

    @action(
        detail=False,
        methods=["get"],
        url_path="get",
    )
    def get(self, request):
        """
        Endpoint to get account avatar
        """
        try:
            logger.info(
                {
                    "event_type": EventType.GET_AVATAR,
                    "message": "Begin retrieve account avatar",
                }
            )
            user = request.user
            presigned_url = None
            if user.avatar:
                presigned_url = self.storage.url(user.avatar.name)

            logger.info(
                {
                    "event_type": EventType.GET_AVATAR,
                    "message": "Retrieve account avatar success",
                }
            )
            return JsonResponse(
                {
                    "message": "Successfully retreive account avatar",
                    "data": {"avatar": presigned_url},
                },
            )
        except Exception as e:
            logger.error(
                {
                    "event_type": EventType.GET_AVATAR,
                    "error_type": ErrorTypes.EXCEPTION,
                    "error_content": str(e),
                }
            )
            raise APIException()
