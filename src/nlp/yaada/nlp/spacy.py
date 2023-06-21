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

import logging
import random

import spacy
from spacy.util import compounding, minibatch

from yaada.core import default_log_level
from yaada.core.analytic import YAADAPipelineProcessor
from yaada.core.analytic.model import ModelBase
from yaada.nlp.utils import ensure_spacy_model

logger = logging.getLogger(__name__)
logger.setLevel(default_log_level)


class SpacyLanguageModel(ModelBase):
    def __init__(self, model_instance_id, base_model=None):
        super().__init__(model_instance_id)
        self.nlp = None
        self.base_model = base_model  # Specify spacy stock model eg: en_core_web_md

    def save_artifacts(self, path):
        artifact_dir = self.make_artifact_dir(path, artifact_type="LanguageModel")
        self.nlp.to_disk(artifact_dir)

    def load_artifacts(self, path):
        artifact_dir = self.get_artifact_dir(path, artifact_type="LanguageModel")
        self.nlp = spacy.load(artifact_dir)

    # train_data = [("Feature text/span", {entities: (start_char, end_char, entity_label)}), ...]
    def build(
        self,
        train_data,
        n_iter=100,
        drop=0.5,
        batch_size_min=4.0,
        batch_size_max=32.0,
        batch_size_compound=1.001,
    ):
        logging.info(
            f"Training spacy language model: {self.instance_id}, starting with base model: {self.base_model}..."
        )
        logging.info(f"Num iterations: {n_iter} Dropout rate: {drop}")
        logging.info(
            f"Batch min_size: {batch_size_min}, Batch max_size: {batch_size_max}, Batch size compounding factor: {batch_size_compound}"
        )

        if self.nlp is None:
            if self.base_model is None:
                self.nlp = spacy.blank("en")
            else:
                ensure_spacy_model(self.base_model)
                self.nlp = spacy.load(self.base_model)

        if "ner" in self.nlp.pipe_names:
            ner = self.nlp.get_pipe("ner")
        else:
            ner = self.nlp.create_pipe("ner")
            self.nlp.add_pipe(ner, last=True)

        for _, annotations in train_data:
            for ent in annotations.get("entities"):
                ner.add_label(ent[2])

        pipe_exceptions = ["ner", "trf_wordpiecer", "trf_tok2vec"]
        other_pipes = [
            pipe for pipe in self.nlp.pipe_names if pipe not in pipe_exceptions
        ]
        with self.nlp.disable_pipes(*other_pipes):
            if self.base_model is None:
                self.nlp.begin_training()

            for i in range(n_iter):
                random.shuffle(train_data)
                losses = {}
                batches = minibatch(
                    train_data,
                    size=compounding(
                        batch_size_min, batch_size_max, batch_size_compound
                    ),
                )
                for batch in batches:
                    texts, annotations = zip(*batch)
                    self.nlp.update(
                        texts,
                        annotations,
                        drop=drop,
                        losses=losses,
                    )
                logging.info(f"Iteration {i} Losses:  {losses}")

    def get_nlp(self):
        return self.nlp


_nlp = None


def spacy_nlp():
    global _nlp
    if _nlp is None:
        lan_model = "en_core_web_md"
        ensure_spacy_model(lan_model)
        logging.info(f"loading spacy model: {lan_model}")
        _nlp = spacy.load(lan_model)
    return _nlp


class SpacyNER(YAADAPipelineProcessor):
    """This processor uses the popular spaCy NLP library to extract named entities. The following pipeline example shows configuration for extracting "PERSON","ORG","DATE","LOC", and "GPE" references from the `content` field and storing the result in the `refs` field.


    .. code-block:: python

        {
            name=yaada.analytic.builtin.spacy.SpacyNER
            parameters {
            source=content
            target=refs
            include_labels=["PERSON","ORG","DATE","LOC","GPE"]
            }
        }
    """

    def init(self, context, parameters):
        self.nlp = None
        if "lang_model_instance_id" in parameters:
            modelmanager = context.get_model_manager()
            model = modelmanager.load_model_instance(
                SpacyLanguageModel, parameters["lang_model_instance_id"]
            )
            if model is not None:
                self.nlp = model.get_nlp()
        if self.nlp is None:
            self.nlp = spacy_nlp()
        logging.info("SpacyNER:initialized")

    def process(self, context, parameters, doc):
        source = parameters["source"]
        target = parameters["target"]
        recompute = parameters.get("recompute", False)
        if not recompute and target in doc:
            context.status["skipped"] = True
            context.status["message"] = f"'{target}' property already exists."
            return doc
        content = doc.get(source, None)

        if content is not None:
            sdoc = self.nlp(content)
            ner = []
            for ent in sdoc.ents:
                if (
                    "include_labels" not in parameters
                    or ent.label_ in parameters["include_labels"]
                ):
                    ner.append(
                        {
                            "label": ent.label_,
                            "start_char": ent.start_char,
                            "end_char": ent.end_char,
                            "text": ent.text,
                            "source": self.__class__.__name__,
                            "source_path": source,
                        }
                    )
            if target not in doc or recompute:
                doc[target] = []
            doc[target].extend(ner)
            context.status["extracted_count"] = len(ner)
        return doc
