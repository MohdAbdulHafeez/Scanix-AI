# ==========================================================
# SCANIX AI - SYSTEM 1 CONSTANTS
# ==========================================================
# Production-grade constants for all scanning operations.
# Contains ONLY essential constants. No hardcoded brands or categories.
# Product identification uses OpenFoodFacts as source of truth.
# Immutability enforced via MappingProxyType and tuples.
# ==========================================================

import re
from types import MappingProxyType
from typing import Mapping, Tuple, Set


# ==========================================================
# UPLOAD LIMITS
# ==========================================================

SUPPORTED_IMAGE_TYPES: frozenset[str] = frozenset([
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
])


# ==========================================================
# OCR THRESHOLDS
# ==========================================================

MIN_OCR_CONFIDENCE: float = 0.40
GOOD_OCR_CONFIDENCE: float = 0.75
EXCELLENT_OCR_CONFIDENCE: float = 0.90
MIN_TEXT_LENGTH_FOR_VALID_OCR: int = 10
MIN_WORDS_FOR_VALID_OCR: int = 3


# ==========================================================
# IMAGE QUALITY THRESHOLDS
# ==========================================================

MIN_IMAGE_QUALITY_SCORE: int = 40
GOOD_IMAGE_QUALITY_SCORE: int = 70
EXCELLENT_IMAGE_QUALITY_SCORE: int = 90
MIN_SHARPNESS_SCORE: int = 30
MIN_BRIGHTNESS_SCORE: int = 20
MIN_CONTRAST_SCORE: int = 20


# ==========================================================
# CONFIDENCE THRESHOLDS (Centralized)
# ==========================================================

LOW_CONFIDENCE: int = 50
MEDIUM_CONFIDENCE: int = 75
HIGH_CONFIDENCE: int = 90
PRODUCT_NAME_MIN_CONFIDENCE: int = 60
BRAND_MIN_CONFIDENCE: int = 50


# ==========================================================
# CONFIDENCE LEVEL RANGES
# ==========================================================

CONFIDENCE_LEVELS: Mapping[str, Tuple[int, int]] = MappingProxyType({
    "critical": (0, 30),
    "high_risk": (31, 50),
    "moderate": (51, 70),
    "low_risk": (71, 85),
    "excellent": (86, 100),
})


# ==========================================================
# PRODUCT FUSION WEIGHTS
# ==========================================================

FUSION_WEIGHTS: Mapping[str, float] = MappingProxyType({
    "barcode": 0.35,
    "ocr": 0.25,
    "openfoodfacts": 0.40,
})


# ==========================================================
# VERIFICATION WEIGHTS
# ==========================================================

VERIFICATION_WEIGHTS: Mapping[str, float] = MappingProxyType({
    "barcode_verified": 15.0,
    "ocr_verified": 10.0,
    "database_verified": 15.0,
    "fusion_verified": 15.0,
    "product_name_verified": 10.0,
    "brand_verified": 10.0,
    "category_verified": 5.0,
    "nutrition_verified": 10.0,
    "ingredients_verified": 10.0,
})


# ==========================================================
# VERIFICATION THRESHOLDS
# ==========================================================

MIN_VERIFICATION_SCORE: int = 50
GOOD_VERIFICATION_SCORE: int = 75
EXCELLENT_VERIFICATION_SCORE: int = 90


# ==========================================================
# RELIABILITY THRESHOLDS
# ==========================================================

HIGH_RELIABILITY_SCORE: int = 75
MEDIUM_RELIABILITY_SCORE: int = 60


# ==========================================================
# OCR CORRECTIONS (Common OCR mistakes - Safe corrections only)
# ==========================================================
# Note: Brand-specific corrections (e.g., "lays" -> "Lay's") are intentionally
# excluded. Product identification relies on OpenFoodFacts as source of truth.
# These corrections are for generic OCR typos only.

OCR_CORRECTIONS: Mapping[str, str] = MappingProxyType({
    # Ingredient typos
    "ingredicnts": "ingredients",
    "ingredents": "ingredients",
    "ingrdients": "ingredients",
    "ingredlents": "ingredients",
    "ingrediente": "ingredients",
    "ingredients": "ingredients",
    "ingredient": "ingredients",

    # Nutrition typos
    "nutrtion": "nutrition",
    "nutrltion": "nutrition",
    "nutritlon": "nutrition",
    "nutriti0n": "nutrition",

    # Protein typos
    "protien": "protein",
    "proteIn": "protein",
    "proteln": "protein",
    "prote1n": "protein",

    # Energy typos
    "energv": "energy",
    "enerqv": "energy",
    "ener9y": "energy",
    "enerqy": "energy",

    # Carbohydrate typos
    "carbohvdrate": "carbohydrate",
    "carbohvbrate": "carbohydrate",
    "carb0hydrate": "carbohydrate",

    # Sodium typos
    "sodiurn": "sodium",
    "sodlum": "sodium",
    "sodivm": "sodium",
    "s0dium": "sodium",

    # Flavour typos
    "lavourings": "flavourings",
    "flav0urings": "flavourings",
    "flavouring": "flavouring",

    # Chocolate typos
    "diecolate": "chocolate",
    "ch0colate": "chocolate",
    "chocolale": "chocolate",
    "choc0late": "chocolate",

    # Oil typos
    "vegetable 0il": "vegetable oil",
    "vegetabIe oil": "vegetable oil",
    "sunfiower oil": "sunflower oil",
    "sunfl0wer oil": "sunflower oil",

    # Additive typos
    "preservatIve": "preservative",
    "preservatlve": "preservative",
    "emulsifler": "emulsifier",
    "emulsitier": "emulsifier",
    "stabiliser": "stabilizer",
    "stabills er": "stabilizer",
    "antloxldant": "antioxidant",
    "antioxidant": "antioxidant",

    # Common substitutions
    "colour": "color",
    "fibre": "fiber",
    "kilojoules": "kilojoules",
    "kj": "kj",
    "kcal": "kcal",

    # Common OCR errors (generic only)
    "ccntains": "contains",
    "conlain": "contain",
    "suphite": "sulphite",
    "al}": "all",
    "coco": "cocoa",
    "in oia": "India",
    "pml": "Pvt Ltd",
})


# ==========================================================
# INTERNATIONAL OCR SECTION KEYWORDS
# ==========================================================
# Multi-language support for ingredient and nutrition section detection

SECTION_KEYWORDS_MULTI: Mapping[str, Tuple[str, ...]] = MappingProxyType({
    "ingredients": (
        # English
        "ingredients", "ingredient list", "contains", "ingredients:", "ingredients :",
        "list of ingredients", "ingredient", "composition",
        # French
        "ingrédients", "liste des ingrédients", "composition",
        # German
        "zutaten", "zutatenliste", "inhaltsstoffe",
        # Spanish
        "ingredientes", "lista de ingredientes",
        # Italian
        "ingredienti", "lista degli ingredienti",
        # Portuguese
        "ingredientes", "lista de ingredientes",
        # Dutch
        "ingrediënten", "ingredienten",
        # Hindi (transliterated)
        "samagri", "samashti",
    ),
    "nutrition": (
        # English
        "nutrition", "nutrition facts", "nutritional information", "nutritional info",
        "nutrition:", "nutrition facts:", "nutritional values", "nutrient content",
        "nutritional composition", "per 100g", "per serving", "typical values",
        # French
        "informations nutritionnelles", "valeur nutritive", "par 100g",
        # German
        "nährwertangaben", "nährwerte", "durchschnittliche nährwerte",
        # Spanish
        "información nutricional", "valor nutricional", "por 100g",
        # Italian
        "informazioni nutrizionali", "valori nutrizionali", "per 100g",
        # Portuguese
        "informação nutricional", "valores nutricionais", "por 100g",
        # Dutch
        "voedingswaarden", "voedingsinformatie", "per 100g",
    ),
    "claims": (
        # English
        "high protein", "low fat", "sugar free", "no added sugar",
        "gluten free", "organic", "natural", "vegan", "vegetarian",
        "keto", "paleo", "diet", "zero sugar", "lite", "light",
        "reduced fat", "fat free", "100% natural",
        # French
        "riche en protéines", "faible en matières grasses", "sans sucre",
        "sans gluten", "biologique", "naturel", "végétalien", "végétarien",
        # German
        "eiweißreich", "fettarm", "zuckerfrei", "glutenfrei",
        "bio", "natürlich", "vegan", "vegetarisch",
        # Spanish
        "alto en proteínas", "bajo en grasa", "sin azúcar",
        "sin gluten", "orgánico", "natural", "vegano", "vegetariano",
    ),
    "warnings": (
        # English
        "warning", "caution", "allergen", "allergy", "contains",
        "may contain", "manufactured in facility", "processed in",
        "best before", "expiry",
        # French
        "avertissement", "attention", "allergène", "allergie", "contient",
        "peut contenir", "à consommer de préférence avant",
        # German
        "warnung", "vorsicht", "allergen", "allergie", "enthält",
        "kann enthalten", "mindestens haltbar bis",
        # Spanish
        "advertencia", "precaución", "alérgeno", "alergia", "contiene",
        "puede contener", "consumir preferentemente antes",
    ),
    "allergens": (
        # English
        "allergen", "allergy advice", "contains", "may contain traces",
        "allergen information", "allergy information",
        # French
        "allergène", "conseil allergie", "contient", "peut contenir des traces",
        # German
        "allergen", "allergiehinweis", "enthält", "kann spuren enthalten",
        # Spanish
        "alérgeno", "consejo sobre alergias", "contiene", "puede contener trazas",
    ),
})


# ==========================================================
# SECTION KEYWORDS (Legacy - kept for backward compatibility)
# ==========================================================

SECTION_KEYWORDS: Mapping[str, Tuple[str, ...]] = MappingProxyType({
    "ingredients": SECTION_KEYWORDS_MULTI["ingredients"],
    "nutrition": SECTION_KEYWORDS_MULTI["nutrition"],
    "claims": SECTION_KEYWORDS_MULTI["claims"],
    "warnings": SECTION_KEYWORDS_MULTI["warnings"],
    "allergens": SECTION_KEYWORDS_MULTI["allergens"],
})


# ==========================================================
# REGEX PATTERNS (Compiled for performance)
# ==========================================================

E_NUMBER_PATTERN: re.Pattern = re.compile(r"(?:E|e|INS)\s*(\d{3,4}[A-Za-z]?)")
BARCODE_PATTERN: re.Pattern = re.compile(r"^\d{8,14}$")

INGREDIENT_SECTION_PATTERN: re.Pattern = re.compile(
    r"(?:ingredients|ingredient list|contains|ingrédients|zutaten|ingredientes|ingredienti)[\s:]*?(.+?)(?=\n\s*(?:nutrition|nutritional|per 100g|allergen|fssai|manufacturer|nährwertangaben|información nutricional|informazioni nutrizionali|$))",
    re.IGNORECASE | re.DOTALL,
)

NUTRITION_SECTION_PATTERN: re.Pattern = re.compile(
    r"(?:nutrition|nutrition facts|nutritional information|nährwertangaben|información nutricional|informazioni nutrizionali)[\s:]*?(.+?)(?=\n\s*(?:ingredients|allergen|fssai|manufacturer|zutaten|ingredientes|$))",
    re.IGNORECASE | re.DOTALL,
)

ENERGY_PATTERN: re.Pattern = re.compile(
    r"(?:energy|energy value|energy kcal|calories|kcal)[^0-9]{0,40}(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)

PROTEIN_PATTERN: re.Pattern = re.compile(
    r"(?:protein|proteins)[^0-9]{0,40}(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)

FAT_PATTERN: re.Pattern = re.compile(
    r"(?:total fat|fat)[^0-9]{0,40}(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)

CARBS_PATTERN: re.Pattern = re.compile(
    r"(?:carbohydrates|carbohydrate|carbs|total carbohydrate)[^0-9]{0,40}(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)

SUGAR_PATTERN: re.Pattern = re.compile(
    r"(?:sugars|sugar|total sugars|added sugars)[^0-9]{0,40}(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)

FIBER_PATTERN: re.Pattern = re.compile(
    r"(?:fiber|fibre|dietary fibre|dietary fiber)[^0-9]{0,40}(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)

SALT_PATTERN: re.Pattern = re.compile(
    r"(?:salt)[^0-9]{0,40}(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)

SODIUM_PATTERN: re.Pattern = re.compile(
    r"(?:sodium)[^0-9]{0,40}(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)


# ==========================================================
# NUTRITION FIELD PATTERNS (Ordered for priority matching)
# ==========================================================

NUTRITION_PATTERNS: Mapping[str, re.Pattern] = MappingProxyType({
    "energy": ENERGY_PATTERN,
    "protein": PROTEIN_PATTERN,
    "fat": FAT_PATTERN,
    "carbohydrates": CARBS_PATTERN,
    "sugars": SUGAR_PATTERN,
    "fiber": FIBER_PATTERN,
    "salt": SALT_PATTERN,
    "sodium": SODIUM_PATTERN,
})


# ==========================================================
# PACKAGE TYPE KEYWORDS (Complete mapping)
# ==========================================================
# Note: Maintains 1:1 alignment with PackageType enum in schemas.py

PACKAGE_TYPE_KEYWORDS: Mapping[str, Tuple[str, ...]] = MappingProxyType({
    "bottle": ("bottle", "pet bottle", "glass bottle", "plastic bottle", "drink bottle"),
    "can": ("can", "tin", "aluminum can", "steel can", "soda can"),
    "jar": ("jar", "glass jar", "plastic jar", "screw top jar"),
    "box": ("box", "carton", "cardboard box", "paper box", "tetra pack", "tetrapak"),
    "pouch": ("pouch", "standup pouch", "pillow pouch", "flat pouch", "recyclable pouch"),
    "packet": ("packet", "sachet", "wrapper", "foil packet", "plastic packet"),
    "tub": ("tub", "container", "plastic tub", "round tub", "ice cream tub"),
    "bag": ("bag", "plastic bag", "paper bag", "poly bag"),
    "tray": ("tray", "plastic tray", "foam tray"),
    "cup": ("cup", "plastic cup", "paper cup", "yogurt cup"),
})


# ==========================================================
# BARCODE PREFIXES
# ==========================================================
# Note: GS1 prefix indicates registration country, not manufacturing origin.
# This is used for market detection only, not as definitive country of origin.

BARCODE_REGION_PREFIXES: Mapping[str, str] = MappingProxyType({
    # India
    "890": "India", "891": "India", "892": "India",
    
    # USA/Canada
    "000": "USA/Canada", "001": "USA/Canada", "002": "USA/Canada", "003": "USA/Canada",
    "004": "USA/Canada", "005": "USA/Canada", "006": "USA/Canada", "007": "USA/Canada",
    "008": "USA/Canada", "009": "USA/Canada", "030": "USA/Canada", "031": "USA/Canada",
    "032": "USA/Canada", "033": "USA/Canada", "034": "USA/Canada", "035": "USA/Canada",
    "036": "USA/Canada", "037": "USA/Canada", "038": "USA/Canada", "039": "USA/Canada",
    
    # Bulgaria
    "380": "Bulgaria",
    
    # Germany
    "400": "Germany", "401": "Germany", "402": "Germany", "403": "Germany", "404": "Germany",
    "405": "Germany", "406": "Germany", "407": "Germany", "408": "Germany", "409": "Germany",
    "410": "Germany", "411": "Germany", "412": "Germany", "413": "Germany", "414": "Germany",
    "415": "Germany", "416": "Germany", "417": "Germany", "418": "Germany", "419": "Germany",
    "420": "Germany", "421": "Germany", "422": "Germany", "423": "Germany", "424": "Germany",
    "425": "Germany", "426": "Germany", "427": "Germany", "428": "Germany", "429": "Germany",
    "430": "Germany", "431": "Germany", "432": "Germany", "433": "Germany", "434": "Germany",
    "435": "Germany", "436": "Germany", "437": "Germany", "438": "Germany", "439": "Germany",
    "440": "Germany",
    
    # Japan
    "450": "Japan", "451": "Japan", "452": "Japan", "453": "Japan", "454": "Japan",
    "455": "Japan", "456": "Japan", "457": "Japan", "458": "Japan", "459": "Japan",
    
    # Russia
    "460": "Russia", "461": "Russia", "462": "Russia", "463": "Russia", "464": "Russia",
    "465": "Russia", "466": "Russia", "467": "Russia", "468": "Russia", "469": "Russia",
    
    # United Kingdom
    "500": "United Kingdom", "501": "United Kingdom", "502": "United Kingdom", "503": "United Kingdom",
    "504": "United Kingdom", "505": "United Kingdom", "506": "United Kingdom", "507": "United Kingdom",
    "508": "United Kingdom", "509": "United Kingdom",
    
    # China
    "690": "China", "691": "China", "692": "China", "693": "China", "694": "China",
    "695": "China", "696": "China", "697": "China", "698": "China", "699": "China",
    
    # Italy
    "800": "Italy", "801": "Italy", "802": "Italy", "803": "Italy", "804": "Italy",
    "805": "Italy", "806": "Italy", "807": "Italy", "808": "Italy", "809": "Italy",
    
    # Spain
    "840": "Spain", "841": "Spain", "842": "Spain", "843": "Spain", "844": "Spain",
    "845": "Spain", "846": "Spain", "847": "Spain", "848": "Spain", "849": "Spain",
    
    # Australia
    "930": "Australia", "931": "Australia", "932": "Australia", "933": "Australia", "934": "Australia",
    "935": "Australia", "936": "Australia", "937": "Australia", "938": "Australia", "939": "Australia",
})


# ==========================================================
# ALLERGEN KEYWORDS
# ==========================================================

ALLERGEN_KEYWORDS: Tuple[str, ...] = (
    "milk", "dairy", "lactose", "casein", "whey",
    "soy", "soybean", "tofu", "edamame",
    "peanut", "peanuts", "groundnut", "monkey nut",
    "tree nuts", "almond", "cashew", "walnut", "pecan",
    "hazelnut", "pistachio", "macadamia",
    "wheat", "gluten", "barley", "rye", "oats", "spelt",
    "egg", "eggs", "albumin", "mayonnaise",
    "fish", "seafood", "shellfish", "shrimp", "prawn",
    "crab", "lobster", "mollusk",
    "sesame", "sesame seed", "til",
    "mustard", "mustard seed",
    "celery", "celery seed",
    "lupin", "lupine",
    "sulphite", "sulfur dioxide", "sulphur dioxide",
    "corn", "maize",
)


# ==========================================================
# PRODUCT NAME BLACKLIST
# ==========================================================

PRODUCT_NAME_BLACKLIST: frozenset[str] = frozenset([
    "ingredients", "ingredient", "nutrition", "nutrition facts",
    "nutritional information", "energy", "protein", "fat",
    "carbohydrate", "sugar", "sodium", "salt", "fiber",
    "contains", "fssai", "manufactured", "manufacturer",
    "consumer care", "customer care", "new", "extra", "free",
    "offer", "vegetarian", "veg", "non vegetarian", "non-veg",
    "premium", "quality", "best", "save", "more", "buy", "get",
    "only", "just", "net weight", "weight", "mrp", "price",
    "batch", "best before", "expiry", "store in cool", "keep",
    "refrigerate", "serving", "per 100g", "per serving",
    "allergen", "allergy", "warning", "caution", "imported",
    "exported", "distributed", "marketed by", "packed by",
    "for", "contact", "customer", "feedback", "review",
    "nutritionist", "dietitian", "healthy", "organic",
    "natural", "pure", "fresh", "gluten free", "sugar free",
    "low fat", "high protein", "no added sugar", "keto",
])


# ==========================================================
# TRUST BADGE LEVELS
# ==========================================================

TRUST_BADGE_LEVELS: Mapping[str, Tuple[int, int]] = MappingProxyType({
    "gold": (90, 100),
    "silver": (75, 89),
    "bronze": (60, 74),
    "none": (0, 59),
})


# ==========================================================
# SCAN JOURNEY STEPS
# ==========================================================

SCAN_JOURNEY_STEPS: Tuple[str, ...] = (
    "Image Uploaded",
    "Image Quality Check",
    "Barcode Detection",
    "OCR Extraction",
    "OpenFoodFacts Lookup",
    "Product Fusion",
    "Verification Complete",
)


# ==========================================================
# EVIDENCE SOURCES
# ==========================================================

EVIDENCE_SOURCES: Mapping[str, str] = MappingProxyType({
    "barcode": "Product barcode detected and validated",
    "ocr": "Product text extracted from label image",
    "openfoodfacts": "Product matched in global food database",
    "product_fusion": "Multi-source data merged successfully",
    "image_quality": "Image quality meets scanning standards",
    "verification": "Cross-verification completed",
})


# ==========================================================
# API LIMITS
# ==========================================================

MAX_PRODUCT_NAME_LENGTH: int = 300
MAX_BRAND_NAME_LENGTH: int = 200
MAX_INGREDIENT_LENGTH: int = 5000


# ==========================================================
# OCR TEXT LENGTH LIMITS
# ==========================================================
# Note: These limits accommodate multi-language labels with
# ingredients, nutrition tables, and marketing text.
# Typically sufficient for 95%+ of food products.

MAX_EXTRACTED_TEXT_LENGTH: int = 10000
MAX_RAW_TEXT_LENGTH: int = 20000


# ==========================================================
# NUTRITION VALIDATION LIMITS (Expanded for high-fat products)
# ==========================================================
# Note: Calories increased to 1500 to accommodate:
# - Cooking oils (884 kcal/100g)
# - Ghee (900 kcal/100g)
# - Butter (717 kcal/100g)
# - Nuts and seeds (600-700 kcal/100g)

NUTRITION_VALIDATION_LIMITS: Mapping[str, Tuple[float, float]] = MappingProxyType({
    "calories": (0.0, 1500.0),
    "protein": (0.0, 100.0),
    "fat": (0.0, 100.0),
    "saturated_fat": (0.0, 50.0),
    "carbohydrates": (0.0, 100.0),
    "sugar": (0.0, 100.0),
    "fiber": (0.0, 50.0),
    "sodium": (0.0, 10000.0),
})


# ==========================================================
# SYSTEM IDENTIFIERS
# ==========================================================

SCAN_SYSTEM_NAME: str = "Scan Intelligence"
SCAN_SYSTEM_VERSION: str = "1.0"


# ==========================================================
# END OF FILE
# ==========================================================