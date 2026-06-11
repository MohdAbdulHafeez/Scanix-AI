from fastapi import HTTPException
from starlette import status


class ScanixException(Exception):
    """
    Base application exception.
    """

    def __init__(
        self,
        message: str,
    ):
        self.message = message
        super().__init__(message)


class NotFoundException(
    ScanixException
):
    pass


class ValidationException(
    ScanixException
):
    pass


class UnauthorizedException(
    ScanixException
):
    pass


class ForbiddenException(
    ScanixException
):
    pass


def raise_not_found(
    message: str,
) -> None:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=message,
    )


def raise_bad_request(
    message: str,
) -> None:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=message,
    )


def raise_unauthorized(
    message: str,
) -> None:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=message,
    )


def raise_forbidden(
    message: str,
) -> None:
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=message,
    )


def raise_internal_error(
    message: str,
) -> None:
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=message,
    )