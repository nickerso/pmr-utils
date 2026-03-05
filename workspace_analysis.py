import logging
from wordcloud import WordCloud
import matplotlib.pyplot as plt
from pathlib import Path
from pmr_cache import PMRCache
from utils import find_in_dict, generate_keywords
from collections import Counter

# ==============================================================================
# Module-level logger
# (each module in your project should do this — they all feed into the
#  root "pmr" logger that gets configured once in main())
# ==============================================================================

import logging
log = logging.getLogger("pmr.workspace_analysis")


def top_keywords(keywords: list[str], n: int = 10) -> list[tuple[str, int]]:
    """Return the top N most common keywords and their counts."""
    counter = Counter(keywords)
    return counter.most_common(n)


def plot_top_keywords(keywords: list[str], n: int = 10, title: str = None, save_path: Path = None):
    results = top_keywords(keywords, n)
    labels  = [kw for kw, _ in results]
    counts  = [ct for _, ct in results]

    plt.figure(figsize=(8, 4))
    plt.barh(labels[::-1], counts[::-1])  # reverse so #1 is at the top
    plt.xlabel("Occurrences")
    if title:
        plt.title(title)
    else:
        plt.title(f"Top {n} Keywords")
    plt.tight_layout()
    if save_path:
        if save_path.exists():
            log.warning(f"Top keywords plot file already exists at {save_path}, it will be overwritten.")
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.show()


def plot_keyword_cloud(keywords: list[str], title: str = None, save_path: Path = None):
    combined_text = " ".join(keywords)
    # Generate a word cloud
    wordcloud = WordCloud(width=1600, height=1200, background_color='black', colormap='rainbow').generate(combined_text)
    # Display the word cloud
    plt.figure(figsize=(10, 8))
    plt.imshow(wordcloud, interpolation='bilinear')
    plt.axis('off')
    if save_path:
        if save_path.exists():
            log.warning(f"Keyword cloud file already exists at {save_path}, it will be overwritten.")
        plt.savefig(save_path, dpi=300, bbox_inches='tight', transparent=True)
    plt.show()

    

def workspace_analysis(cache: PMRCache, exposures_only: bool = False, max_keywords: int = 20, keyword_cloud: bool = False) -> int:
    workspaces = cache.list_workspaces()
    log.info(f'There are {len(workspaces)} workspaces in the cache')
    if exposures_only:
        log.info('Analyzing only exposures (not all workspace information)')    

    # these lists come from information in the exposures, so they will be the same regardless of whether we're analyzing exposures only or all workspace information
    semantic_keywords = []
    citations = []
    filetypes = []
    workspace_texts = []
    for w in workspaces:
        # build a combined text string for keyword extraction (if needed)
        if w.title and w.title != "":
            workspace_texts.append(w.title)
        if w.description and w.description != "":
            workspace_texts.append(w.description)

        if w.latest_exposure:
            links = w.latest_exposure['links']
            for l in links:
                keyword_pairs = find_in_dict(l, 'keywords')
                if keyword_pairs:
                    for kw in keyword_pairs:
                        semantic_keywords.append(kw[1])

                citation_id = find_in_dict(l, 'citation_id')
                if citation_id:
                    citations.append(citation_id)

                file_type = find_in_dict(l, 'file_type')
                if file_type:
                    filetypes.append(file_type)

    # report on the information we found in the exposure metadata (this will be the same regardless of whether we're analyzing exposures only or all workspace information)
    print(f'Exposure metadata summary:')
    citation_set = set(citation.lower() for citation in citations)
    print(f'- There are {len(citations)} citations in exposure metadata, consisting of {len(citation_set)} unique values.')
    
    filetype_set = set(filetypes)
    print(f'- There are {len(filetypes)} files in exposure metadata with their type defined, consisting of {len(filetype_set)} unique values.')
    for ft in filetype_set:
        print(f'-- {ft}: {filetypes.count(ft)} files')

    semantic_keyword_set = set(semantic_keywords)
    print(f'- There are {len(semantic_keywords)} semantic keywords in exposure metadata, consisting of {len(semantic_keyword_set)} unique values.')
    counted_semantic_keywords = top_keywords(semantic_keywords, n=max_keywords)
    print(f'- The top {max_keywords} most common semantic keywords in exposure metadata are:')
    for rank, (keyword, count) in enumerate(counted_semantic_keywords, start=1):
        print(f'-- {rank}. {keyword}: {count} occurrences')
    plot_top_keywords(semantic_keywords, n=max_keywords, title=f'Top {max_keywords} Semantic Keywords in Exposure Metadata', save_path=cache.base_folder / "top_semantic_keywords.png")

    if not exposures_only:
        # If we're not just analyzing exposures, we can also extract keywords from the combined text
        workspace_keywords = generate_keywords(workspace_texts, top_n=max_keywords)
        counted_workspace_keywords = top_keywords(workspace_keywords, n=max_keywords)
        print(f'- The top {max_keywords} most common keywords in workspace text are:')
        for rank, (keyword, count) in enumerate(counted_workspace_keywords, start=1):
            print(f'-- {rank}. {keyword}: {count} occurrences')
        plot_top_keywords(workspace_keywords, n=max_keywords, title=f'Top {max_keywords} Keywords in Workspace Text', save_path=cache.base_folder / "top_workspace_keywords.png")

    if keyword_cloud:
        plot_keyword_cloud(semantic_keywords, title='Semantic Keyword Cloud from Exposure Metadata', save_path=cache.base_folder / "exposure_keyword_cloud.png")
        if not exposures_only:
            plot_keyword_cloud(workspace_keywords, title='Keyword Cloud from Workspace Text', save_path=cache.base_folder / "workspace_keyword_cloud.png")
            combined_keywords = semantic_keywords + workspace_keywords
            plot_keyword_cloud(combined_keywords, title='Combined Keyword Cloud from Workspace Text and Exposure Metadata', save_path=cache.base_folder / "combined_keyword_cloud.png")

    return 0