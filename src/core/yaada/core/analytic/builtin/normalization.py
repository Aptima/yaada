# Copyright (c) 2022 Aptima, Inc.
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

import datetime

import dateparser
import dateutil.parser

from yaada.core import utility
from yaada.core.analytic import YAADAPipelineProcessor


class DateNormalizer(YAADAPipelineProcessor):
    def process(self, context, parameters, doc):
        source = parameters["source"]
        target = parameters["target"]
        fuzzy = parameters.get("fuzzy", True)
        date_formats = utility.listify_parameter_values(
            parameters.get("date_formats", [])
        )
        if source in doc:
            ts = None
            for f in date_formats:
                try:
                    ts = datetime.strptime(doc[source], f)
                    if ts is not None:
                        break
                except ValueError:
                    pass
            if ts is None:
                try:
                    ts = dateutil.parser.parse(doc[source])
                except ValueError:
                    pass
            if ts is None and fuzzy:
                ts = dateparser.parse(doc[source])

            doc[target] = ts

        return doc
