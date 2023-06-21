from setuptools import find_namespace_packages, setup

setup(
    name="yaada-weaviate",
    version="0.0.1",
    description="YAADA weaviate package.",
    install_requires=[
        "yaada-core>=6.1.0",
        "weaviate-client>=3.15.6",
    ],
    python_requires=">=3.8.0",
    packages=find_namespace_packages(),
    scripts=[],
    include_package_data=True,
)
