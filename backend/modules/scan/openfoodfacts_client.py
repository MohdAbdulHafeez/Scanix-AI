from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx

from core.config import settings
from core.logging import get_logger


logger = get_logger(__name__)


class OpenFoodFactsClient:
    """
    Production OpenFoodFacts Client.

    Responsibilities
    ----------------
    - Barcode Lookup
    - OCR Product Search
    - Product Ranking
    - Health Check
    - Retry
    - Connection Pooling
    - Request Validation
    """

    def __init__(self) -> None:

        self._client = httpx.AsyncClient(
            base_url=settings.OPENFOODFACTS_BASE_URL,
            timeout=httpx.Timeout(
                timeout=settings.OPENFOODFACTS_TIMEOUT,
                connect=settings.OPENFOODFACTS_CONNECT_TIMEOUT,
                read=settings.OPENFOODFACTS_READ_TIMEOUT,
            ),
            limits=httpx.Limits(
                max_connections=settings.OPENFOODFACTS_MAX_CONNECTIONS,
                max_keepalive_connections=settings.OPENFOODFACTS_MAX_KEEPALIVE,
                keepalive_expiry=60,
            ),
            headers=self._default_headers(),
            follow_redirects=True,
            http2=True,
        )

    def _default_headers(self) -> dict[str, str]:

        return {
            "User-Agent": settings.OPENFOODFACTS_USER_AGENT,
            "Accept": "application/json",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }

    async def close(self) -> None:

        await self._client.aclose()

    async def __aenter__(self):

        return self

    async def __aexit__(
        self,
        exc_type,
        exc,
        tb,
    ) -> None:

        await self.close()

    async def _request(
        self,
        method: str,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        retries = settings.OPENFOODFACTS_MAX_RETRIES

        last_error: Exception | None = None

        for attempt in range(1, retries + 1):

            started = time.perf_counter()

            try:

                response = await self._client.request(
                    method=method,
                    url=endpoint,
                    params=params,
                )

                latency = (
                    time.perf_counter() - started
                ) * 1000

                logger.info(
                    "OFF request",
                    extra={
                        "endpoint": endpoint,
                        "status": response.status_code,
                        "latency_ms": round(latency, 2),
                        "attempt": attempt,
                    },
                )

                response.raise_for_status()

                return response.json()

            except (
                httpx.TimeoutException,
                httpx.NetworkError,
                httpx.HTTPStatusError,
            ) as exc:

                last_error = exc

                logger.warning(
                    "OFF retry",
                    extra={
                        "attempt": attempt,
                        "endpoint": endpoint,
                        "error": str(exc),
                    },
                )

                if attempt == retries:
                    break

                await asyncio.sleep(
                    settings.OPENFOODFACTS_BACKOFF_FACTOR
                    * (2 ** (attempt - 1))
                )

        logger.error(
            "OFF request failed",
            extra={
                "endpoint": endpoint,
                "error": str(last_error),
            },
        )

        raise last_error  # type: ignore[misc]

    @staticmethod
    def _validate_product_response(
        response: dict[str, Any],
    ) -> bool:

        if not response:
            return False

        if response.get("status") != 1:
            return False

        if "product" not in response:
            return False

        return True

    @staticmethod
    def _validate_search_response(
        response: dict[str, Any],
    ) -> bool:

        if not response:
            return False

        products = response.get("products")

        if not isinstance(products, list):
            return False

        return True

    @staticmethod
    def _normalize_search_text(
        text: str,
    ) -> str:

        return (
            text.lower()
            .replace("-", " ")
            .replace("_", " ")
            .strip()
        )
    

    # ==========================================================
# PUBLIC API
# ==========================================================

async def get_product_by_barcode(
    self,
    barcode: str,
) -> dict[str, Any] | None:

    barcode = self._sanitize_barcode(barcode)

    if not barcode:
        return None

    endpoint = (
        f"/api/v2/product/{barcode}.json"
    )

    logger.info(
        "Barcode lookup started",
        extra={
            "barcode": barcode,
        },
    )

    response = await self._request(
        "GET",
        endpoint,
    )

    if not self._validate_product_response(
        response
    ):

        logger.warning(
            "Barcode not found",
            extra={
                "barcode": barcode,
            },
        )

        return None

    product = response["product"]

    logger.info(
        "Barcode lookup successful",
        extra={
            "barcode": barcode,
            "product_name": product.get(
                "product_name"
            ),
            "brand": product.get(
                "brands"
            ),
        },
    )

    return product


async def search_products(
    self,
    *,
    product_name: str,
    brand: str | None = None,
    category: str | None = None,
    page_size: int = 20,
) -> list[dict[str, Any]]:

    queries = self._build_search_queries(
        product_name=product_name,
        brand=brand,
        category=category,
    )

    merged_results: list[dict[str, Any]] = []

    seen_codes: set[str] = set()

    for query in queries:

        params = {
            "search_terms": query,
            "search_simple": 1,
            "action": "process",
            "json": 1,
            "page_size": page_size,
        }

        logger.info(
            "Searching OFF",
            extra={
                "query": query,
            },
        )

        response = await self._request(
            "GET",
            "/cgi/search.pl",
            params=params,
        )

        if not self._validate_search_response(
            response
        ):
            continue

        for product in response.get(
            "products",
            [],
        ):

            barcode = product.get(
                "code",
                "",
            )

            if barcode in seen_codes:
                continue

            seen_codes.add(barcode)

            merged_results.append(product)

    logger.info(
        "Search completed",
        extra={
            "queries": len(queries),
            "results": len(
                merged_results
            ),
        },
    )

    return merged_results


# ==========================================================
# SEARCH QUERY BUILDER
# ==========================================================

def _build_search_queries(
    self,
    *,
    product_name: str,
    brand: str | None,
    category: str | None,
) -> list[str]:

    queries: list[str] = []

    product_name = self._normalize_search_text(
        product_name
    )

    if brand:

        brand = self._normalize_search_text(
            brand
        )

    if category:

        category = self._normalize_search_text(
            category
        )

    # Highest confidence

    if brand and product_name:

        queries.append(
            f"{brand} {product_name}"
        )

    # Product name only

    queries.append(product_name)

    # Brand only

    if brand:

        queries.append(brand)

    # Category

    if category:

        queries.append(category)

    # Brand + Category

    if brand and category:

        queries.append(
            f"{brand} {category}"
        )

    # Remove duplicates while preserving order

    unique_queries = []

    seen = set()

    for query in queries:

        query = query.strip()

        if (
            query
            and query not in seen
        ):

            unique_queries.append(query)

            seen.add(query)

    return unique_queries


# ==========================================================
# HELPERS
# ==========================================================

@staticmethod
def _sanitize_barcode(
    barcode: str,
) -> str:

    barcode = "".join(
        c for c in barcode
        if c.isdigit()
    )

    if len(barcode) not in (
        8,
        12,
        13,
        14,
    ):
        return ""

    return barcode


from rapidfuzz import fuzz


# ==========================================================
# PRODUCT RANKING ENGINE
# ==========================================================

def _rank_products(
    self,
    products: list[dict[str, Any]],
    *,
    product_name: str,
    brand: str | None,
    category: str | None,
) -> list[dict[str, Any]]:

    ranked: list[tuple[int, dict[str, Any]]] = []

    target_name = self._normalize_search_text(
        product_name
    )

    target_brand = (
        self._normalize_search_text(brand)
        if brand
        else ""
    )

    target_category = (
        self._normalize_search_text(category)
        if category
        else ""
    )

    for product in products:

        score = self._calculate_product_score(
            product,
            target_name=target_name,
            target_brand=target_brand,
            target_category=target_category,
        )

        product["_scanix_confidence"] = score

        ranked.append(
            (
                score,
                product,
            )
        )

    ranked.sort(
        key=lambda x: x[0],
        reverse=True,
    )

    return [
        product
        for _, product in ranked
    ]


def _calculate_product_score(
    self,
    product: dict[str, Any],
    *,
    target_name: str,
    target_brand: str,
    target_category: str,
) -> int:

    score = 0.0

    off_name = self._normalize_search_text(
        product.get(
            "product_name",
            "",
        )
    )

    off_brand = self._normalize_search_text(
        product.get(
            "brands",
            "",
        )
    )

    off_category = self._normalize_search_text(
        product.get(
            "categories",
            "",
        )
    )

    # ------------------------------------------------------
    # Product Name (40%)
    # ------------------------------------------------------

    name_similarity = fuzz.token_set_ratio(
        target_name,
        off_name,
    )

    score += (
        name_similarity * 0.40
    )

    # ------------------------------------------------------
    # Brand (20%)
    # ------------------------------------------------------

    if target_brand:

        brand_similarity = fuzz.token_set_ratio(
            target_brand,
            off_brand,
        )

        score += (
            brand_similarity * 0.20
        )

    else:

        score += 10

    # ------------------------------------------------------
    # Category (10%)
    # ------------------------------------------------------

    if target_category:

        category_similarity = fuzz.token_set_ratio(
            target_category,
            off_category,
        )

        score += (
            category_similarity * 0.10
        )

    else:

        score += 5

    # ------------------------------------------------------
    # Barcode Presence (5%)
    # ------------------------------------------------------

    if product.get("code"):

        score += 5

    # ------------------------------------------------------
    # Nutrition Completeness (5%)
    # ------------------------------------------------------

    nutriments = product.get(
        "nutriments",
        {},
    )

    if isinstance(
        nutriments,
        dict,
    ):

        important = [

            "energy-kcal_100g",

            "proteins_100g",

            "fat_100g",

            "carbohydrates_100g",

            "sugars_100g",

            "fiber_100g",

            "salt_100g",
        ]

        available = sum(
            1
            for field in important
            if field in nutriments
        )

        score += (
            available
            / len(important)
        ) * 5

    # ------------------------------------------------------
    # Ingredient Completeness (5%)
    # ------------------------------------------------------

    ingredients = product.get(
        "ingredients",
        [],
    )

    if ingredients:

        score += 5

    # ------------------------------------------------------
    # Images (5%)
    # ------------------------------------------------------

    images = [

        product.get(
            "image_front_url"
        ),

        product.get(
            "image_ingredients_url"
        ),

        product.get(
            "image_nutrition_url"
        ),

        product.get(
            "image_packaging_url"
        ),
    ]

    score += min(
        len(
            [
                img
                for img in images
                if img
            ]
        ),
        4,
    ) * 1.25

    # ------------------------------------------------------
    # OFF Completeness (10%)
    # ------------------------------------------------------

    completeness = product.get(
        "completeness",
        0,
    )

    try:

        score += min(
            float(
                completeness
            ),
            100,
        ) * 0.10

    except Exception:

        pass

    return min(
        round(score),
        100,
    )


# ==========================================================
# BEST MATCH SELECTION
# ==========================================================

async def search_best_match(
    self,
    *,
    product_name: str,
    brand: str | None = None,
    category: str | None = None,
) -> dict[str, Any] | None:

    products = await self.search_products(
        product_name=product_name,
        brand=brand,
        category=category,
        page_size=30,
    )

    if not products:

        logger.warning(
            "No products found",
            extra={
                "product_name": product_name,
            },
        )

        return None

    products = self._remove_duplicate_products(
        products
    )

    products = self._filter_low_quality_products(
        products
    )

    ranked = self._rank_products(
        products,
        product_name=product_name,
        brand=brand,
        category=category,
    )

    if not ranked:

        return None

    best = ranked[0]

    logger.info(
        "Best product selected",
        extra={
            "product": best.get(
                "product_name"
            ),
            "confidence": best.get(
                "_scanix_confidence"
            ),
        },
    )

    return best


# ==========================================================
# DEDUPLICATION
# ==========================================================

def _remove_duplicate_products(
    self,
    products: list[dict[str, Any]],
) -> list[dict[str, Any]]:

    unique = {}

    for product in products:

        barcode = product.get(
            "code"
        )

        if barcode:

            existing = unique.get(barcode)

            if existing is None:

                unique[barcode] = product

                continue

            if (
                product.get(
                    "completeness",
                    0,
                )
                >
                existing.get(
                    "completeness",
                    0,
                )
            ):

                unique[barcode] = product

        else:

            key = (
                self._normalize_search_text(
                    product.get(
                        "product_name",
                        "",
                    )
                )
                +
                self._normalize_search_text(
                    product.get(
                        "brands",
                        "",
                    )
                )
            )

            unique[key] = product

    return list(unique.values())


# ==========================================================
# QUALITY FILTER
# ==========================================================

def _filter_low_quality_products(
    self,
    products: list[dict[str, Any]],
) -> list[dict[str, Any]]:

    filtered = []

    for product in products:

        if not product.get(
            "product_name"
        ):
            continue

        nutriments = product.get(
            "nutriments",
            {}
        )

        ingredients = product.get(
            "ingredients",
            []
        )

        images = any(

            product.get(field)

            for field in (

                "image_front_url",

                "image_nutrition_url",

                "image_ingredients_url",
            )
        )

        completeness = float(
            product.get(
                "completeness",
                0,
            )
            or 0
        )

        score = 0

        if nutriments:
            score += 1

        if ingredients:
            score += 1

        if images:
            score += 1

        if completeness >= 50:
            score += 1

        if score >= 2:

            filtered.append(product)

    return filtered


# ==========================================================
# FALLBACK SEARCH
# ==========================================================

async def search_with_fallback(
    self,
    *,
    product_name: str,
    brand: str | None = None,
    category: str | None = None,
) -> dict[str, Any] | None:

    product = await self.search_best_match(

        product_name=product_name,

        brand=brand,

        category=category,
    )

    if product:

        return product

    logger.info(
        "Running fallback search"
    )

    products = await self.search_products(

        product_name=product_name,

        page_size=20,
    )

    if not products:

        return None

    ranked = self._rank_products(

        products,

        product_name=product_name,

        brand=None,

        category=None,
    )

    if not ranked:

        return None

    return ranked[0]


