from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime, date
from enum import Enum

# Enums
class FrequencyEnum(str, Enum):
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"

# class ThresholdEnum(str, Enum):
#     low = "low"
#     medium = "medium"
#     high = "high"

class SourceEnum(str, Enum):
    user = "user"
    arxiv = "arxiv"

class ModeEnum(str, Enum):
    abstract = "abstract"
    full = "full"

class TypeEnum(str, Enum):
    abstract = "abstract"
    section = "section"

class StatusEnum(str, Enum):
    sent = "sent"
    failed = "failed"

# User Schemas
class UserCreate(BaseModel):
    email: str
    name: Optional[str] = None

class UserUpdate(BaseModel):
    email: Optional[str] = None
    name: Optional[str] = None

class UserResponse(BaseModel):
    id: int
    email: str
    name: Optional[str]
    created_at: datetime

# Profile Schemas
class ProfileCreate(BaseModel):
    user_id: int
    name: str
    keywords: List[str]
    categories: List[str] = []
    email_notify: bool = True
    frequency: FrequencyEnum
    threshold: float = 0.6
    top_x: Optional[int] = None

class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    keywords: Optional[List[str]] = None
    categories: Optional[List[str]] = None
    email_notify: Optional[bool] = None
    frequency: Optional[FrequencyEnum] = None
    threshold: Optional[float] = None
    top_x: Optional[int] = None

class ProfileResponse(BaseModel):
    id: int
    user_id: int
    name: str
    keywords: List[str]
    categories: List[str]
    email_notify: bool
    frequency: str
    threshold: float
    top_x: Optional[int]
    created_at: datetime
    updated_at: datetime

# Corpus Schemas
class CorpusCreate(BaseModel):
    user_id: int
    name: str
    description: Optional[str] = None

class CorpusUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

class CorpusResponse(BaseModel):
    id: int
    user_id: int
    name: str
    description: Optional[str]
    created_at: datetime

# ProfileCorpus Schemas
class ProfileCorpusCreate(BaseModel):
    profile_id: int
    corpus_id: int

class ProfileCorpusResponse(BaseModel):
    profile_id: int
    corpus_id: int

# Paper Schemas
class PaperCreate(BaseModel):
    corpus_id: Optional[int] = None  # used for M2M linking only
    arxiv_id: Optional[str] = None
    title: str
    abstract: Optional[str] = None
    metadata: Optional[dict] = None
    pdf_path: Optional[str] = None
    submitted_date: Optional[datetime] = None
    source: SourceEnum

class PaperUpdate(BaseModel):
    arxiv_id: Optional[str] = None
    title: Optional[str] = None
    abstract: Optional[str] = None
    metadata: Optional[dict] = None
    pdf_path: Optional[str] = None
    source: Optional[SourceEnum] = None

class PaperResponse(BaseModel):
    id: int
    corpus_id: Optional[int]  # legacy — may be NULL for new papers
    arxiv_id: Optional[str]
    title: str
    abstract: Optional[str]
    metadata: Optional[dict]
    pdf_path: Optional[str]
    processed_text_path: Optional[str]
    submitted_date: Optional[datetime]
    source: str
    created_at: datetime

# Section Schemas
class SectionCreate(BaseModel):
    paper_id: int
    header: Optional[str] = None
    text: Optional[str] = None

class SectionUpdate(BaseModel):
    header: Optional[str] = None
    text: Optional[str] = None

class SectionResponse(BaseModel):
    id: int
    paper_id: int
    header: Optional[str]
    text: Optional[str]
    created_at: datetime

# Summary Schemas
class SummaryCreate(BaseModel):
    paper_id: int
    mode: ModeEnum
    summary_text: Optional[str] = None
    summarizer: Optional[str] = None

class SummaryUpdate(BaseModel):
    summary_text: Optional[str] = None
    summarizer: Optional[str] = None

class SummaryResponse(BaseModel):
    id: int
    paper_id: int
    mode: str
    summary_text: Optional[str]
    summarizer: Optional[str]
    created_at: datetime

# Embedding Schemas
class EmbeddingCreate(BaseModel):
    paper_id: int
    section_id: Optional[int] = None
    embedding: List[float]
    type: TypeEnum
    model_name: str

    model_config = {"protected_namespaces": ()}

class EmbeddingUpdate(BaseModel):
    embedding: Optional[List[float]] = None
    
class EmbeddingResponse(BaseModel):
    id: int
    paper_id: int
    section_id: Optional[int]
    embedding: List[float]
    type: str
    model_name: str
    created_at: datetime

    model_config = {"protected_namespaces": ()}

# RecommendationRun Schemas
class RecommendationRunCreate(BaseModel):
    profile_id: Optional[int] = None
    user_id: int
    user_corpus_id: int
    ref_corpus_id: int
    threshold: Optional[float] = None
    method: Optional[str] = None
    total_papers_fetched: Optional[int] = 0
    target_date: Optional[date] = None

class RecommendationRunResponse(BaseModel):
    id: int
    profile_id: Optional[int]
    user_id: int
    user_corpus_id: int
    ref_corpus_id: int
    threshold: Optional[float]
    method: Optional[str]
    total_papers_fetched: Optional[int]
    target_date: Optional[date]
    created_at: datetime

# Recommendation Schemas
class RecommendationCreate(BaseModel):
    run_id: int
    paper_id: int
    score: float
    rank: int
    summary: Optional[str] = None

class RecommendationUpdate(BaseModel):
    score: Optional[float] = None
    rank: Optional[int] = None
    summary: Optional[str] = None

class RecommendationResponse(BaseModel):
    id: int
    run_id: int
    paper_id: int
    score: float
    rank: int
    summary: Optional[str]
    created_at: datetime

class VectorSearchRequest(BaseModel):
    embedding: List[float]
    corpus_id: Optional[int] = None
    limit: int = 10
    threshold: float = 0.5

# ProfileRecommendation Schemas
class ProfileRecommendationCreate(BaseModel):
    profile_id: int
    recommendation_id: int

class ProfileRecommendationResponse(BaseModel):
    id: int
    profile_id: int
    recommendation_id: int
    created_at: datetime

# EmailLog Schemas
class EmailLogCreate(BaseModel):
    user_id: int
    profile_id: Optional[int] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    status: StatusEnum = StatusEnum.sent

class EmailLogResponse(BaseModel):
    id: int
    user_id: int
    profile_id: Optional[int]
    subject: Optional[str]
    body: Optional[str]
    sent_at: datetime
    status: str

# ProcessingRun Schemas
class ProcessingRunCreate(BaseModel):
    run_type: str
    category: Optional[str] = None
    status: str = "started"
    papers_processed: int = 0

class ProcessingRunUpdate(BaseModel):
    status: Optional[str] = None
    papers_processed: Optional[int] = None
    error_message: Optional[str] = None

class ProcessingRunResponse(BaseModel):
    id: int
    run_type: str
    category: Optional[str]
    status: str
    papers_processed: int
    error_message: Optional[str]
    started_at: datetime
    completed_at: Optional[datetime]