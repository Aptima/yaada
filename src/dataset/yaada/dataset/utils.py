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

import tempfile

import requests
from tqdm import tqdm


def download_to_temp(url):
    tf = tempfile.NamedTemporaryFile()
    print(f'downloading "{url}" to {tf.name}')
    r = requests.get(url, stream=True)
    # Estimates the number of bar updates
    block_size = 4096
    file_size = int(r.headers.get("Content-Length"))
    # num_bars = math.ceil(file_size / block_size)
    bar = tqdm(total=file_size, unit="iB", unit_scale=True)

    for data in r.iter_content(block_size):
        bar.update(len(data))
        tf.write(data)
    tf.seek(0)
    return tf
