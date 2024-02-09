from setuptools import find_packages, setup

setup(
    name="{{cookiecutter.python_package}}",
    version="{{cookiecutter.project_version}}",
    description="{{cookiecutter.project_name}}",
    install_requires=[
        "yaada-core>={{cookiecutter.yaada_version}}",
        "yaada-nlp>={{cookiecutter.yaada_version}}",
        "yaada-openapi>={{cookiecutter.yaada_version}}",
        "yaada-webscraping>={{cookiecutter.yaada_version}}"
    ],
    python_requires=">=3.10",
    packages=find_packages(),
    scripts=[],
)
