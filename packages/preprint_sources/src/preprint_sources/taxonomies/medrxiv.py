"""
medRxiv category taxonomy - flat list of subject areas.

Used by the profile form's category-picker widget.
Each value is the category name the API returns, which isn't always the
website label in lowercase (e.g. "hiv aids" for "HIV/AIDS").
"""

from typing import Dict, List

MEDRXIV_CATEGORY_TREE: List[Dict] = [
    {"label": "Addiction Medicine", "value": "addiction medicine"},
    {"label": "Allergy and Immunology", "value": "allergy and immunology"},
    {"label": "Anesthesia", "value": "anesthesia"},
    {"label": "Cardiovascular Medicine", "value": "cardiovascular medicine"},
    {"label": "Dentistry and Oral Medicine", "value": "dentistry and oral medicine"},
    {"label": "Dermatology", "value": "dermatology"},
    {"label": "Emergency Medicine", "value": "emergency medicine"},
    {
        "label": "Endocrinology (including Diabetes Mellitus and Metabolic Disease)",
        "value": "endocrinology",
    },
    {"label": "Epidemiology", "value": "epidemiology"},
    {"label": "Forensic Medicine", "value": "forensic medicine"},
    {"label": "Gastroenterology", "value": "gastroenterology"},
    {"label": "Genetic and Genomic Medicine", "value": "genetic and genomic medicine"},
    {"label": "Geriatric Medicine", "value": "geriatric medicine"},
    {"label": "Health Economics", "value": "health economics"},
    {"label": "Health Informatics", "value": "health informatics"},
    {"label": "Health Policy", "value": "health policy"},
    {
        "label": "Health Systems and Quality Improvement",
        "value": "health systems and quality improvement",
    },
    {"label": "Hematology", "value": "hematology"},
    {"label": "HIV/AIDS", "value": "hiv aids"},
    {"label": "Infectious Diseases (except HIV/AIDS)", "value": "infectious diseases"},
    {
        "label": "Intensive Care and Critical Care Medicine",
        "value": "intensive care and critical care medicine",
    },
    {"label": "Medical Education", "value": "medical education"},
    {"label": "Medical Ethics", "value": "medical ethics"},
    {"label": "Nephrology", "value": "nephrology"},
    {"label": "Neurology", "value": "neurology"},
    {"label": "Nursing", "value": "nursing"},
    {"label": "Nutrition", "value": "nutrition"},
    {"label": "Obstetrics and Gynecology", "value": "obstetrics and gynecology"},
    {
        "label": "Occupational and Environmental Health",
        "value": "occupational and environmental health",
    },
    {"label": "Oncology", "value": "oncology"},
    {"label": "Ophthalmology", "value": "ophthalmology"},
    {"label": "Orthopedics", "value": "orthopedics"},
    {"label": "Otolaryngology", "value": "otolaryngology"},
    {"label": "Pain Medicine", "value": "pain medicine"},
    {"label": "Palliative Medicine", "value": "palliative medicine"},
    {"label": "Pathology", "value": "pathology"},
    {"label": "Pediatrics", "value": "pediatrics"},
    {"label": "Pharmacology and Therapeutics", "value": "pharmacology and therapeutics"},
    {"label": "Primary Care Research", "value": "primary care research"},
    {"label": "Psychiatry and Clinical Psychology", "value": "psychiatry and clinical psychology"},
    {"label": "Public and Global Health", "value": "public and global health"},
    {"label": "Radiology and Imaging", "value": "radiology and imaging"},
    {
        "label": "Rehabilitation Medicine and Physical Therapy",
        "value": "rehabilitation medicine and physical therapy",
    },
    {"label": "Respiratory Medicine", "value": "respiratory medicine"},
    {"label": "Rheumatology", "value": "rheumatology"},
    {"label": "Sexual and Reproductive Health", "value": "sexual and reproductive health"},
    {"label": "Sports Medicine", "value": "sports medicine"},
    {"label": "Surgery", "value": "surgery"},
    {"label": "Toxicology", "value": "toxicology"},
    {"label": "Transplantation", "value": "transplantation"},
    {"label": "Urology", "value": "urology"},
]

MEDRXIV_CODE_TO_LABEL: Dict[str, str] = {
    node["value"]: node["label"] for node in MEDRXIV_CATEGORY_TREE
}

MEDRXIV_LEAF_CODES: set = {node["value"] for node in MEDRXIV_CATEGORY_TREE}


def label_for(code: str) -> str:
    """Return the human-readable label for a medRxiv category code"""
    return MEDRXIV_CODE_TO_LABEL.get(code, code)
