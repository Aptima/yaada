from setuptools import find_packages, setup

setup(
    name="yaada-neo4j",
    version="0.1",
    description="Neo4J API for YAADA",
    install_requires=["yaada-core>=6.1.0", "neo4j==5.6.0"],
    python_requires=">=3.8.0",
    packages=find_packages(),
    scripts=[],
)
