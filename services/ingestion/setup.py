"""
VESPER Data Ingestion Service
Setup configuration for the data ingestion service.
"""
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="vesper-ingestion",
    version="0.1.0",
    author="VESPER Team",
    description="Data ingestion service for VESPER platform",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/vesper/vesper-ingestion",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.10",
    install_requires=[
        "requests>=2.31.0",
        "boto3>=1.28.0",
        "pydantic>=2.0.0",
        "python-dotenv>=1.0.0",
        "structlog>=23.1.0",
        "tenacity>=8.2.0",
        "click>=8.1.0",
        "httpx>=0.24.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
            "pytest-asyncio>=0.21.0",
            "black>=23.7.0",
            "ruff>=0.0.286",
            "mypy>=1.5.0",
            "types-requests",
        ],
    },
    entry_points={
        "console_scripts": [
            "vesper-ingest=vesper_ingestion.cli:cli",
        ],
    },
)
