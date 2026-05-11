# pipeline/taxonomy.py
# Original detailed category lookup
CATEGORY_LOOKUP = {
    # Category A: Language and Rhetorical Fallacies
    "A1": "Category A: Use of Dehumanizing or Vituperative Language",
    "A2": "Category A: Unsubstantiated Accusations of Treason / Dual Loyalty",
    "A3": "Category A: Simplistic and Ahistorical Equivalencies",
    "A4": "Category A: Use of Derogatory Slurs and Pejoratives",
    "A5": "Category A: Ominous Innuendo and Suggestive Language",
    "A6": "Category A: Creation of a False Dichotomy",
    "A7": "Category A: Appeal to Inappropriate Authority or Consensus",
    "A7.1": "Category A: Unsubstantiated Accusations of Malice, Bigotry, or Criminality",

    # Category B: Misrepresentation and Falsification
    "B8": "Category B: Misappropriation of Symbols and Practices",
    "B9": "Category B: Misrepresenting Core Ideology and Texts",
    "B10": "Category B: Historical Falsification and Myth-Making",
    "B11": "Category B: Conflation of RSS with All Hindus or the Indian State",
    "B12": "Category B: Selective and Biased Framing",
    "B13": "Category B: Misleading Use of Decontextualized Data",
    "B14": "Category B: Misattribution of Fringe Actions to the Mainstream",
    "B15": "Category B: Denial of the Right of Reply / Presenting Accusations without Rebuttal",
    "B15.1": "Category B: Propaganda Mandate Framing",

    # Category C: Psychological and Sociological Tactics
    "C16": "Category C: Gaslighting and Invalidation of Lived Experience",
    "C16.1": "Category C: Scare-Quote Hinduphobia Dismissal",
    "C17": "Category C: Strategic Mislabeling to Silence and Invert Victimhood",
    "C18": "Category C: Denial of Phobia's Existence as a Phobic Act",
    "C19": "Category C: Rejection of Any Possibility of Good Intent",
    "C20": "Category C: Promotion of Grand Conspiracy Theories",
    "C21": "Category C: Collective Guilt and Punishment",
    "C22": "Category C: Pathologizing Members",
    "C23": "Category C: Weaponizing Internal Dissent",
    "C24": "Category C: Denial of Agency and Self-Interpretation",

    # Category D: Calls to Action and Behavioral Indicators
    "D25": "Category D: Incitement to Violence, Discrimination, or Ostracism",
    "D25.1": "Category D: Systematic Partnership Termination Demands",
    "D26": "Category D: Moving the Goalposts",
    "D27": "Category D: Refusal to Acknowledge Nuance, Evolution, or Internal Debate",
    "D28": "Category D: Guilt by Association",
    "D29": "Category D: Catastrophizing and Alarmism",
    "D30": "Category D: Emotional Outrage Over Factual Analysis",
    "D31": "Category D: Attribution of All Societal Ills",
    "D32": "Category D: Inducing Perpetrator Stigma via Decontextualized History",
    "D33": "Category D: Dismissal of Democratic Legitimacy",
    "D34": "Category D: Imposing a Singular, Negative Definition on 'Hindutva'",
    "D35": "Category D: Application of Differential Evidentiary Standards",
    "D36": "Category D: Application of Pervasive Double Standards",
    "D37": "Category D: Academic or Intellectual Gatekeeping",
    "D38": "Category D: 'Lawfare' or Vexatious Litigation",
    "D39": "Category D: Economic and Professional Blacklisting",

    # Category E: Civilizational Pathologizing and Diaspora Demonization
    "E40": "Category E: Pathologizing Guruship and Hindu Spiritual Authority",
    "E41": "Category E: Framing Gurus as Prototype Abusers and Brahmanical Oppressors",
    "E42": "Category E: Conceptual Delegitimization via 'Cruel Optimism' and 'Confined Universalism'",
    "E43": "Category E: Demonization of Hindu Nationalist Diaspora and Targeting Narratives",
    "E44": "Category E: Systematic Criminalization of Advocacy as Disinformation and Propaganda",
    "E45": "Category E: Transnational Conspiracy and World-Mission Framing",
    "E46": "Category E: Pathologizing Constitutional Alternative Models",
    "E47": "Category E: Selective Criminalization of Religious Authority",
    "E48": "Category E: Hagiographic Delegitimization",

    # Category F: Institutional Omnipresence and Permanence Framing
    "F49": "Category F: Portraying Ubiquitous and Inescapable Influence",
    "F50": "Category F: Historical Guilt by Assassination",
    "F51": "Category F: Framing Resistance as Futile Without Alternative",

    # Category G: Majoritarianism as Inherent Evil
    "G52": "Category G: Treating Democratic Majority Representation as Illegitimate",
    "G53": "Category G: Contrasting Consensus-Building with Majoritarian Leadership",

    # Category H: Strategic Victimhood Inversion and Minority Masking
    "H54": "Category H: Micro-Minority Masquerading",
    "H55": "Category H: Dismissing Religious Freedom Claims as Strategic Deception",
    "H56": "Category H: 'Innocuous-Sounding' Delegitimization",

    # Category I: Institutional Boycott and Partnership Termination Advocacy
    "I57": "Category I: Calling for Institutional Disengagement",
    "I58": "Category I: Framing Engagement as Moral Contamination",

    # Category J: Comparative Cultural Chauvinism and Personal Deficiency Attacks
    "J59": "Category J: Contrasting Cultural Sophistication",
    "J60": "Category J: Pathologizing via Personality Deficiency",

    # Category K: Media Capture and Institutional Takeover Narratives
    "K61": "Category K: Declaring Complete Media Capture",
    "K62": "Category K: Judicial Delegitimization via Capture Claims",

    # Category L: Fractal Organizational Pathologizing
    "L63": "Category L: Fractal Guruship as Totalizing System",

    # Category M: Embodiment and Personification of Authoritarianism
    "M64": "Category M: Leader as Embodiment of Authoritarian Guruship",
    "M65": "Category M: Bhakts as Mindless Devotees",

    # Category N: Masquerading and Fooling Narratives
    "N66": "Category N: Beleaguered Minority Masquerade",
    "N67": "Category N: 'Haven't Fooled Anyone' Elite Gatekeeping",

    # Category O: Alarming Ideological Movement Framing
    "O68": "Category O: 'Alarming Ideological Movement' Designation",
    "O69": "Category O: Ad Hominem Attack Catalog Without Evidence",

    # Category P: Rhetorical Question Cascades for Impossibility Claims
    "P70": "Category P: Impossibility Cascade via Rhetorical Questions",
    "P71": "Category P: Street Legitimacy Contestation Threat",

    # Category Q: Civilizational Inferiority and Fear-Mongering
    "Q72": "Category Q: Identities Change Through Fear Manipulation",
    "Q73": "Category Q: Islamists Helped RSS Narrative",
}

# Main 8 frontend categories
MAIN_CATEGORIES = {
    1: "Negative Stereotyping of RSS",
    2: "Dehumanization or Hate Speech",
    3: "Justification of Harm/Discrimination",
    4: "Blaming RSS for Societal Problems",
    5: "Misrepresentation of RSS",
    6: 'Fear-Mongering ("hindutva")',
    7: "Contextual Tone",
    8: "Guilt by Association",
}

# Mapping: detailed code -> list of main category IDs
DETAIL_TO_MAIN_MAPPING = {
    "A1": [1, 2], "A2": [1], "A3": [1, 5], "A4": [1, 2],
    "A5": [1, 6], "A7.1": [1], "7.1": [1, 2], "19": [6], "20": [5], "29": [6],
    "C17": [2], "C21": [2, 3], "C22": [2], "D25": [2, 3],
    "E40": [2, 5], "E41": [2, 5], "J60": [2], "M65": [2], "O69": [2],
    "D25.1": [3], "D37": [3], "D38": [3], "D39": [3], "I57": [3], "I58": [3],
    "C20": [4, 6], "D29": [4, 6], "D31": [4], "E43": [4, 6],
    "E45": [4, 6], "F49": [4], "K61": [4], "K62": [4], "Q73": [4],
    "B8": [5], "B9": [5], "B10": [5], "B11": [5, 1], "B12": [5],
    "B13": [5], "B14": [5], "B15": [5], "B15.1": [5],
    "C16": [5], "C16.1": [5], "C24": [5], "D26": [5], "D27": [5],
    "D34": [5], "D35": [5], "D36": [5], "E42": [5], "E44": [5],
    "E46": [5], "E48": [5], "H54": [5], "H55": [5], "H56": [5],
    "N66": [5], "N67": [5],
    "A6": [6], "C18": [6], "C19": [6], "D32": [6], "D33": [6],
    "E47": [6], "F50": [6], "F51": [6], "G52": [6], "G53": [6],
    "L63": [6], "M64": [6], "O68": [6], "P70": [6], "P71": [6], "Q72": [6],
    "A7": [7], "C23": [8, 7], "D30": [7], "J59": [7],
    "D28": [8],
}


def get_main_categories_for_code(code: str) -> list[int]:
    """Given a detailed code (e.g. 'A1'), return list of main category IDs."""
    return DETAIL_TO_MAIN_MAPPING.get(code, [])


def get_main_category_name(main_id: int) -> str:
    """Get the name of a main category by its ID (1-8)."""
    return MAIN_CATEGORIES.get(main_id, "Unknown Category")


def get_all_codes_for_main_category(main_id: int) -> list[str]:
    """Get all detailed codes that belong to a specific main category."""
    return [code for code, cats in DETAIL_TO_MAIN_MAPPING.items() if main_id in cats]


def enrich_detection(detection: dict) -> dict:
    """
    Given a raw detection dict from Gemini (with method_code),
    add taxonomy-enriched fields:
      - method_name_full   : full CATEGORY_LOOKUP label
      - main_category_ids  : list of main category IDs (1-8)
      - main_category_names: list of main category name strings
    Returns the detection dict in-place (also returns it).
    """
    code = detection.get("method_code", "")
    detection["method_name_full"]   = CATEGORY_LOOKUP.get(code, detection.get("method_name", ""))
    main_ids                         = get_main_categories_for_code(code)
    detection["main_category_ids"]  = main_ids
    detection["main_category_names"] = [get_main_category_name(i) for i in main_ids]
    return detection
