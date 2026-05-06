import requests
from lxml import etree

GROBID_URL = "http://localhost:8070/api/processFulltextDocument"
NS = {"tei": "http://www.tei-c.org/ns/1.0"}


def extract_grobid_sections(src):
    """
    Extract structured metadata, sections and references from a PDF.
    Returns dict with title, abstract, authors, sections, etc.
    """
    # 1. Load bytes 
    if isinstance(src, (bytes, bytearray)):
        pdf_bytes = src
    else:  # assume path-like
        with open(src, "rb") as fp:
            pdf_bytes = fp.read()

    # 2. Call GROBID 
    try:
        resp = requests.post(
            GROBID_URL,
            files={"input": ("file.pdf", pdf_bytes)},
            data={"consolidateHeader": "1"},
            timeout=60,
        )
        resp.raise_for_status()
    except Exception as e:
        print(f"GROBID error: {e}")
        raise
    
    root = etree.fromstring(resp.content)

    # 3. Convenience helper
    def _txt(el, path):
        found = el.find(path, NS)
        if found is not None:
            return " ".join(found.itertext()).strip()
        return ""

    # 4. Extract metadata
    title = _txt(root, ".//tei:titleStmt/tei:title")
    abstract = _txt(root, ".//tei:profileDesc/tei:abstract")
    
    authors = []
    for auth in root.findall(".//tei:sourceDesc//tei:author", NS):
        forename = auth.findtext("tei:persName/tei:forename", namespaces=NS, default="")
        surname = auth.findtext("tei:persName/tei:surname", namespaces=NS, default="")
        full_name = f"{forename} {surname}".strip()
        if full_name:
            authors.append(full_name)
    
    affiliations = []
    for aff in root.findall(".//tei:sourceDesc//tei:affiliation", NS):
        aff_text = " ".join(aff.itertext()).strip()
        if aff_text:
            affiliations.append(aff_text)
    
    publication_date = _txt(root, ".//tei:sourceDesc//tei:date")

    # 5. Extract sections from body
    sections = []
    exclude_headers = ['acknowledgement', 'acknowledgements', 'reference', 'references', 
                      'bibliography', 'appendix', 'supplementary']
    
    for div in root.findall(".//tei:body//tei:div", NS):
        head_elem = div.find("tei:head", NS)
        head = ""
        if head_elem is not None:
            head = "".join(head_elem.itertext()).strip()
        
        if not head:
            head = "Untitled Section"
        
        # Skip excluded sections
        if any(excl in head.lower() for excl in exclude_headers):
            continue
        
        # Get all paragraph text
        paras = []
        for p in div.findall(".//tei:p", NS):
            p_text = "".join(p.itertext()).strip()
            if p_text:
                paras.append(p_text)
        
        if paras:
            section_text = "\n\n".join(paras)
            sections.append({"header": head, "text": section_text})

    # 6. Extract references
    references = []
    for ref in root.findall(".//tei:listBibl//tei:biblStruct", NS):
        ref_title = _txt(ref, ".//tei:title")
        ref_authors = []
        for surname in ref.findall(".//tei:author//tei:surname", NS):
            if surname.text:
                ref_authors.append(surname.text.strip())
        
        if ref_title or ref_authors:
            references.append({"title": ref_title, "authors": ref_authors})

    return {
        "title": title,
        "abstract": abstract,
        "authors": authors,
        "pub_date": publication_date,
        "sections": sections,
    }
