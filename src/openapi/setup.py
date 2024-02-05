# Copyright (c) 2023 Aptima, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

from setuptools import find_namespace_packages, setup

setup(
    name="yaada-openapi",
    version="7.0.0",
    packages=find_namespace_packages(),
    description="",
    long_description="",
    author="Gabriel Ganberg",
    author_email="ganberg@aptima.com",
    python_requires=">=3.8.0",
    zip_safe=False,
    scripts=[
        "yaada/openapi/entrypoints/yaada-openapi.py",
    ],
    licence="MIT License",
    install_requires=["connexion[swagger-ui]<3", "flask", "flask-cors"],
    include_package_data=True,
)
