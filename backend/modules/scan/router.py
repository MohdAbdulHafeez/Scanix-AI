# ==========================================================
# SCANIX AI - SYSTEM 1 ROUTER (PRODUCTION GRADE)
# ==========================================================

from typing import Optional

from fastapi import APIRouter, Body, Depends, File, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.dependencies import get_db, get_optional_user, rate_limit
from core.exceptions import FileTooLargeError, InvalidFileTypeError
from core.logging import get_api_logger

from modules.scan.constants import SUPPORTED_IMAGE_TYPES
from modules.scan.schemas import (
    ManualBarcodeRequest,
    ManualSearchRequest,
    ScanReport,
    SearchResponse,
)
from modules.scan.service import scan_service
from modules.scan.engines.product_identity_engine import product_identity_engine


router = APIRouter(
    prefix="/scan",
    tags=["Scan Intelligence System 1"],
)

logger = get_api_logger()


async def validate_image_upload(file: UploadFile) -> bytes:

    if file.content_type not in SUPPORTED_IMAGE_TYPES:

        raise InvalidFileTypeError(
            allowed_types=list(SUPPORTED_IMAGE_TYPES),
            received_type=file.content_type or "unknown",
        )

    content = await file.read()

    size_mb = len(content) / (1024 * 1024)

    if size_mb > settings.MAX_UPLOAD_MB:

        raise FileTooLargeError(
            max_size_mb=settings.MAX_UPLOAD_MB,
            actual_size_mb=size_mb,
        )

    return content


@router.post(
    "/image",
    response_model=ScanReport,
    status_code=status.HTTP_200_OK,
    summary="Full OCR & Data Fusion Pipeline",
)
async def process_image_scan(
    file: UploadFile = File(...),
    user_id: Optional[str] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
    _rate_limit: bool = Depends(rate_limit),
):

    logger.info(
        f"Image scan initiated by {user_id or 'anonymous'}"
    )

    image_bytes = await validate_image_upload(file)

    return await scan_service.process_image_scan(
        image_bytes=image_bytes,
        user_id=user_id,
        db=db,
    )


@router.post(
    "/barcode",
    response_model=ScanReport,
    status_code=status.HTTP_200_OK,
    summary="Database Lookup by Barcode",
)
async def process_manual_barcode(
    payload: ManualBarcodeRequest = Body(...),
    user_id: Optional[str] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
    _rate_limit: bool = Depends(rate_limit),
):

    logger.info(
        f"Manual barcode lookup: {payload.barcode}"
    )

    return await scan_service.process_barcode_scan(
        barcode=payload.barcode,
        user_id=user_id,
        db=db,
    )


@router.post(
    "/search",
    response_model=SearchResponse,
    status_code=status.HTTP_200_OK,
    summary="OpenFoodFacts Name Search",
)
async def process_manual_search(
    payload: ManualSearchRequest = Body(...),
    user_id: Optional[str] = Depends(get_optional_user),
    _rate_limit: bool = Depends(rate_limit),
):

    logger.info(
        f"Manual text search: {payload.query}"
    )

    results = await product_identity_engine.search_openfoodfacts(
        payload.query
    )

    return SearchResponse(
        success=True,
        results=results or [],
    )