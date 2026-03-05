import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from nltk.collocations import BigramAssocMeasures, BigramCollocationFinder
from nltk.collocations import TrigramAssocMeasures, TrigramCollocationFinder
import string

# Download required NLTK data (only needed once)
nltk.download('stopwords')
nltk.download('punkt')
nltk.download('punkt_tab')

# Common English stopwords (the, a, from, is, etc.)
STOPWORDS = set(stopwords.words('english'))
PMR_STOPWORDS = set([
    'model', 'models', 'modelling', 'modeling',
    'cellml', 'annotated', 'annotation', 'annotations',
    'sbml', 'biomodels', 'physiome', 'repository',
    'using', 'used', 'use', 'based', 'approach', 'approaches',
    'http', 'https', 'www', 'com', 'org', 'net', 'edu', 'gov',
    'available', 'workspace', 'workspaces', 'exposure', 'exposures',
    'data', 'dataset', 'datasets', 'file', 'files',
])
PMR_KNOWN_PHRASES = {
    ('bond', 'graph'),
    ('bond', 'graphs'),
    ('intervertebral', 'disc'),
    ('intervertebral', 'discs'),
    ('cardiac', 'cell'),
    ('cardiac', 'cells'),
    ('cardiac', 'myocyte'),
    ('cardiac', 'myocytes'),
    ('cardiac', 'electrophysiology'),
    ('cardiac', 'electrophysiological'),
    ('calcium', 'dynamics'),
    ('calcium', 'signaling'),
    ('calcium', 'signalling'),
    ('calcium', 'oscillations'),
    ('ca2+', 'dynamics'),
    ('ca2+', 'signaling'),
    ('ca2+', 'signalling'),
    ('ca2+', 'oscillations'),
    ('signaling', 'pathway'),
    ('signalling', 'pathway'),
    ('signal', 'transduction'),
    ('signal', 'transduction', 'pathway'),
    ('cell', 'cycle'),
    ('cell', 'cycling'),
}

# ==============================================================================
# Module-level logger
# (each module in your project should do this — they all feed into the
#  root "pmr" logger that gets configured once in main())
# ==============================================================================

import logging
log = logging.getLogger("pmr.utils")


def clean_tokens(text: str) -> list[str]:
    """Tokenize and remove stopwords/punctuation."""
    tokens = word_tokenize(text.lower())
    return [
        t for t in tokens
        if t not in STOPWORDS
        and t not in PMR_STOPWORDS
        and not t.isnumeric()
        and t not in string.punctuation
        and len(t) > 2
    ]


def find_collocations(texts: list[str], top_n: int = 10) -> tuple[list, list]:
    """
    Find the most common bigrams and trigrams across a list of texts.
    Needs a corpus of texts to find statistically meaningful collocations.
    """
    all_tokens = []
    log.debug(f"Finding collocations in {len(texts)} texts...")
    for text in texts:
        all_tokens.extend(clean_tokens(text))

    # Bigrams (2-word phrases)
    bigram_finder = BigramCollocationFinder.from_words(all_tokens)
    bigram_finder.apply_freq_filter(5)  # must appear at N times to be considered
    bigrams = bigram_finder.nbest(BigramAssocMeasures().pmi, top_n)

    # Trigrams (3-word phrases)
    trigram_finder = TrigramCollocationFinder.from_words(all_tokens)
    trigram_finder.apply_freq_filter(5) # must appear at N times to be considered
    trigrams = trigram_finder.nbest(TrigramAssocMeasures().pmi, top_n)

    return bigrams, trigrams



def extract_keywords(text: str, known_phrases: list[tuple]) -> list[str]:
    """
    Extract keywords, preserving known multi-word phrases as single tokens.
    """
    tokens = clean_tokens(text)
    keywords = []
    i = 0
    while i < len(tokens):
        # Try to match a trigram first, then bigram, then single token
        trigram = tuple(tokens[i:i+3])
        bigram  = tuple(tokens[i:i+2])

        if trigram in known_phrases:
            keywords.append(" ".join(trigram))
            i += 3
        elif bigram in known_phrases:
            keywords.append(" ".join(bigram))
            i += 2
        else:
            keywords.append(tokens[i])
            i += 1

    return keywords


def generate_keywords(texts: list[str], top_n: int = 10) -> list[str]:
    # bigrams, trigrams = find_collocations(texts, top_n)
    # known_phrases = set(bigrams + trigrams)
    # log.debug(f"Identified {len(known_phrases)} known phrases from collocation analysis:")
    known_phrases = PMR_KNOWN_PHRASES
    
    all_keywords = []
    for text in texts:
        keywords = extract_keywords(text, known_phrases)
        all_keywords.extend(keywords)
    return all_keywords


def find_in_dict(data, target_key):
    """
    Recursively search for a target key in a nested dictionary.

    Args:
        data (dict): The dictionary to search.
        target_key (str): The key to find.

    Returns:
        Any: The value associated with the target key if found, else None.
    """
    if isinstance(data, dict):
        for key, value in data.items():
            if key == target_key:
                return value
            # Recursive call if the value is a dict or list
            if isinstance(value, (dict, list)):
                result = find_in_dict(value, target_key)
                if result is not None:
                    return result
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, (dict, list)):
                result = find_in_dict(item, target_key)
                if result is not None:
                    return result
    return None


