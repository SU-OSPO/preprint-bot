import os
import re
from pathlib import Path
from nltk.tokenize import sent_tokenize
from nltk import download
from transformers import pipeline
import torch
import json
from tqdm import tqdm

# llama-cpp-python is an optional dependency (the [llama] extra).
# Guard the import so the pipeline can run with --summarizer transformer
# without it installed; LlamaSummarizer.__init__ raises if it's missing.
try:
    from llama_cpp import Llama
    _LLAMA_AVAILABLE = True
except ImportError:
    Llama = None
    _LLAMA_AVAILABLE = False

# NLTK setup
try:
    sent_tokenize("This is a test. This is only a test.")
except Exception:
    def sent_tokenize(text):
        return text.split('. ')

download('punkt')


# Text cleaning
def clean_text(text):
    text = re.sub(r'-\n', '', text)
    text = re.sub(r'\n+', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\[\d+\]', '', text)
    text = re.sub(r'\([A-Za-z, ]+\d{4}\)', '', text)
    return text.strip()


# Section extraction
def extract_sections_from_txt_markdown(txt, exclude_sections=None):
    if exclude_sections is None:
        exclude_sections = ['acknowledgement', 'acknowledgements', 'reference', 'references']
    sections = []
    current_header = None
    current_text = []

    for line in txt.splitlines():
        line = line.strip()
        if line.startswith("### "):
            if current_header and current_text:
                if not any(excl in current_header.lower() for excl in exclude_sections):
                    sections.append({'header': current_header.lower(), 'text': ' '.join(current_text)})
            current_header = line[4:].strip()
            current_text = []
        else:
            if current_header:
                current_text.append(line)

    if current_header and current_text:
        if not any(excl in current_header.lower() for excl in exclude_sections):
            sections.append({'header': current_header.lower(), 'text': ' '.join(current_text)})

    return [{'header': s['header'], 'text': clean_text(s['text'])} for s in sections]


# Chunking for transformer
def chunk_text(text, max_tokens=900):
    sentences = sent_tokenize(text)
    chunks = []
    current = ''
    for sent in sentences:
        if len(current.split()) + len(sent.split()) < max_tokens:
            current += ' ' + sent
        else:
            chunks.append(current.strip())
            current = sent
    if current:
        chunks.append(current.strip())
    return chunks


# Transformer summarizer
class TransformerSummarizer:
    def __init__(self, model_name="google/pegasus-xsum"):
        device = 0 if torch.cuda.is_available() else -1
        print(f"Transformer summarizer using {'cuda:0' if device == 0 else 'cpu'}")
        self.summarizer = pipeline("summarization", model=model_name, tokenizer=model_name, use_fast=False, device=device)

    def summarize(self, text, max_length=180, mode="abstract"):
        chunks = chunk_text(text)
        summaries = []
        for chunk in chunks:
            if len(chunk.split()) < 20:
                continue
            try:
                result = self.summarizer(chunk, max_length=max_length, min_length=60, do_sample=False)
                summaries.append(result[0]['summary_text'])
            except Exception as e:
                print(f"Chunk summarization error: {e}")

        if len(summaries) > 1:
            try:
                combined = ' '.join(summaries)
                final_summary = self.summarizer(combined, max_length=max_length, min_length=60, do_sample=False)[0]['summary_text']
                return final_summary
            except Exception:
                return ' '.join(summaries)

        if summaries:
            return summaries[0]
        return "No valid chunks to summarize."


# LLaMA summarizer with explicit GPU support
class LlamaSummarizer:
    def __init__(self, model_path: str):
        if not _LLAMA_AVAILABLE:
            raise ImportError(
                "llama-cpp-python is not installed. "
                "Install it with: pip install '.[llama]', "
                "or use --summarizer transformer."
            )
        # Check if CUDA is available
        use_gpu = torch.cuda.is_available()
        
        if use_gpu:
            # Use GPU: offload all layers to GPU
            n_gpu_layers = -1  # -1 means offload all layers
            print(f"LLaMA summarizer using GPU (offloading all layers)")
        else:
            # Use CPU only
            n_gpu_layers = 0
            print(f"LLaMA summarizer using CPU only")
        
        self.llm = Llama(
            model_path=str(model_path),
            n_ctx=2048,
            n_threads=8,
            n_gpu_layers=n_gpu_layers,
            verbose=False
        )

    def summarize(self, text: str, max_length: int = 200, mode: str = "abstract") -> str:
        tokens = self.llm.tokenize(text.encode("utf-8"))
        if len(tokens) > 1800:
            tokens = tokens[:1800]
            text = self.llm.detokenize(tokens).decode("utf-8", errors="ignore")

        # Always use abstract summarization prompt
        prompt_text = (
            "Task: Write a 3-sentence summary of this research abstract.\n"
            "Rules:\n"
            "- Exactly 3 sentences\n"
            "- Focus on main contribution and results\n"
            "- No meta-commentary, word counts, or extra text\n"
            "- Stop after the third sentence\n\n"
            f"Abstract:\n{text}\n\n"
            "Summary:\n"
        )

        result = self.llm(prompt_text, max_tokens=max_length, temperature=0.3, top_p=0.9, echo=False)
        if isinstance(result, dict):
            if "choices" in result and len(result["choices"]) > 0:
                return result["choices"][0].get("text", "").strip()
            if "text" in result:
                return result["text"].strip()
        return str(result).strip()


# Section-based summarization
def summarize_sections_single_paragraph(sections, summarizer, max_length=180):
    section_keywords = [
        ('introduction', 'Introduction'),
        ('method', 'Methods'),
        ('result', 'Results'),
        ('discussion', 'Discussion'),
        ('conclusion', 'Conclusions')
    ]
    section_texts = {label: "" for _, label in section_keywords}
    for sec in sections:
        header = sec['header'].lower()
        for key, label in section_keywords:
            if key in header and not section_texts[label]:
                section_texts[label] = sec['text']
    section_summaries = []
    for _, label in section_keywords:
        text = section_texts[label]
        if text and len(text.split()) > 25:
            section_summaries.append(summarizer.summarize(text, max_length=max_length, mode="full"))
    return ' '.join(section_summaries)


# File / Folder processing
def process_file(input_file, output_file, summarizer, max_length=180):
    with open(input_file, "r", encoding="utf-8") as f:
        txt = f.read()
    sections = extract_sections_from_txt_markdown(txt)
    summary = summarize_sections_single_paragraph(sections, summarizer, max_length=max_length)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(summary)
    print(f"Summary saved to {output_file}")


def process_folder(input_folder, output_folder, summarizer, max_length=180):
    output_path = Path(output_folder)
    output_path.mkdir(parents=True, exist_ok=True)
    input_path = Path(input_folder)

    # Get list of files
    txt_files = list(input_path.glob("*.txt"))
    
    print(f"\nProcessing {len(txt_files)} files...")
    
    # Process with progress bar
    for input_file in tqdm(txt_files, desc="Summarizing papers", unit="paper"):
        output_file = output_path / f"{input_file.stem}_summary.txt"
        try:
            with open(input_file, "r", encoding="utf-8") as f:
                txt = f.read()
            sections = extract_sections_from_txt_markdown(txt)
            summary = summarize_sections_single_paragraph(sections, summarizer, max_length=max_length)
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(summary)
        except Exception as e:
            tqdm.write(f"Error processing {input_file.name}: {e}")


# Metadata processing
def process_metadata(metadata_path, output_path, summarizer, max_length=120, mode="abstract"):
    with open(metadata_path, "r", encoding="utf-8") as f:
        papers = json.load(f)

    print(f"\nGenerating summaries for {len(papers)} papers...")
    updated_papers = []
    
    for paper in tqdm(papers, desc="Summarizing abstracts", unit="paper"):
        original_summary = paper.get("summary", "")
        paper_title = paper.get("title", "Unknown")[:60]
        
        if not original_summary.strip():
            paper["llm_summary"] = "No summary available."
            tqdm.write(f"Skipped (no abstract): {paper_title}...")
        else:
            try:
                concise_summary = summarizer.summarize(original_summary, max_length=max_length, mode=mode)
                paper["llm_summary"] = concise_summary
                tqdm.write(f"Summarized: {paper_title}...")
            except Exception as e:
                paper["llm_summary"] = f"Error summarizing: {e}"
                tqdm.write(f"Error: {paper_title}... - {e}")
        
        updated_papers.append(paper)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(updated_papers, f, indent=2, ensure_ascii=False)

    print(f"\nUpdated metadata with LLM summaries saved to {output_path} (mode={mode})")