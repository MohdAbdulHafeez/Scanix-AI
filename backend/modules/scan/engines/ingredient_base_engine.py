# ==========================================================
# SCANIX AI
# SYSTEM 1 - INGREDIENT BASE ENGINE
# Advanced ingredient analysis for System 1
# Features: Pre-compiled regex, Schema-strict mapping, Fuzzy matching
# Parenthetical preservation, E-number classification, Contextual allergen detection
# ==========================================================


import re
from types import MappingProxyType
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Set
from typing import Tuple

from rapidfuzz import fuzz

from core.logging import get_logger

from modules.scan.constants import ALLERGEN_KEYWORDS
from modules.scan.constants import E_NUMBER_PATTERN
from modules.scan.constants import INGREDIENT_SECTION_PATTERN


logger = get_logger(__name__)


# ==========================================================
# PRE-COMPILED HEURISTIC MAPPINGS
# ==========================================================


# E-Number to Name Mapping
E_NUMBER_NAMES = MappingProxyType({
    "E100": "Curcumin (Turmeric)",
    "E101": "Riboflavin (Vitamin B2)",
    "E102": "Tartrazine",
    "E104": "Quinoline Yellow",
    "E110": "Sunset Yellow FCF",
    "E120": "Cochineal / Carminic Acid",
    "E122": "Azorubine / Carmoisine",
    "E124": "Ponceau 4R",
    "E129": "Allura Red AC",
    "E133": "Brilliant Blue FCF",
    "E150": "Caramel Color",
    "E150a": "Plain Caramel",
    "E150b": "Caustic Sulfite Caramel",
    "E150c": "Ammonia Caramel",
    "E150d": "Sulfite Ammonia Caramel",
    "E153": "Vegetable Carbon",
    "E160a": "Carotenes",
    "E160b": "Annatto",
    "E160c": "Paprika Extract",
    "E160d": "Lycopene",
    "E161b": "Lutein",
    "E162": "Beetroot Red",
    "E163": "Anthocyanins",
    "E170": "Calcium Carbonate",
    "E171": "Titanium Dioxide",
    "E172": "Iron Oxides",
    "E200": "Sorbic Acid",
    "E202": "Potassium Sorbate",
    "E210": "Benzoic Acid",
    "E211": "Sodium Benzoate",
    "E212": "Potassium Benzoate",
    "E220": "Sulfur Dioxide",
    "E221": "Sodium Sulfite",
    "E222": "Sodium Bisulfite",
    "E223": "Sodium Metabisulfite",
    "E224": "Potassium Metabisulfite",
    "E250": "Sodium Nitrite",
    "E251": "Sodium Nitrate",
    "E252": "Potassium Nitrate",
    "E270": "Lactic Acid",
    "E296": "Malic Acid",
    "E300": "Ascorbic Acid (Vitamin C)",
    "E301": "Sodium Ascorbate",
    "E302": "Calcium Ascorbate",
    "E304": "Fatty Acid Esters of Ascorbic Acid",
    "E306": "Tocopherols (Vitamin E)",
    "E307": "Alpha-Tocopherol",
    "E308": "Gamma-Tocopherol",
    "E309": "Delta-Tocopherol",
    "E320": "Butylated Hydroxyanisole (BHA)",
    "E321": "Butylated Hydroxytoluene (BHT)",
    "E322": "Lecithin",
    "E325": "Sodium Lactate",
    "E326": "Potassium Lactate",
    "E327": "Calcium Lactate",
    "E330": "Citric Acid",
    "E331": "Sodium Citrate",
    "E332": "Potassium Citrate",
    "E333": "Calcium Citrate",
    "E334": "Tartaric Acid",
    "E335": "Sodium Tartrate",
    "E336": "Potassium Tartrate",
    "E337": "Sodium Potassium Tartrate",
    "E338": "Phosphoric Acid",
    "E339": "Sodium Phosphates",
    "E340": "Potassium Phosphates",
    "E341": "Calcium Phosphates",
    "E350": "Sodium Malate",
    "E351": "Potassium Malate",
    "E352": "Calcium Malate",
    "E353": "Metatartaric Acid",
    "E354": "Calcium Tartrate",
    "E355": "Adipic Acid",
    "E356": "Sodium Adipate",
    "E357": "Potassium Adipate",
    "E363": "Succinic Acid",
    "E370": "1,4-Heptonolactone",
    "E375": "Niacin (Nicotinic Acid)",
    "E380": "Triammonium Citrate",
    "E385": "Calcium Disodium EDTA",
    "E392": "Rosemary Extract",
    "E400": "Alginic Acid",
    "E401": "Sodium Alginate",
    "E402": "Potassium Alginate",
    "E403": "Ammonium Alginate",
    "E404": "Calcium Alginate",
    "E405": "Propane-1,2-Diol Alginate",
    "E406": "Agar",
    "E407": "Carrageenan",
    "E410": "Locust Bean Gum",
    "E412": "Guar Gum",
    "E414": "Gum Arabic",
    "E415": "Xanthan Gum",
    "E416": "Karaya Gum",
    "E417": "Tara Gum",
    "E418": "Gellan Gum",
    "E420": "Sorbitol",
    "E421": "Mannitol",
    "E422": "Glycerol",
    "E431": "Polyoxyethylene (40) Stearate",
    "E432": "Polysorbate 20",
    "E433": "Polysorbate 80",
    "E434": "Polysorbate 40",
    "E435": "Polysorbate 60",
    "E436": "Polysorbate 65",
    "E440": "Pectin",
    "E460": "Cellulose",
    "E461": "Methyl Cellulose",
    "E462": "Ethyl Cellulose",
    "E463": "Hydroxypropyl Cellulose",
    "E464": "Hydroxypropyl Methyl Cellulose",
    "E465": "Ethyl Methyl Cellulose",
    "E466": "Carboxymethyl Cellulose",
    "E470": "Magnesium Salts of Fatty Acids",
    "E471": "Mono- and Diglycerides of Fatty Acids",
    "E472": "Esters of Mono- and Diglycerides",
    "E473": "Sucrose Esters of Fatty Acids",
    "E474": "Sucroglycerides",
    "E475": "Polyglycerol Esters of Fatty Acids",
    "E476": "Polyglycerol Polyricinoleate (PGPR)",
    "E477": "Propylene Glycol Esters",
    "E479": "Thermally Oxidized Soybean Oil",
    "E481": "Sodium Stearoyl Lactylate",
    "E482": "Calcium Stearoyl Lactylate",
    "E483": "Stearyl Tartrate",
    "E491": "Sorbitan Monostearate",
    "E492": "Sorbitan Tristearate",
    "E493": "Sorbitan Monolaurate",
    "E494": "Sorbitan Monooleate",
    "E495": "Sorbitan Monopalmitate",
    "E500": "Sodium Carbonates",
    "E501": "Potassium Carbonates",
    "E503": "Ammonium Carbonates",
    "E504": "Magnesium Carbonates",
    "E507": "Hydrochloric Acid",
    "E508": "Potassium Chloride",
    "E509": "Calcium Chloride",
    "E510": "Ammonium Chloride",
    "E511": "Magnesium Chloride",
    "E512": "Stannous Chloride",
    "E513": "Sulfuric Acid",
    "E514": "Sodium Sulfates",
    "E515": "Potassium Sulfates",
    "E516": "Calcium Sulfate",
    "E517": "Ammonium Sulfate",
    "E520": "Aluminum Sulfate",
    "E521": "Aluminum Sodium Sulfate",
    "E522": "Aluminum Potassium Sulfate",
    "E523": "Aluminum Ammonium Sulfate",
    "E524": "Sodium Hydroxide",
    "E525": "Potassium Hydroxide",
    "E526": "Calcium Hydroxide",
    "E527": "Ammonium Hydroxide",
    "E528": "Magnesium Hydroxide",
    "E529": "Calcium Oxide",
    "E530": "Magnesium Oxide",
    "E535": "Sodium Ferrocyanide",
    "E536": "Potassium Ferrocyanide",
    "E538": "Calcium Ferrocyanide",
    "E541": "Sodium Aluminum Phosphate",
    "E551": "Silicon Dioxide",
    "E552": "Calcium Silicate",
    "E553": "Magnesium Silicate",
    "E554": "Sodium Aluminosilicate",
    "E555": "Potassium Aluminosilicate",
    "E556": "Calcium Aluminosilicate",
    "E559": "Aluminum Silicate",
    "E570": "Fatty Acids",
    "E572": "Magnesium Stearate",
    "E574": "Gluconic Acid",
    "E575": "Glucono Delta-Lactone (GDL)",
    "E576": "Sodium Gluconate",
    "E577": "Potassium Gluconate",
    "E578": "Calcium Gluconate",
    "E579": "Ferrous Gluconate",
    "E585": "Ferrous Lactate",
    "E620": "Glutamic Acid",
    "E621": "Monosodium Glutamate (MSG)",
    "E622": "Monopotassium Glutamate",
    "E623": "Calcium Diglutamate",
    "E624": "Monoammonium Glutamate",
    "E625": "Magnesium Diglutamate",
    "E626": "Guanylic Acid",
    "E627": "Disodium Guanylate",
    "E628": "Dipotassium Guanylate",
    "E629": "Calcium Guanylate",
    "E630": "Inosinic Acid",
    "E631": "Disodium Inosinate",
    "E632": "Dipotassium Inosinate",
    "E633": "Calcium Inosinate",
    "E634": "Calcium Ribonucleotides",
    "E635": "Disodium Ribonucleotides",
    "E636": "Maltol",
    "E637": "Ethyl Maltol",
    "E640": "Glycine",
    "E641": "L-Leucine",
    "E642": "Lysine",
    "E650": "Zinc Acetate",
    "E900": "Dimethyl Polysiloxane",
    "E901": "Beeswax",
    "E902": "Candelilla Wax",
    "E903": "Carnauba Wax",
    "E904": "Shellac",
    "E905": "Microcrystalline Wax",
    "E907": "Refined Microcrystalline Wax",
    "E912": "Montan Acid Esters",
    "E913": "Lanolin",
    "E914": "Oxidized Polyethylene Wax",
    "E920": "L-Cysteine",
    "E921": "L-Cystine",
    "E925": "Chlorine",
    "E926": "Chlorine Dioxide",
    "E927": "Azodicarbonamide",
    "E928": "Benzoyl Peroxide",
    "E950": "Acesulfame K",
    "E951": "Aspartame",
    "E952": "Cyclamic Acid",
    "E953": "Isomalt",
    "E954": "Saccharin",
    "E955": "Sucralose",
    "E957": "Thaumatin",
    "E959": "Neohesperidine DC",
    "E960": "Steviol Glycosides (Stevia)",
    "E961": "Neotame",
    "E962": "Salt of Aspartame-Acesulfame",
    "E965": "Maltitol",
    "E966": "Lactitol",
    "E967": "Xylitol",
    "E968": "Erythritol",
    "E999": "Quillaia Extract",
    "E1200": "Polydextrose",
    "E1201": "Polyvinylpyrrolidone",
    "E1202": "Polyvinylpolypyrrolidone",
    "E1400": "Dextrin",
    "E1401": "Modified Starch",
    "E1404": "Oxidized Starch",
    "E1410": "Monostarch Phosphate",
    "E1412": "Distarch Phosphate",
    "E1413": "Phosphated Distarch Phosphate",
    "E1414": "Acetylated Distarch Phosphate",
    "E1420": "Acetylated Starch",
    "E1422": "Acetylated Distarch Adipate",
    "E1440": "Hydroxypropyl Starch",
    "E1442": "Hydroxypropyl Distarch Phosphate",
    "E1450": "Starch Sodium Octenylsuccinate",
    "E1505": "Triethyl Citrate",
    "E1518": "Glyceryl Triacetate",
    "E1520": "Propylene Glycol",
})

# E-Number Risk Classification
E_NUMBER_RISKS = MappingProxyType({
    "E102": "high",
    "E104": "high",
    "E110": "high",
    "E120": "medium",
    "E122": "high",
    "E124": "high",
    "E129": "high",
    "E211": "medium",
    "E220": "high",
    "E221": "high",
    "E222": "high",
    "E223": "high",
    "E224": "high",
    "E250": "high",
    "E251": "high",
    "E252": "high",
    "E320": "medium",
    "E321": "medium",
    "E407": "medium",
    "E412": "low",
    "E415": "low",
    "E420": "low",
    "E421": "low",
    "E422": "low",
    "E440": "low",
    "E460": "low",
    "E461": "low",
    "E466": "low",
    "E471": "low",
    "E472": "low",
    "E473": "low",
    "E474": "low",
    "E475": "low",
    "E476": "medium",
    "E481": "low",
    "E482": "low",
    "E500": "low",
    "E501": "low",
    "E503": "low",
    "E504": "low",
    "E508": "low",
    "E509": "low",
    "E950": "medium",
    "E951": "medium",
    "E952": "medium",
    "E954": "medium",
    "E955": "low",
    "E957": "low",
    "E960": "low",
    "E961": "low",
    "E962": "medium",
    "E965": "low",
    "E966": "low",
    "E967": "low",
    "E968": "low",
})

# Fuzzy matching threshold for ingredient section detection
INGREDIENT_SECTION_THRESHOLD = 85
INGREDIENT_VARIANTS = ["ingredients", "ingredient", "ingredlents", "ingrediants", "ingredientes", "ingrédients"]


def _compile_heuristics(source_dict: Dict[str, str]) -> Tuple[Tuple[re.Pattern, str, str], ...]:
    
    compiled = []
    
    for keyword, value in source_dict.items():
        
        pattern = re.compile(rf"\b{re.escape(keyword)}\b", re.IGNORECASE)
        
        compiled.append((pattern, value, keyword))
        
    return tuple(compiled)


POSITIVE_INGREDIENTS = _compile_heuristics({
    "protein": "Contains Protein",
    "fiber": "Contains Fiber",
    "whole grain": "Whole Grain",
    "milk": "Dairy Source",
    "oats": "Oats",
    "almond": "Almonds",
    "peanut": "Peanuts",
    "whey": "Whey Protein",
    "soy protein": "Soy Protein",
    "plant protein": "Plant Protein",
    "lentils": "Lentils",
    "chickpeas": "Chickpeas",
    "millets": "Millets",
    "quinoa": "Quinoa",
    "brown rice": "Brown Rice",
    "flaxseed": "Flaxseed",
    "chia seed": "Chia Seeds",
    "pea protein": "Pea Protein",
})


NEGATIVE_INGREDIENTS = _compile_heuristics({
    "maltodextrin": "Highly Processed Additive",
    "artificial flavor": "Artificial Flavoring",
    "artificial flavour": "Artificial Flavoring",
    "artificial color": "Artificial Coloring",
    "artificial colour": "Artificial Coloring",
    "hydrogenated": "Processed Fat",
    "palm oil": "Palm Oil",
    "palmolein": "Palm Oil",
    "high fructose corn syrup": "High Fructose Corn Syrup",
    "hfcs": "High Fructose Corn Syrup",
    "sucralose": "Artificial Sweetener",
    "acesulfame k": "Artificial Sweetener",
    "aspartame": "Artificial Sweetener",
    "sodium benzoate": "Artificial Preservative",
    "potassium sorbate": "Artificial Preservative",
    "monosodium glutamate": "MSG",
    "msg": "MSG",
    "artificial sweetener": "Artificial Sweetener",
    "artificial preservative": "Artificial Preservative",
    "modified starch": "Modified Starch",
    "carrageenan": "Thickener/Preservative",
})


PROCESSING_INDICATORS = _compile_heuristics({
    "maltodextrin": "high",
    "modified starch": "high",
    "hydrogenated": "high",
    "artificial flavor": "high",
    "artificial flavour": "high",
    "artificial color": "high",
    "artificial colour": "high",
    "emulsifier": "high",
    "stabilizer": "high",
    "preservative": "high",
    "sweetener": "high",
    "palm oil": "medium",
    "palmolein": "medium",
    "sugar": "medium",
    "salt": "medium",
})


# Contextual allergen detection patterns
ALLERGEN_CONTEXT_PATTERNS = [
    re.compile(r"contains\s*:?\s*([^.]+)", re.IGNORECASE),
    re.compile(r"may contain\s*:?\s*([^.]+)", re.IGNORECASE),
    re.compile(r"processed in a facility that also processes\s*:?\s*([^.]+)", re.IGNORECASE),
    re.compile(r"manufactured on equipment that also processes\s*:?\s*([^.]+)", re.IGNORECASE),
    re.compile(r"allergen information\s*:?\s*([^.]+)", re.IGNORECASE),
    re.compile(r"contains milk|soy|wheat|eggs|nuts|peanuts|fish|shellfish", re.IGNORECASE),
]

# Pre-compile allergens from constants
ALLERGEN_PATTERNS = tuple((re.compile(rf"\b{re.escape(a)}\b", re.IGNORECASE), a) for a in ALLERGEN_KEYWORDS)


class IngredientBaseEngine:
    
    def _extract_ingredient_section(self, text: str) -> Optional[str]:
        
        if not text:
            
            return None
        
        # Try exact pattern first
        match = INGREDIENT_SECTION_PATTERN.search(text)
        
        if match:
            
            return match.group(1).strip()
        
        # Fuzzy matching fallback for OCR errors
        lines = text.split('\n')
        
        for i, line in enumerate(lines[:20]):  # Check first 20 lines
            line_lower = line.lower().strip()
            
            for variant in INGREDIENT_VARIANTS:
                score = fuzz.partial_ratio(variant, line_lower)
                
                if score >= INGREDIENT_SECTION_THRESHOLD:
                    # Found ingredient section with fuzzy match
                    ingredient_lines = []
                    for j in range(i + 1, min(i + 30, len(lines))):
                        if len(lines[j].strip()) < 2:
                            continue
                        # Stop at next section marker
                        if re.match(r'^[A-Z\s]{5,}$', lines[j]) and len(lines[j]) < 30:
                            break
                        ingredient_lines.append(lines[j])
                    
                    if ingredient_lines:
                        logger.debug(f"Found ingredient section via fuzzy match: {variant} (score={score})")
                        return "\n".join(ingredient_lines)
        
        return None
    
    
    def _preserve_parenthetical_groups(self, ingredient_text: str) -> List[str]:
        """
        Intelligently split ingredients while preserving parenthetical groups.
        Example: "Vegetable Oils (Sunflower Oil, Palm Oil)" remains as one ingredient.
        """
        if not ingredient_text:
            return []
        
        # First, protect parenthetical groups by replacing them with placeholders
        parentheses_content = []
        
        def replace_parenthesis(match):
            parentheses_content.append(match.group(0))
            return f"__PAREN_{len(parentheses_content) - 1}__"
        
        protected_text = re.sub(r'\([^)]*\)', replace_parenthesis, ingredient_text)
        
        # Split by commas, semicolons, or newlines
        raw_ingredients = re.split(r'[,;\\n]', protected_text)
        
        # Restore parenthetical groups
        restored_ingredients = []
        
        for ing in raw_ingredients:
            ing = ing.strip()
            if not ing:
                continue
            
            # Restore parentheses
            for i, content in enumerate(parentheses_content):
                ing = ing.replace(f"__PAREN_{i}__", content)
            
            restored_ingredients.append(ing)
        
        return restored_ingredients
    
    
    def _clean_ingredient(self, ingredient: str) -> str:
        
        # Remove parentheses content only if it's excessive (nested processing)
        # But keep the main ingredient name
        
        # Remove common prefixes (numbers, dashes, etc.)
        ingredient = re.sub(r'^[\d\s\(\)\-\.:]+', '', ingredient)
        
        # Strip common punctuation
        ingredient = ingredient.strip(" .:-;,()")
        
        # Remove multiple spaces
        ingredient = re.sub(r'\s+', ' ', ingredient)
        
        return ingredient
    
    
    def extract_ingredients(self, text: str) -> List[str]:
        
        if not text:
            
            return []
        
        ingredient_section = self._extract_ingredient_section(text)
        
        if not ingredient_section:
            
            return []
        
        # Clean the ingredient section
        ingredient_section = re.sub(r'\s+', ' ', ingredient_section)
        
        # Use parenthetical-preserving split
        ingredients = self._preserve_parenthetical_groups(ingredient_section)
        
        cleaned = []
        
        seen: Set[str] = set()
        
        for ingredient in ingredients:
            
            ingredient = ingredient.strip().lower()
            
            if not ingredient or len(ingredient) < 2:
                
                continue
            
            ingredient = self._clean_ingredient(ingredient)
            
            if not ingredient:
                
                continue
            
            if ingredient not in seen:
                
                seen.add(ingredient)
                
                cleaned.append(ingredient)
        
        return cleaned
    
    
    def extract_e_numbers(self, text: str) -> List[Dict[str, Any]]:
        
        if not text:
            
            return []
        
        # Find all E-numbers
        matches = E_NUMBER_PATTERN.findall(text)
        
        # Get unique matches
        unique_numbers = set()
        for match in matches:
            e_number = f"E{match.upper()}"
            unique_numbers.add(e_number)
        
        # Classify each E-number
        classified = []
        for e_number in sorted(unique_numbers):
            name = E_NUMBER_NAMES.get(e_number, "Unknown Additive")
            risk = E_NUMBER_RISKS.get(e_number, "unknown")
            
            classified.append({
                "code": e_number,
                "name": name,
                "risk_level": risk,
            })
        
        return classified
    
    
    def detect_basic_allergens(self, text: str) -> List[str]:
        
        if not text:
            
            return []
        
        detected = set()
        
        # Exact matching for allergen keywords
        for pattern, allergen in ALLERGEN_PATTERNS:
            
            if pattern.search(text):
                
                detected.add(allergen)
        
        # Contextual detection for "contains" statements
        for pattern in ALLERGEN_CONTEXT_PATTERNS:
            matches = pattern.finditer(text)
            for match in matches:
                context_text = match.group(1) if match.lastindex else match.group(0)
                context_lower = context_text.lower()
                
                for allergen in ALLERGEN_KEYWORDS:
                    if allergen.lower() in context_lower:
                        detected.add(allergen)
        
        return list(detected)
    
    
    def detect_positive_ingredients(self, text: str) -> List[Dict[str, Any]]:
        
        if not text:
            
            return []
        
        positives = []
        
        for pattern, title, keyword in POSITIVE_INGREDIENTS:
            
            if pattern.search(text):
                
                positives.append({
                    "title": title,
                    "ingredient": keyword,
                    "type": "positive",
                })
        
        return positives
    
    
    def detect_negative_ingredients(self, text: str) -> List[Dict[str, Any]]:
        
        if not text:
            
            return []
        
        negatives = []
        
        for pattern, title, keyword in NEGATIVE_INGREDIENTS:
            
            if pattern.search(text):
                
                negatives.append({
                    "title": title,
                    "ingredient": keyword,
                    "type": "negative",
                })
        
        return negatives
    
    
    def calculate_ingredient_visibility_score(
        self,
        text: str,
        has_ingredients_section: bool,
        ingredient_count: int,
        readability_score: int,
    ) -> int:
        
        if not text:
            
            return 0
        
        score = 0
        
        if has_ingredients_section:
            
            score += 40
        
        if ingredient_count > 15:
            
            score += 25
        
        elif ingredient_count > 8:
            
            score += 20
        
        elif ingredient_count > 3:
            
            score += 15
        
        elif ingredient_count > 0:
            
            score += 10
        
        score += min(20, int(readability_score / 5))
        
        e_numbers = self.extract_e_numbers(text)
        
        if len(e_numbers) == 0:
            
            score += 15
        
        elif len(e_numbers) < 3:
            
            score += 8
        
        else:
            
            score += 2
        
        return min(100, score)
    
    
    def estimate_processing_level(self, text: str) -> Tuple[str, List[str]]:
        
        if not text:
            
            return "UNKNOWN", []
        
        high_count = 0
        
        medium_count = 0
        
        indicators = []
        
        for pattern, level, keyword in PROCESSING_INDICATORS:
            
            if pattern.search(text):
                
                indicators.append(keyword)
                
                if level == "high":
                    
                    high_count += 1
                
                elif level == "medium":
                    
                    medium_count += 1
        
        # Check for emulsifiers, isolates, flavors systematically
        if re.search(r'\b(emulsifier|stabilizer|thickener|gum)\b', text, re.IGNORECASE):
            high_count += 1
            indicators.append("emulsifiers/stabilizers")
        
        if re.search(r'\b(isolate|concentrate|hydrolyzed)\b', text, re.IGNORECASE):
            high_count += 1
            indicators.append("protein isolates/concentrates")
        
        if re.search(r'\b(flavour|flavor|natural flavour)\b', text, re.IGNORECASE):
            medium_count += 1
            indicators.append("added flavors")
        
        if high_count >= 3 or (high_count >= 2 and medium_count >= 2):
            
            return "HIGH", indicators[:10]
        
        if high_count >= 1 or medium_count >= 3:
            
            return "MEDIUM", indicators[:10]
        
        if medium_count >= 1:
            
            return "LOW", indicators[:10]
        
        return "MINIMAL", indicators[:10]
    
    
    def generate_risk_preview(self, negatives: List[Dict], e_count: int, processing_level: str) -> List[str]:
        
        risks = []
        
        if e_count > 5:
            
            risks.append("Multiple additives detected")
        
        elif e_count > 2:
            
            risks.append("Contains additives")
        
        for neg in negatives[:3]:
            
            if "Artificial Sweetener" in neg["title"]:
                
                risks.append("Contains artificial sweetener")
            
            elif "Artificial Preservative" in neg["title"]:
                
                risks.append("Contains preservatives")
            
            elif "MSG" in neg["title"]:
                
                risks.append("Contains MSG")
            
            elif "Palm Oil" in neg["title"]:
                
                risks.append("Contains palm oil")
        
        if processing_level == "HIGH":
            
            risks.append("Highly processed ingredients")
        
        elif processing_level == "MEDIUM":
            
            risks.append("Moderately processed ingredients")
        
        if not risks:
            
            risks.append("No major risks detected")
        
        seen = set()
        
        unique_risks = []
        
        for risk in risks:
            
            if risk not in seen:
                
                seen.add(risk)
                
                unique_risks.append(risk)
        
        return unique_risks[:5]
    
    
    def analyze_basic(self, text: str, has_ingredients_section: bool, readability_score: int) -> Dict[str, Any]:
        
        if not text:
            
            return {
                "ingredients": [],
                "ingredient_count": 0,
                "e_numbers": [],
                "basic_allergens": [],
                "has_ingredients_section": False,
                "ingredient_visibility_score": 0,
            }
        
        raw_ingredients = self.extract_ingredients(text)
        
        ingredient_count = len(raw_ingredients)
        
        e_numbers = self.extract_e_numbers(text)
        
        basic_allergens = self.detect_basic_allergens(text)
        
        visibility_score = self.calculate_ingredient_visibility_score(
            text,
            has_ingredients_section,
            ingredient_count,
            readability_score,
        )
        
        # Map raw strings to IngredientItem schema strict format
        ingredient_items = [
            {"name": ing, "confidence": 1.0, "source": "ocr"} 
            for ing in raw_ingredients[:200]
        ]
        
        # Strict mapping to the 'IngredientSummary' schema in schemas.py
        return {
            "ingredients": ingredient_items,
            "ingredient_count": ingredient_count,
            "e_numbers": e_numbers[:50],
            "basic_allergens": basic_allergens[:50],
            "has_ingredients_section": has_ingredients_section,
            "ingredient_visibility_score": visibility_score,
        }


# ==========================================================
# SINGLETON
# ==========================================================


ingredient_base_engine = IngredientBaseEngine()


# ==========================================================
# END OF FILE
# ==========================================================