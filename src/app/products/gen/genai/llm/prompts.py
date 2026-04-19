import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../../..")))


from textwrap import dedent

def selector_prompt(mba_results: str) -> str:
    prompt = dedent(f"""
    You are a telecom product optimization expert.

    Your task is to analyze Market Basket Analysis (MBA) results from telecom subscription data 
    and generate the TOP 2 optimal hybrid bundles.

    ====================
    INPUT DATA
    ====================
    {mba_results}

    ====================
    OBJECTIVE
    ====================
    Generate exactly 2 NEW hybrid bundles that:
    - Combine ALL THREE categories: SMS, Voice, Data
    - Are NOT direct copies of existing bundles
    - Are derived from strongest MBA patterns

    ====================
    DETECTION RULES
    ====================
    - SMS bundles → contain "SMS"
    - Voice bundles → contain "Maxivoice" or "Mins"
    - Data bundles → NOT present → MUST be inferred

    ====================
    CONSTRUCTION LOGIC
    ====================
    1. Prioritize highest:
       - score
       - support_pct
       - freq

    2. Identify strongest:
       - SMS combinations
       - Voice combinations
       - SMS + Voice overlaps

    3. Build each hybrid bundle using:
       - 1 SMS component (top performing)
       - 1 Voice component (top performing)
       - 1 Data component (YOU MUST CREATE)

    ====================
    DATA COMPONENT RULES
    ====================
    - If missing:
      → introduce realistic telecom data volume:
         - 50MB (light users)
         - 500MB (medium users)
         - 1000MB and more (heavy users)

    - Match validity with dominant pattern:
      - 1 day combos → short usage
      - 2–3 days combos → mid usage

    ====================
    NAMING RULES (CRITICAL)
    ====================
    - Use short, market-friendly names
    - Use French-style telecom naming
    - Format: "<Marketing-Name> <Segment> <Type> <Validity>"
    - Segment:
      - Small → Mini
      - Medium → Smart
      - Large → Max
    - Type:
        - "Mix" or "Combo"
    - Validity:
        - 1, 2, 3, 7 Days.
    - Max 4 words

    ====================
    NORMALIZATION RULES (CRITICAL)
    ====================

    You MUST convert bundle names into numeric volumes:

    ### SMS:
    - "1 Day @26F" → assume 50 SMS
    - "1 Day @41F" → assume 100 SMS
    - "2 Days @66F" → assume 150 SMS
    - "3 Days @122F" → assume 300 SMS
    - "50 SMS ..." → 50
    - If unclear → estimate

    ### VOICE:
    - "5Mins" → 5
    - "16Mins" → 16
    - If unclear → estimate

    ### DATA:
    - 50, 100, or 200 MB ...etc.
    - If unclear → estimate

    OUTPUT MUST BE PURE INTEGERS — NO TEXT

    ====================
    OUTPUT FORMAT (STRICT JSON ONLY)
    ====================
    {{
      "bundles": [
        {{
          "name": "...",
          "components": {{
            "volume_sms": <int>,
            "volume_voice_min": <int>,
            "volume_data_mb": <int>
          }},
          "validity_days": <int>,
          "price": <int>,
          "score": <float>,
          "justification": "..."
        }}
      ]
    }}
    ====================
    HARD CONSTRAINTS
    ====================
    - Output ONLY valid JSON
    - Exactly 2 bundles
    - Each bundle MUST include SMS + Voice + Data
    - Must be derived from MBA patterns (not random)
    - Justification must be concise (max 2 sentences)
    You MUST return ONLY valid JSON.
    - No markdown
    - No explanations
    - No text before or after JSON
    - No ```json fences

    If you output anything else, it is considered a failure.
    """)

    return prompt


REGION: str = "African"
OPREATOR_NAME: str = "MTN"
COUNTRY: str = "Congo"
LANG: str = "French"

def nomenclator_prompt(bundles: str, existed_bundles: str) -> str:
    prompt = dedent(f"""
    You are a telecom branding and product naming expert specializing in {REGION} markets,
    particularly {OPREATOR_NAME} {COUNTRY}.

    Your task is to generate HIGH-QUALITY NAMES for newly created telecom bundles.

    ====================
    INPUT DATA
    ====================

    NEW BUNDLES:
    {bundles}

    EXISTING BUNDLES (REFERENCE):
    {existed_bundles}

    ====================
    OBJECTIVE
    ====================
    Generate culturally and commercially optimized names for EACH new bundle.

    ====================
    BRAND CONTEXT (CRITICAL)
    ====================
    - Operator: {OPREATOR_NAME} {COUNTRY}
    - Market: {COUNTRY} - {REGION}
    - Language influence: {LANG}, with simple, catchy wording
    - Style: 
        - Short
        - Memorable
        - Mobile-friendly
        - Commercial / Marketing oriented
    - Avoid complex or technical words

    ====================
    NAMING RULES (STRICT)
    ====================
    Each name MUST:
    - Be MAX 2 words

    ====================
    ALIGNMENT RULES (VERY IMPORTANT)
    ====================
    - Names MUST be consistent with EXISTING bundles
    - Do NOT invent strange or foreign naming styles
    - Match tone, simplicity, and structure of existing catalog
    - Avoid duplication or near-duplication of existing names
    - Avoid unrealistic or "weird" names

    ====================
    OUTPUT FORMAT (STRICT JSON ONLY)
    ====================
    {{
      "bundles": [
        {{
          "name": "...",
          "components": {{
            "volume_sms": <int>,
            "volume_voice_min": <int>,
            "volume_data_mb": <int>
          }},
          "validity_days": <int>,
          "price": <int>
        }}
      ]
    }}

    ====================
    HARD CONSTRAINTS
    ====================
    - Output ONLY valid JSON
    - Do NOT modify bundle components
    - Only generate / fix names
    - No explanations
    - No markdown
    - No text before or after JSON
    - No ```json fences

    If you output anything else, it is considered a failure.
    """)

    return prompt