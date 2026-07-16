from setuptools import setup, find_packages
import os

"""
Installation Commands:
----------------------

Basic installation (core dependencies only):
    pip install -e .

Install with specific extras:
    pip install -e ".[dev]"          # Development tools
    pip install -e ".[test]"         # Testing dependencies
    pip install -e ".[cuda]"         # GPU support (faiss-gpu)
    pip install -e ".[qdrant]"       # Qdrant vector database
    pip install -e ".[s3]"           # arXiv S3 bulk download
    pip install -e ".[llama]"        # LLaMA summarization
    pip install -e ".[production]"   # Production deployment tools

Install multiple extras:
    pip install -e ".[dev,test]"
    pip install -e ".[dev,test,llama]"

Install ALL optional dependencies (excludes CUDA - install separately if needed):
    pip install -e ".[all]"

For GPU support (RTX 5070 Ti), install PyTorch with CUDA first, then manually install faiss-gpu:
    pip install torch==2.5.1 --index-url https://download.pytorch.org/whl/cu124
    pip install faiss-gpu
    pip install -e ".[all]"
 
Post-installation steps:
    python -c "import nltk; nltk.download('punkt')"
"""

def read_readme():
    readme_path = os.path.join(os.path.dirname(__file__), 'README.md')
    if os.path.exists(readme_path):
        with open(readme_path, 'r', encoding='utf-8') as f:
            return f.read()
    return "A database-integrated preprint recommendation bot"

# Define extras_require first
extras_require = {
    # Development tools
    "dev": [
        "setuptools>=65.0.0",
        "wheel>=0.38.0",
        "pytest>=8.0.0",
        "pytest-asyncio>=0.23.0",
        "black>=24.0.0",
        "flake8>=7.0.0",
        "mypy>=1.8.0",
        "isort>=5.13.0",
    ],
    
    # GPU support - NOTE: Install manually if pip install fails
    # pip install faiss-gpu (requires CUDA toolkit)
    "cuda": [
        # Commented out to prevent installation errors on systems without CUDA
        # Manually install with: pip install faiss-gpu
        # "faiss-gpu>=1.7.4",
    ],
    
    # Alternative vector database
    "qdrant": [
        "qdrant-client>=1.12.1",
    ],
    
    # arXiv S3 bulk download
    "s3": [
        "boto3>=1.34.0",
        "botocore>=1.34.0",
    ],
    
    # LLM-based summarization
    "llama": [
        "llama-cpp-python>=0.1.83",
    ],
    
    # Production deployment
    "production": [
        "gunicorn>=21.2.0",
        "redis>=5.0.0",
        "celery>=5.3.0",
    ],
    
    # Testing
    "test": [
        "pytest>=8.0.0",
        "pytest-asyncio>=0.23.0",
        "pytest-cov>=4.1.0",
        "faker>=22.0.0",
    ],
}

# Create 'all' extra that includes everything except CUDA (install manually)
all_extras = set()
for key, extra_deps in extras_require.items():
    if key != "cuda":  # Skip CUDA dependencies in 'all'
        all_extras.update(extra_deps)
extras_require['all'] = list(all_extras)

setup(
    name="preprint_bot",
    version="1.1.0.dev0",
    description="A database-integrated preprint recommendation bot with FastAPI backend and PostgreSQL storage",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    author="Syracuse University",
    author_email="ospo@syr.edu",
    url="https://github.com/SyracuseUniversity/preprint-bot",
    python_requires=">=3.10",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    
    # Core dependencies
    install_requires=[
        # arXiv and PDF processing
        "requests>=2.31.0",
        "feedparser>=6.0.11",
        "lxml>=5.3.0",
        
        # progress bars
        "tqdm>=4.66.0",
        
        # Machine Learning and Embeddings
        "numpy>=1.26.0,<2.0.0",
        "sentence-transformers>=2.6.0",
        "transformers>=4.41.0,<5.0.0",
        "torch>=2.5.0",
        "nltk>=3.9",
        
        # Similarity Search (CPU version - works everywhere)
        "faiss-cpu>=1.7.4",
        "scikit-learn>=1.5.0",
        
        # FastAPI and Web Server
        "fastapi>=0.109.0",
        "uvicorn[standard]>=0.27.0",
        "httpx>=0.27.0",
        
        # Database
        "asyncpg>=0.29.0",
        "psycopg2-binary>=2.9.9",
        
        # Data Validation and Settings
        "pydantic>=2.5.0,<3.0.0",
        "pydantic-settings>=2.1.0",
        "email-validator>=2.0.0",
        
        # Environment and Configuration
        "python-dotenv>=1.0.0",
    ],
    
    extras_require=extras_require,
    
    # Console scripts
    entry_points={
        "console_scripts": [
            "preprint_bot=preprint_bot.pipeline:main",
        ],
    },
    
    include_package_data=True,
    
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Science/Research",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    
    zip_safe=False,
)