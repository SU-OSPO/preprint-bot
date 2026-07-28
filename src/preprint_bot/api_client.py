import httpx
from typing import List, Dict, Optional
import datetime

class APIClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8000"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=60.0)
    
    async def close(self):
        await self.client.aclose()
    
    
    async def create_user(self, email: str, name: Optional[str] = None) -> Dict:
        response = await self.client.post(
            f"{self.base_url}/users/",
            json={"email": email, "name": name}
        )
        response.raise_for_status()
        return response.json()
    
    async def get_user_by_email(self, email: str) -> Optional[Dict]:
        response = await self.client.get(f"{self.base_url}/users/")
        users = response.json()
        return next((u for u in users if u["email"] == email), None)
    
    async def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        try:
            response = await self.client.get(f"{self.base_url}/users/{user_id}")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise
    
    async def get_or_create_user(self, email: str, name: Optional[str] = None) -> Dict:
        user = await self.get_user_by_email(email)
        if user:
            return user
        return await self.create_user(email, name)
    
    
    async def create_profile(self, user_id: int, name: str, keywords: List[str],
                        categories: List[str] = None,  # ADD THIS PARAMETER
                        email_notify: bool = True, frequency: str = "weekly",
                        threshold: float = 0.6, top_x: int = 10) -> Dict:
        response = await self.client.post(
            f"{self.base_url}/profiles/",
            json={
                "user_id": user_id,
                "name": name,
                "keywords": keywords,
                "categories": categories or [],  # ADD THIS LINE
                "email_notify": email_notify,
                "frequency": frequency,
                "threshold": threshold,
                "top_x": top_x
            }
        )
        response.raise_for_status()
        return response.json()
    
    async def get_profile_by_name(self, user_id: int, name: str) -> Optional[Dict]:
        response = await self.client.get(f"{self.base_url}/profiles/")
        profiles = response.json()
        return next((p for p in profiles if p["user_id"] == user_id and p["name"] == name), None)
    
    async def get_profiles_by_user(self, user_id: int) -> List[Dict]:
        response = await self.client.get(f"{self.base_url}/profiles/")
        profiles = response.json()
        return [p for p in profiles if p["user_id"] == user_id]
    
    async def get_or_create_profile(self, user_id: int, name: str, keywords: List[str], 
                                categories: List[str] = None) -> Dict:  # ADD PARAMETER
        profile = await self.get_profile_by_name(user_id, name)
        if profile:
            return profile
        return await self.create_profile(user_id, name, keywords, categories)  # ADD ARGUMENT
    
    
    async def create_corpus(self, user_id: int, name: str, description: str = None) -> Dict:
        response = await self.client.post(
            f"{self.base_url}/corpora/",
            json={"user_id": user_id, "name": name, "description": description}
        )
        response.raise_for_status()
        return response.json()
    
    async def get_corpus_by_name(self, user_id: int, name: str) -> Optional[Dict]:
        response = await self.client.get(f"{self.base_url}/corpora/")
        corpora = response.json()
        return next((c for c in corpora if c["user_id"] == user_id and c["name"] == name), None)
    
    async def get_or_create_corpus(self, user_id: int, name: str, description: str = None) -> Dict:
        corpus = await self.get_corpus_by_name(user_id, name)
        if corpus:
            return corpus
        return await self.create_corpus(user_id, name, description)
    
    async def link_profile_corpus(self, profile_id: int, corpus_id: int):
        try:
            response = await self.client.post(
                f"{self.base_url}/profile-corpora/",
                json={"profile_id": profile_id, "corpus_id": corpus_id}
            )
            return response.status_code == 201
        except Exception:
            return False
    
    
    async def create_paper(self, corpus_id: int, arxiv_id: str, title: str, 
                        abstract: str, metadata: Dict, source: str = "arxiv",
                        processed_text_path: str = None, pdf_path: str = None,
                        submitted_date: datetime = None) -> Dict:  # ADD THIS PARAM
        paper_data = {
            "corpus_id": corpus_id,
            "arxiv_id": arxiv_id,
            "title": title,
            "abstract": abstract,
            "metadata": metadata,
            "source": source,
            "pdf_path": pdf_path,
            "submitted_date": submitted_date.isoformat() if submitted_date else None  # ADD THIS
        }
        
        response = await self.client.post(
            f"{self.base_url}/papers/",
            json=paper_data
        )
        response.raise_for_status()
        paper = response.json()
        
        if processed_text_path:
            await self.update_paper_processed_path(paper["id"], processed_text_path)
            paper["processed_text_path"] = processed_text_path
        
        return paper
    
    async def update_paper_processed_path(self, paper_id: int, path: str) -> Dict:
        response = await self.client.post(
            f"{self.base_url}/papers/{paper_id}/processed-text",
            params={"path": path}
        )
        response.raise_for_status()
        return response.json()
    
    async def get_paper_by_arxiv_id(self, arxiv_id: str) -> Optional[Dict]:
        response = await self.client.get(
            f"{self.base_url}/papers/",
            params={"arxiv_id": arxiv_id}
        )
        response.raise_for_status()
        papers = response.json()
        return papers[0] if papers else None
    
    async def get_paper_by_id(self, paper_id: int) -> Optional[Dict]:
        try:
            response = await self.client.get(f"{self.base_url}/papers/{paper_id}")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise
    
    async def update_paper(self, paper_id: int, **fields) -> Optional[Dict]:
        """Update a paper's fields (title, abstract, metadata, etc.)."""
        response = await self.client.put(
            f"{self.base_url}/papers/{paper_id}",
            json=fields
        )
        response.raise_for_status()
        return response.json()
    
    async def get_papers_by_corpus(self, corpus_id: int) -> List[Dict]:
        response = await self.client.get(f"{self.base_url}/papers/?corpus_id={corpus_id}")
        response.raise_for_status()
        return response.json()
    
    async def get_papers_needing_processing(self) -> List[Dict]:
        """Papers with a PDF but no sections extracted yet."""
        response = await self.client.get(f"{self.base_url}/papers/needing-processing")
        response.raise_for_status()
        return response.json()
    
    async def get_papers_needing_embeddings(self) -> List[Dict]:
        """Papers with sections but no abstract embedding yet."""
        response = await self.client.get(f"{self.base_url}/papers/needing-embeddings")
        response.raise_for_status()
        return response.json()
    
    
    async def create_section(self, paper_id: int, header: str, text: str) -> Dict:
        response = await self.client.post(
            f"{self.base_url}/sections/",
            json={
                "paper_id": paper_id,
                "header": header,
                "text": text
            }
        )
        response.raise_for_status()
        return response.json()
        
    async def get_sections_by_paper(self, paper_id: int) -> List[Dict]:
        response = await self.client.get(f"{self.base_url}/sections/?paper_id={paper_id}")
        response.raise_for_status()
        return response.json()
    
    
    async def create_embedding(self, paper_id: int, embedding: List[float], 
                              type: str, model_name: str, section_id: Optional[int] = None) -> Dict:
        response = await self.client.post(
            f"{self.base_url}/embeddings/",
            json={
                "paper_id": paper_id,
                "section_id": section_id,
                "embedding": embedding,
                "type": type,
                "model_name": model_name
            }
        )
        response.raise_for_status()
        return response.json()
    
    async def get_embeddings_by_corpus(self, corpus_id: int, type: str = None) -> List[Dict]:
        params = {"corpus_id": corpus_id}
        if type:
            params["type"] = type
        response = await self.client.get(
            f"{self.base_url}/embeddings/",
            params=params
        )
        response.raise_for_status()
        return response.json()
    
    async def get_embeddings_by_paper(self, paper_id: int, type: str = None) -> List[Dict]:
        params = {"paper_id": paper_id}
        if type:
            params["type"] = type
        response = await self.client.get(f"{self.base_url}/embeddings/", params=params)
        response.raise_for_status()
        return response.json()
    
    async def batch_create_embeddings(self, embeddings: List[Dict]) -> List[Dict]:
        response = await self.client.post(
            f"{self.base_url}/embeddings/batch",
            json=embeddings
        )
        response.raise_for_status()
        return response.json()
    
    async def create_summary(self, paper_id: int, mode: str, summary_text: str, summarizer: str) -> Dict:
        response = await self.client.post(
            f"{self.base_url}/summaries/",
            json={
                "paper_id": paper_id,
                "mode": mode,
                "summary_text": summary_text,
                "summarizer": summarizer
            }
        )
        response.raise_for_status()
        return response.json()
    
    
    async def create_recommendation_run(self, profile_id: int, user_id: int,
                                    user_corpus_id: int, ref_corpus_id: int,
                                    threshold: str, method: str, total_papers_fetched: int = 0,
                                    target_date=None) -> Dict:
        response = await self.client.post(
            f"{self.base_url}/recommendation-runs/",
            json={
                "profile_id": profile_id,
                "user_id": user_id,
                "user_corpus_id": user_corpus_id,
                "ref_corpus_id": ref_corpus_id,
                "threshold": threshold,
                "method": method,
                "total_papers_fetched": total_papers_fetched,
                "target_date": str(target_date) if target_date else None
            }
        )
        response.raise_for_status()
        return response.json()
    
    async def create_processing_run(self, run_type: str, category: Optional[str] = None,
                                    status: str = "started",
                                    papers_processed: int = 0) -> Dict:
        response = await self.client.post(
            f"{self.base_url}/processing-runs/",
            json={
                "run_type": run_type,
                "category": category,
                "status": status,
                "papers_processed": papers_processed,
            }
        )
        response.raise_for_status()
        return response.json()

    async def update_processing_run(self, run_id: int, status: Optional[str] = None,
                                    papers_processed: Optional[int] = None,
                                    error_message: Optional[str] = None) -> Dict:
        response = await self.client.patch(
            f"{self.base_url}/processing-runs/{run_id}",
            json={
                "status": status,
                "papers_processed": papers_processed,
                "error_message": error_message,
            }
        )
        response.raise_for_status()
        return response.json()
    
    async def create_recommendation(self, run_id: int, paper_id: int, 
                                   score: float, rank: int, summary: str = None) -> Dict:
        response = await self.client.post(
            f"{self.base_url}/recommendations/",
            json={
                "run_id": run_id,
                "paper_id": paper_id,
                "score": score,
                "rank": rank,
                "summary": summary
            }
        )
        response.raise_for_status()
        return response.json()
    
    async def get_recommendations_by_run(self, run_id: int) -> List[Dict]:
        response = await self.client.get(f"{self.base_url}/recommendations/?run_id={run_id}")
        response.raise_for_status()
        return response.json()
    
    async def get_recommendations_with_papers(self, run_id: int, limit: int = 50) -> List[Dict]:
        response = await self.client.get(
            f"{self.base_url}/recommendations/run/{run_id}/with-papers",
            params={"limit": limit}
        )
        response.raise_for_status()
        return response.json() 

    async def record_arxiv_stats(self, submission_date: str, category: str, total_papers: int):
        """Record arXiv fetch statistics"""
        response = await self.client.post(
            f"{self.base_url}/papers/arxiv-stats",
            params={
                "submission_date": submission_date,
                "category": category,
                "total_papers": total_papers
            }
        )
        response.raise_for_status()
        return response.json()

    async def get_arxiv_stats_for_date(self, date: str) -> Dict:
        """Get total papers for a specific date"""
        response = await self.client.get(f"{self.base_url}/papers/arxiv-stats/date/{date}")
        response.raise_for_status()
        return response.json()

    async def send_admin_alert(self, subject: str, detail: str) -> Dict:
        """Ask the API to email the configured admin about a pipeline failure."""
        response = await self.client.post(
            f"{self.base_url}/emails/admin-alert",
            json={"subject": subject, "detail": detail},
        )
        response.raise_for_status()
        return response.json()