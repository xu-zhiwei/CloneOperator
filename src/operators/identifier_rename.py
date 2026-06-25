"""O1 - Identifier Renaming.

Call ``IdentifierRename(...)(code, k=n)`` to rename local identifiers using
WordNet or CodeBERT candidates. ``rename_similarity`` sets the similarity limit.
"""

from .base_operator import BaseOperator

from tree_sitter import Language, Parser
import tree_sitter_java as tsjava

import spacy
import re

from transformers import AutoTokenizer, AutoModel
import torch
import random
from nltk.corpus import wordnet, words as nltk_words


_JAVA_KEYWORDS: frozenset = frozenset({
    "abstract", "assert", "boolean", "break", "byte", "case", "catch", "char",
    "class", "const", "continue", "default", "do", "double", "else", "enum",
    "extends", "final", "finally", "float", "for", "goto", "if", "implements",
    "import", "instanceof", "int", "interface", "long", "native", "new",
    "package", "private", "protected", "public", "return", "short", "static",
    "strictfp", "super", "switch", "synchronized", "this", "throw", "throws",
    "transient", "try", "var", "void", "volatile", "while",
    "true", "false", "null",
})


class IdentifierRename(BaseOperator):

    def __init__(
        self,
        token_vocab=None,
        model_name="microsoft/codebert-base",
        word_len=3,
        top_k_syn=0.5,
        rename_similarity=0.5,
        whitening_kernel_size=256,
        seed=42,
    ):
        # Set random seeds for reproducibility
        random.seed(seed)
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)

        self.token_vocab: list = token_vocab
        self.model_name = model_name
        self.word_len = word_len
        self.top_k_syn = top_k_syn
        self.rename_similarity = rename_similarity

        self.tokenizer: AutoTokenizer = None
        self.model: AutoModel = None
        self._load_encoder()

        self.vocab_embeddings = None
        self._whitening_mu = None
        self._whitening_W = None
        self.whitening_kernel_size = whitening_kernel_size
        self._load_vocab_embeddings()

        self.excluded_identifiers = {
            # Java keywords
            "public",
            "static",
            "void",
            "int",
            "class",
            # Common standard library identifiers
            "System",
            "out",
            "println",
            "main",
            # Other identifiers to exclude
            "String",
            "args",
        }

        self.excluded_tokens = {"<unk>", "<sep>", "<cls>", "<pad>", "<mask>"}
        self.lemma_analyzer = spacy.load("en_core_web_sm")
        self.english_words = set(w.lower() for w in nltk_words.words())

    def __call__(self, code, k=1):
        modified_code = code
        for _ in range(k):
            modified_code = self.operate(modified_code)[0]
        return modified_code

    def operate(self, code):
        # Convert code to bytearray for mutable processing
        code_bytes = bytearray(code.encode("utf-8"))
        tree = self._parse_code(code_bytes)
        local_identifiers = self._extract_local_identifiers(tree, code_bytes)
        recommendations = self._recommend_identifier_names(local_identifiers)
        code_bytes = self._rename_identifiers(
            tree, code_bytes, recommendations, local_identifiers
        )
        return code_bytes.decode("utf-8"), recommendations

    def _parse_code(self, code_bytes):
        # Use tree-sitter to parse the code and extract identifier names
        JAVA_LANGUAGE = Language(tsjava.language())
        parser = Parser(JAVA_LANGUAGE)
        tree = parser.parse(bytes(code_bytes))
        return tree

    def _extract_identifier_names(self, tree, code_bytes):
        # Traverse the AST to find identifier declarations and usages
        identifier_names = set()

        def traverse(node):
            # Extract all identifiers that are identifier names (both declarations and usages)
            if node.type == "identifier":
                name = code_bytes[node.start_byte : node.end_byte].decode("utf-8")
                if name not in self.excluded_identifiers:
                    identifier_names.add(name)

            for child in node.children:
                traverse(child)

        traverse(tree.root_node)

        return list(sorted(identifier_names))

    def _extract_local_identifiers(self, tree, code_bytes):
        """Extract only local variables and parameters that can be safely renamed.

        This includes:
        - Variable declarators (local variables)
        - Formal parameters (function arguments)

        Excludes:
        - Method names in method declarations
        - Method names in method invocations
        - Class names
        - Type references
        """
        local_identifiers = set()

        def traverse(node):
            # Variable declarators: int x = 5; -> extract "x"
            if node.type == "variable_declarator":
                for child in node.children:
                    if child.type == "identifier":
                        name = code_bytes[child.start_byte : child.end_byte].decode(
                            "utf-8"
                        )
                        if name not in self.excluded_identifiers:
                            local_identifiers.add(name)
                        break  # Only the first identifier is the variable name

            # Formal parameters: (int param1, String param2) -> extract identifiers
            elif node.type == "formal_parameter":
                for child in node.children:
                    if child.type == "identifier":
                        name = code_bytes[child.start_byte : child.end_byte].decode(
                            "utf-8"
                        )
                        if name not in self.excluded_identifiers:
                            local_identifiers.add(name)
                        break  # Only the last identifier is the parameter name

            # Catch formal parameter in enhanced for loops
            elif node.type == "enhanced_for_statement":
                # Find the variable declarator in enhanced for loops
                for child in node.children:
                    if child.type == "variable_declarator":
                        for subchild in child.children:
                            if subchild.type == "identifier":
                                name = code_bytes[
                                    subchild.start_byte : subchild.end_byte
                                ].decode("utf-8")
                                if name not in self.excluded_identifiers:
                                    local_identifiers.add(name)
                                break

            for child in node.children:
                traverse(child)

        traverse(tree.root_node)
        return list(sorted(local_identifiers))

    def _recommend_identifier_names(self, identifier_names):
        # Get tokens for each identifier name
        tokens = set()
        for identifier_name in identifier_names:
            identifier_tokens = self._convert_identifier_name_to_tokens(identifier_name)
            tokens.update(identifier_tokens)
        tokens = list(tokens)

        # Get token embeddings and track which tokens have valid embeddings
        token_embeddings = []
        tokens_with_embeddings = []
        for token in tokens:
            encoded = self.tokenizer(
                token, add_special_tokens=False, return_tensors="pt"
            )
            input_ids = encoded["input_ids"].to(self.model.device)
            if input_ids.numel() == 0:
                continue

            subword_embeddings = self.model.embeddings.word_embeddings(
                input_ids
            ).detach()
            token_embedding = subword_embeddings.mean(dim=1).squeeze(0)
            token_embeddings.append(token_embedding)
            tokens_with_embeddings.append(token)

        if not token_embeddings:
            return {}

        raw_token_embeddings = torch.stack(token_embeddings, dim=0)

        # Apply the same whitening transform used for vocab embeddings
        token_embeddings_whitened = (
            raw_token_embeddings - self._whitening_mu.to(raw_token_embeddings.device)
        ) @ self._whitening_W.to(raw_token_embeddings.device)

        # Use cosine similarity in the whitened space
        token_emb_norm = torch.nn.functional.normalize(
            token_embeddings_whitened, p=2, dim=-1
        )
        vocab_emb_norm = torch.nn.functional.normalize(
            self.vocab_embeddings, p=2, dim=-1
        )
        similarities = torch.matmul(token_emb_norm, vocab_emb_norm.T)

        # Sort similarities in descending order for each token
        sorted_similarities, sorted_indices = torch.sort(
            similarities, dim=-1, descending=True
        )
        sorted_similarities = sorted_similarities.cpu().tolist()
        sorted_indices = sorted_indices.cpu().tolist()

        used = set()
        recommendations = {}
        for i, token in enumerate(tokens_with_embeddings):
            # Skip tokens already assigned (same sub-token shared across identifiers)
            if token in recommendations:
                continue

            # Try WordNet synonyms (semantically reliable) if token is a valid English word
            if len(token) >= self.word_len and token.lower() in self.english_words:
                wordnet_rec = self._recommend_by_wordnet(token, used)
                if wordnet_rec:
                    recommendations[token] = (wordnet_rec, 1.0)
                    used.add(wordnet_rec)
                    continue

            # Fallback to whitened embedding similarity
            for recommend_token_id, recommend_similarity in zip(
                sorted_indices[i], sorted_similarities[i]
            ):
                if recommend_similarity < self.rename_similarity:
                    break

                recommend_token = self.token_vocab[recommend_token_id]
                recommend_token = (
                    recommend_token[1:]
                    if recommend_token.startswith("\u0120")
                    else recommend_token
                ).lower()

                if recommend_token in used or recommend_token in self.excluded_tokens:
                    continue
                if recommend_token in _JAVA_KEYWORDS:
                    continue
                if not re.fullmatch(r"[A-Za-z0-9_$]+", recommend_token):
                    continue
                if recommend_token[0].isdigit():
                    continue

                # Check if both tokens produce valid lemmas from spacy analysis
                recommend_doc = self.lemma_analyzer(recommend_token)
                token_doc = self.lemma_analyzer(token.lower())
                if (
                    len(recommend_doc) == 0
                    or len(token_doc) == 0
                    or (recommend_doc[0].lemma_ == token_doc[0].lemma_)
                ):
                    continue

                recommendations[token] = (recommend_token, recommend_similarity)
                used.add(recommend_token)
                break
            # If no valid match found, token is simply not added → original identifier preserved

        return recommendations

    def _rename_identifiers(self, tree, code_bytes, recommendations, local_identifiers):
        """Rename identifiers only if they are in the local_identifiers set."""
        replacements = []

        def traverse(node):
            if node.type == "identifier":
                old_name = code_bytes[node.start_byte : node.end_byte].decode("utf-8")
                # Only rename if this identifier is a declared local variable
                if old_name and old_name in local_identifiers:
                    old_tokens = self._convert_identifier_name_to_tokens(old_name)
                    first_lower = old_name[0].islower()
                    new_tokens = []
                    for old_token in old_tokens:
                        if old_token in recommendations:
                            new_token, similarity = recommendations[old_token]
                            new_tokens.append(new_token)
                        else:
                            new_tokens.append(old_token)
                    new_name = self._convert_tokens_to_identifier_name(
                        new_tokens, first_lower=first_lower
                    )
                    replacements.append(
                        (
                            node.start_byte,
                            node.end_byte,
                            new_name.encode("utf-8"),
                        )
                    )

            for child in node.children:
                traverse(child)

        traverse(tree.root_node)

        # Apply replacements from right to left so original byte ranges stay valid.
        for start_byte, end_byte, new_name_bytes in sorted(
            replacements, key=lambda item: item[0], reverse=True
        ):
            code_bytes[start_byte:end_byte] = new_name_bytes

        return code_bytes

    def _recommend_by_wordnet(self, token: str, used: set) -> str | None:
        """Find a WordNet synonym for token that hasn't been used yet."""
        synsets = wordnet.synsets(token.lower())
        allowed_syn_count = max(1, int(round(len(synsets) * self.top_k_syn, 0)))
        for syn in synsets[:allowed_syn_count]:  # Limit to top K synonyms
            candidate = syn.name().split(".")[0]
            if "_" in candidate:
                candidate = self._convert_tokens_to_identifier_name(
                    candidate.split("_"), first_lower=token[0].islower()
                )
            if (
                candidate != token.lower()
                and candidate not in used
                and candidate not in _JAVA_KEYWORDS
                and candidate in self.token_vocab
                and self.lemma_analyzer(candidate)[0].lemma_
                != self.lemma_analyzer(token.lower())[0].lemma_
            ):
                return candidate

    def _load_encoder(self):
        # Select CUDA device with the most free memory
        if torch.cuda.is_available():
            device = None
            for i in range(torch.cuda.device_count()):
                if (
                    device is None
                    or torch.cuda.get_device_properties(i).total_memory
                    > torch.cuda.get_device_properties(device).total_memory
                ):
                    device = i
            device = torch.device(f"cuda:{device}")
        else:
            device = torch.device("cpu")

        tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        model = AutoModel.from_pretrained(self.model_name).to(device)

        self.tokenizer = tokenizer
        self.model = model

    def _load_vocab_embeddings(self):
        if self.token_vocab is None:
            self.token_vocab = list(self.tokenizer.get_vocab().keys())
            self.token_vocab.sort(
                key=lambda token: self.tokenizer.convert_tokens_to_ids(token)
            )

        token_ids = self.tokenizer.convert_tokens_to_ids(self.token_vocab)
        token_ids = torch.tensor(token_ids, dtype=torch.long).to(self.model.device)
        raw_embeddings = self.model.embeddings.word_embeddings(token_ids).detach()
        self.vocab_embeddings = self._compute_whitening(raw_embeddings)

    def _compute_whitening(self, embeddings: torch.Tensor) -> torch.Tensor:
        """Apply PCA whitening to reduce anisotropy in embedding space."""
        mu = embeddings.mean(dim=0, keepdim=True)
        centered = embeddings - mu
        cov = centered.T @ centered / centered.shape[0]
        # eigh is numerically stable for symmetric covariance matrices
        eigenvalues, eigenvectors = torch.linalg.eigh(cov)
        # eigh returns ascending order; reverse for descending
        eigenvalues = eigenvalues.flip(0)
        eigenvectors = eigenvectors.flip(1)
        k = min(self.whitening_kernel_size, eigenvectors.shape[1])
        W = eigenvectors[:, :k] / eigenvalues[:k].clamp(min=1e-8).sqrt()
        self._whitening_mu = mu
        self._whitening_W = W
        return centered @ W

    @staticmethod
    def _convert_identifier_name_to_tokens(name):
        # detect snake case or camel case and split into tokens
        if "_" in name:
            return name.split("_")
        elif any(char.isupper() for char in name):
            return "".join(
                [
                    (
                        char.lower()
                        if char.islower() or (i == 0 and char.isupper())
                        else "_" + char.lower()
                    )
                    for i, char in enumerate(name)
                ]
            ).split("_")
        else:
            return [name]

    @staticmethod
    def _convert_tokens_to_identifier_name(tokens, first_lower=True):
        # Convert list of tokens back to identifier name (using camel case)
        return "".join(
            token.capitalize() if (i == 0 and not first_lower) or i > 0 else token
            for i, token in enumerate(tokens)
        )
