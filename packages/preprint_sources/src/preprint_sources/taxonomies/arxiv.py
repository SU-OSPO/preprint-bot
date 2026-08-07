"""
arXiv category taxonomy – flat list and nested tree structure.

Used by the profile form's category-picker widget.
The tree mirrors the Streamlit app's ARXIV_CATEGORY_TREE exactly,
with "title" renamed to "label" for the Django JS picker.
"""

from typing import Dict, List

# Nested tree used by the JavaScript category picker
ARXIV_CATEGORY_TREE: List[Dict] = [
    {
        "label": "Computer Science",
        "value": "cs",
        "children": [
            {"label": "Artificial Intelligence (cs.AI)", "value": "cs.AI"},
            {"label": "Hardware Architecture (cs.AR)", "value": "cs.AR"},
            {"label": "Computational Complexity (cs.CC)", "value": "cs.CC"},
            {"label": "Computational Engineering, Finance, and Science (cs.CE)", "value": "cs.CE"},
            {"label": "Computational Geometry (cs.CG)", "value": "cs.CG"},
            {"label": "Computation and Language (cs.CL)", "value": "cs.CL"},
            {"label": "Cryptography and Security (cs.CR)", "value": "cs.CR"},
            {"label": "Computer Vision and Pattern Recognition (cs.CV)", "value": "cs.CV"},
            {"label": "Computers and Society (cs.CY)", "value": "cs.CY"},
            {"label": "Databases (cs.DB)", "value": "cs.DB"},
            {"label": "Distributed, Parallel, and Cluster Computing (cs.DC)", "value": "cs.DC"},
            {"label": "Digital Libraries (cs.DL)", "value": "cs.DL"},
            {"label": "Discrete Mathematics (cs.DM)", "value": "cs.DM"},
            {"label": "Data Structures and Algorithms (cs.DS)", "value": "cs.DS"},
            {"label": "Emerging Technologies (cs.ET)", "value": "cs.ET"},
            {"label": "Formal Languages and Automata Theory (cs.FL)", "value": "cs.FL"},
            {"label": "General Literature (cs.GL)", "value": "cs.GL"},
            {"label": "Graphics (cs.GR)", "value": "cs.GR"},
            {"label": "Computer Science and Game Theory (cs.GT)", "value": "cs.GT"},
            {"label": "Human-Computer Interaction (cs.HC)", "value": "cs.HC"},
            {"label": "Information Retrieval (cs.IR)", "value": "cs.IR"},
            {"label": "Information Theory (cs.IT)", "value": "cs.IT"},
            {"label": "Machine Learning (cs.LG)", "value": "cs.LG"},
            {"label": "Logic in Computer Science (cs.LO)", "value": "cs.LO"},
            {"label": "Multiagent Systems (cs.MA)", "value": "cs.MA"},
            {"label": "Multimedia (cs.MM)", "value": "cs.MM"},
            {"label": "Mathematical Software (cs.MS)", "value": "cs.MS"},
            {"label": "Numerical Analysis (cs.NA)", "value": "cs.NA"},
            {"label": "Neural and Evolutionary Computing (cs.NE)", "value": "cs.NE"},
            {"label": "Networking and Internet Architecture (cs.NI)", "value": "cs.NI"},
            {"label": "Other Computer Science (cs.OH)", "value": "cs.OH"},
            {"label": "Operating Systems (cs.OS)", "value": "cs.OS"},
            {"label": "Performance (cs.PF)", "value": "cs.PF"},
            {"label": "Programming Languages (cs.PL)", "value": "cs.PL"},
            {"label": "Robotics (cs.RO)", "value": "cs.RO"},
            {"label": "Symbolic Computation (cs.SC)", "value": "cs.SC"},
            {"label": "Sound (cs.SD)", "value": "cs.SD"},
            {"label": "Software Engineering (cs.SE)", "value": "cs.SE"},
            {"label": "Social and Information Networks (cs.SI)", "value": "cs.SI"},
            {"label": "Systems and Control (cs.SY)", "value": "cs.SY"},
        ],
    },
    {
        "label": "Economics",
        "value": "econ",
        "children": [
            {"label": "Econometrics (econ.EM)", "value": "econ.EM"},
            {"label": "General Economics (econ.GN)", "value": "econ.GN"},
            {"label": "Theoretical Economics (econ.TH)", "value": "econ.TH"},
        ],
    },
    {
        "label": "Electrical Engineering and Systems Science",
        "value": "eess",
        "children": [
            {"label": "Audio and Speech Processing (eess.AS)", "value": "eess.AS"},
            {"label": "Image and Video Processing (eess.IV)", "value": "eess.IV"},
            {"label": "Signal Processing (eess.SP)", "value": "eess.SP"},
            {"label": "Systems and Control (eess.SY)", "value": "eess.SY"},
        ],
    },
    {
        "label": "Mathematics",
        "value": "math",
        "children": [
            {"label": "Commutative Algebra (math.AC)", "value": "math.AC"},
            {"label": "Algebraic Geometry (math.AG)", "value": "math.AG"},
            {"label": "Analysis of PDEs (math.AP)", "value": "math.AP"},
            {"label": "Algebraic Topology (math.AT)", "value": "math.AT"},
            {"label": "Classical Analysis and ODEs (math.CA)", "value": "math.CA"},
            {"label": "Combinatorics (math.CO)", "value": "math.CO"},
            {"label": "Category Theory (math.CT)", "value": "math.CT"},
            {"label": "Complex Variables (math.CV)", "value": "math.CV"},
            {"label": "Differential Geometry (math.DG)", "value": "math.DG"},
            {"label": "Dynamical Systems (math.DS)", "value": "math.DS"},
            {"label": "Functional Analysis (math.FA)", "value": "math.FA"},
            {"label": "General Mathematics (math.GM)", "value": "math.GM"},
            {"label": "General Topology (math.GN)", "value": "math.GN"},
            {"label": "Group Theory (math.GR)", "value": "math.GR"},
            {"label": "Geometric Topology (math.GT)", "value": "math.GT"},
            {"label": "History and Overview (math.HO)", "value": "math.HO"},
            {"label": "Information Theory (math.IT)", "value": "math.IT"},
            {"label": "K-Theory and Homology (math.KT)", "value": "math.KT"},
            {"label": "Logic (math.LO)", "value": "math.LO"},
            {"label": "Metric Geometry (math.MG)", "value": "math.MG"},
            {"label": "Mathematical Physics (math.MP)", "value": "math.MP"},
            {"label": "Numerical Analysis (math.NA)", "value": "math.NA"},
            {"label": "Number Theory (math.NT)", "value": "math.NT"},
            {"label": "Operator Algebras (math.OA)", "value": "math.OA"},
            {"label": "Optimization and Control (math.OC)", "value": "math.OC"},
            {"label": "Probability (math.PR)", "value": "math.PR"},
            {"label": "Quantum Algebra (math.QA)", "value": "math.QA"},
            {"label": "Rings and Algebras (math.RA)", "value": "math.RA"},
            {"label": "Representation Theory (math.RT)", "value": "math.RT"},
            {"label": "Symplectic Geometry (math.SG)", "value": "math.SG"},
            {"label": "Spectral Theory (math.SP)", "value": "math.SP"},
            {"label": "Statistics Theory (math.ST)", "value": "math.ST"},
        ],
    },
    {
        "label": "Physics",
        "value": "physics_group",
        "children": [
            {
                "label": "Astrophysics",
                "value": "astro-ph",
                "children": [
                    {"label": "Cosmology and Nongalactic Astrophysics (astro-ph.CO)", "value": "astro-ph.CO"},
                    {"label": "Earth and Planetary Astrophysics (astro-ph.EP)", "value": "astro-ph.EP"},
                    {"label": "Astrophysics of Galaxies (astro-ph.GA)", "value": "astro-ph.GA"},
                    {"label": "High Energy Astrophysical Phenomena (astro-ph.HE)", "value": "astro-ph.HE"},
                    {"label": "Instrumentation and Methods for Astrophysics (astro-ph.IM)", "value": "astro-ph.IM"},
                    {"label": "Solar and Stellar Astrophysics (astro-ph.SR)", "value": "astro-ph.SR"},
                ],
            },
            {
                "label": "Condensed Matter",
                "value": "cond-mat",
                "children": [
                    {"label": "Disordered Systems and Neural Networks (cond-mat.dis-nn)", "value": "cond-mat.dis-nn"},
                    {"label": "Mesoscale and Nanoscale Physics (cond-mat.mes-hall)", "value": "cond-mat.mes-hall"},
                    {"label": "Materials Science (cond-mat.mtrl-sci)", "value": "cond-mat.mtrl-sci"},
                    {"label": "Other Condensed Matter (cond-mat.other)", "value": "cond-mat.other"},
                    {"label": "Quantum Gases (cond-mat.quant-gas)", "value": "cond-mat.quant-gas"},
                    {"label": "Soft Condensed Matter (cond-mat.soft)", "value": "cond-mat.soft"},
                    {"label": "Statistical Mechanics (cond-mat.stat-mech)", "value": "cond-mat.stat-mech"},
                    {"label": "Strongly Correlated Electrons (cond-mat.str-el)", "value": "cond-mat.str-el"},
                    {"label": "Superconductivity (cond-mat.supr-con)", "value": "cond-mat.supr-con"},
                ],
            },
            {
                "label": "High Energy Physics",
                "value": "hep",
                "children": [
                    {"label": "High Energy Physics – Experiment (hep-ex)", "value": "hep-ex"},
                    {"label": "High Energy Physics – Lattice (hep-lat)", "value": "hep-lat"},
                    {"label": "High Energy Physics – Phenomenology (hep-ph)", "value": "hep-ph"},
                    {"label": "High Energy Physics – Theory (hep-th)", "value": "hep-th"},
                ],
            },
            {
                "label": "Nonlinear Sciences",
                "value": "nlin",
                "children": [
                    {"label": "Adaptation and Self-Organizing Systems (nlin.AO)", "value": "nlin.AO"},
                    {"label": "Chaotic Dynamics (nlin.CD)", "value": "nlin.CD"},
                    {"label": "Cellular Automata and Lattice Gases (nlin.CG)", "value": "nlin.CG"},
                    {"label": "Pattern Formation and Solitons (nlin.PS)", "value": "nlin.PS"},
                    {"label": "Exactly Solvable and Integrable Systems (nlin.SI)", "value": "nlin.SI"},
                ],
            },
            {
                "label": "Physics (General)",
                "value": "physics",
                "children": [
                    {"label": "Accelerator Physics (physics.acc-ph)", "value": "physics.acc-ph"},
                    {"label": "Atmospheric and Oceanic Physics (physics.ao-ph)", "value": "physics.ao-ph"},
                    {"label": "Applied Physics (physics.app-ph)", "value": "physics.app-ph"},
                    {"label": "Atomic and Molecular Clusters (physics.atm-clus)", "value": "physics.atm-clus"},
                    {"label": "Atomic Physics (physics.atom-ph)", "value": "physics.atom-ph"},
                    {"label": "Biological Physics (physics.bio-ph)", "value": "physics.bio-ph"},
                    {"label": "Chemical Physics (physics.chem-ph)", "value": "physics.chem-ph"},
                    {"label": "Classical Physics (physics.class-ph)", "value": "physics.class-ph"},
                    {"label": "Computational Physics (physics.comp-ph)", "value": "physics.comp-ph"},
                    {"label": "Data Analysis, Statistics and Probability (physics.data-an)", "value": "physics.data-an"},
                    {"label": "Physics Education (physics.ed-ph)", "value": "physics.ed-ph"},
                    {"label": "Fluid Dynamics (physics.flu-dyn)", "value": "physics.flu-dyn"},
                    {"label": "General Physics (physics.gen-ph)", "value": "physics.gen-ph"},
                    {"label": "Geophysics (physics.geo-ph)", "value": "physics.geo-ph"},
                    {"label": "History and Philosophy of Physics (physics.hist-ph)", "value": "physics.hist-ph"},
                    {"label": "Instrumentation and Detectors (physics.ins-det)", "value": "physics.ins-det"},
                    {"label": "Medical Physics (physics.med-ph)", "value": "physics.med-ph"},
                    {"label": "Optics (physics.optics)", "value": "physics.optics"},
                    {"label": "Plasma Physics (physics.plasm-ph)", "value": "physics.plasm-ph"},
                    {"label": "Popular Physics (physics.pop-ph)", "value": "physics.pop-ph"},
                    {"label": "Physics and Society (physics.soc-ph)", "value": "physics.soc-ph"},
                    {"label": "Space Physics (physics.space-ph)", "value": "physics.space-ph"},
                ],
            },
            {
                "label": "Other Physics",
                "value": "other-physics",
                "children": [
                    {"label": "General Relativity and Quantum Cosmology (gr-qc)", "value": "gr-qc"},
                    {"label": "Mathematical Physics (math-ph)", "value": "math-ph"},
                    {"label": "Nuclear Experiment (nucl-ex)", "value": "nucl-ex"},
                    {"label": "Nuclear Theory (nucl-th)", "value": "nucl-th"},
                    {"label": "Quantum Physics (quant-ph)", "value": "quant-ph"},
                ],
            },
        ],
    },
    {
        "label": "Quantitative Biology",
        "value": "q-bio",
        "children": [
            {"label": "Biomolecules (q-bio.BM)", "value": "q-bio.BM"},
            {"label": "Cell Behavior (q-bio.CB)", "value": "q-bio.CB"},
            {"label": "Genomics (q-bio.GN)", "value": "q-bio.GN"},
            {"label": "Molecular Networks (q-bio.MN)", "value": "q-bio.MN"},
            {"label": "Neurons and Cognition (q-bio.NC)", "value": "q-bio.NC"},
            {"label": "Other Quantitative Biology (q-bio.OT)", "value": "q-bio.OT"},
            {"label": "Populations and Evolution (q-bio.PE)", "value": "q-bio.PE"},
            {"label": "Quantitative Methods (q-bio.QM)", "value": "q-bio.QM"},
            {"label": "Subcellular Processes (q-bio.SC)", "value": "q-bio.SC"},
            {"label": "Tissues and Organs (q-bio.TO)", "value": "q-bio.TO"},
        ],
    },
    {
        "label": "Quantitative Finance",
        "value": "q-fin",
        "children": [
            {"label": "Computational Finance (q-fin.CP)", "value": "q-fin.CP"},
            {"label": "Economics (q-fin.EC)", "value": "q-fin.EC"},
            {"label": "General Finance (q-fin.GN)", "value": "q-fin.GN"},
            {"label": "Mathematical Finance (q-fin.MF)", "value": "q-fin.MF"},
            {"label": "Portfolio Management (q-fin.PM)", "value": "q-fin.PM"},
            {"label": "Pricing of Securities (q-fin.PR)", "value": "q-fin.PR"},
            {"label": "Risk Management (q-fin.RM)", "value": "q-fin.RM"},
            {"label": "Statistical Finance (q-fin.ST)", "value": "q-fin.ST"},
            {"label": "Trading and Market Microstructure (q-fin.TR)", "value": "q-fin.TR"},
        ],
    },
    {
        "label": "Statistics",
        "value": "stat",
        "children": [
            {"label": "Applications (stat.AP)", "value": "stat.AP"},
            {"label": "Computation (stat.CO)", "value": "stat.CO"},
            {"label": "Methodology (stat.ME)", "value": "stat.ME"},
            {"label": "Machine Learning (stat.ML)", "value": "stat.ML"},
            {"label": "Other Statistics (stat.OT)", "value": "stat.OT"},
            {"label": "Statistics Theory (stat.TH)", "value": "stat.TH"},
        ],
    },
]


def _build_code_to_label() -> Dict[str, str]:
    """Build a flat code → human-readable label mapping."""
    out: Dict[str, str] = {}

    def walk(nodes):
        for node in nodes:
            v = node.get("value", "")
            lbl = node.get("label", v)
            if v:
                out[v] = lbl
            for ch in node.get("children", []):
                walk([ch])

    walk(ARXIV_CATEGORY_TREE)
    return out


ARXIV_CODE_TO_LABEL: Dict[str, str] = _build_code_to_label()


def _build_leaf_codes() -> set:
    """Return the set of leaf category codes (no children in the tree)."""
    leaves: set = set()

    def walk(nodes):
        for node in nodes:
            children = node.get("children", [])
            if children:
                walk(children)
            elif node.get("value"):
                leaves.add(node["value"])

    walk(ARXIV_CATEGORY_TREE)
    return leaves


ARXIV_LEAF_CODES: set = _build_leaf_codes()


def label_for(code: str) -> str:
    """Return the human-readable label for an arXiv category code."""
    return ARXIV_CODE_TO_LABEL.get(code, code)
