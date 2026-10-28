"""
bioRxiv category taxonomy - flat list of subject areas.

Used by the profile form's category-picker widget.
The website's Clinical Trials and Epidemiology categories are omitted:
they are closed to new submissions (now on medRxiv).
"""

from typing import Dict, List

BIORXIV_CATEGORY_TREE: List[Dict] = [
    {"label": "Animal Behavior and Cognition", "value": "animal behavior and cognition"},
    {"label": "Biochemistry", "value": "biochemistry"},
    {"label": "Bioengineering", "value": "bioengineering"},
    {"label": "Bioinformatics", "value": "bioinformatics"},
    {"label": "Biophysics", "value": "biophysics"},
    {"label": "Cancer Biology", "value": "cancer biology"},
    {"label": "Cell Biology", "value": "cell biology"},
    {"label": "Developmental Biology", "value": "developmental biology"},
    {"label": "Ecology", "value": "ecology"},
    {"label": "Evolutionary Biology", "value": "evolutionary biology"},
    {"label": "Genetics", "value": "genetics"},
    {"label": "Genomics", "value": "genomics"},
    {"label": "Immunology", "value": "immunology"},
    {"label": "Microbiology", "value": "microbiology"},
    {"label": "Molecular Biology", "value": "molecular biology"},
    {"label": "Neuroscience", "value": "neuroscience"},
    {"label": "Paleontology", "value": "paleontology"},
    {"label": "Pathology", "value": "pathology"},
    {"label": "Pharmacology and Toxicology", "value": "pharmacology and toxicology"},
    {"label": "Physiology", "value": "physiology"},
    {"label": "Plant Biology", "value": "plant biology"},
    {
        "label": "Scientific Communication and Education",
        "value": "scientific communication and education",
    },
    {"label": "Synthetic Biology", "value": "synthetic biology"},
    {"label": "Systems Biology", "value": "systems biology"},
    {"label": "Zoology", "value": "zoology"},
]

BIORXIV_CODE_TO_LABEL: Dict[str, str] = {
    node["value"]: node["label"] for node in BIORXIV_CATEGORY_TREE
}

BIORXIV_LEAF_CODES: set = {node["value"] for node in BIORXIV_CATEGORY_TREE}


def label_for(code: str) -> str:
    """Return the human-readable label for a bioRxiv category code"""
    return BIORXIV_CODE_TO_LABEL.get(code, code)
