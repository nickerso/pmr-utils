import logging
from wordcloud import WordCloud
import matplotlib.pyplot as plt
from pathlib import Path
from pmr_cache import PMRCache
from utils import find_in_dict, generate_keywords
from collections import Counter
import cellml
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm


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
    # plt.show()


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
    # plt.show()

    

def workspace_analysis(cache: PMRCache, exposures_only: bool = False, max_keywords: int = 20, keyword_cloud: bool = False,
                       check_cellml_models: bool = False) -> int:
    workspaces = cache.list_workspaces()
    log.info(f'There are {len(workspaces)} workspaces in the cache')
    if exposures_only:
        log.info('Analyzing only exposures (not all workspace information)')    

    # these lists come from information in the exposures, so they will be the same regardless of whether we're analyzing exposures only or all workspace information
    semantic_keywords = []
    citations = []
    filetypes = []
    workspace_texts = []
    exposed_cellml_models = []
    exposure_count = 0
    for w in workspaces:
        # build a combined text string for keyword extraction (if needed)
        if w.title and w.title != "":
            workspace_texts.append(w.title)
        if w.description and w.description != "":
            workspace_texts.append(w.description)

        if w.latest_exposure:
            exposure_count += 1
            links = w.latest_exposure['links']
            exposure_url = w.latest_exposure['href']
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
                    if check_cellml_models:
                        if file_type == "https://models.physiomeproject.org/filetype/cellml":
                            model_url = l.get('href')
                            log.debug(f'Found CellML model in exposure metadata: {model_url}')
                            commit_id = l.get('commit_id')
                            workspace_url = w.href
                            # construct the workspace URL with the commit ID to ensure we're looking at the correct version of the model
                            raw_cellml_url = model_url.replace(exposure_url, f'{workspace_url}/rawfile/{commit_id}').strip('/view')
                            log.debug(f'Constructed raw CellML URL: {raw_cellml_url}')
                            exposed_cellml_models.append(raw_cellml_url)

    # report on the information we found in the exposure metadata (this will be the same regardless of whether we're analyzing exposures only or all workspace information)
    print(f'Exposure metadata summary:')
    print(f'- There are {exposure_count} exposures')
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

    # analyse the CellML models we found in the exposures (if requested)
    parsed_models = []
    cellml_10_models = []
    cellml_11_models = []
    cellml_20_models = []
    valid_models = []
    models_with_imports = []
    resolveable_models = []
    resolved_and_valid_models = []
    executable_models = []
    if check_cellml_models:
        with logging_redirect_tqdm(loggers=[log]):
            for model_url in tqdm(exposed_cellml_models, desc="Checking CellML models"):
                log.info(f'Checking CellML model at URL: {model_url}')
                model, version = cellml.parse_remote_model(model_url, silent=True, strict_mode=False)
                if model is None:
                    # can't do anything
                    log.debug(f'Model {model_url} is invalid')
                    continue
                log.debug(f'{model_url} was parsed and is CellML version {version}')
                parsed_models.append(model_url)
                if version == "1.0":
                    cellml_10_models.append(model_url)
                elif version == "1.1":
                    cellml_11_models.append(model_url)
                else:
                    cellml_20_models.append(model_url)
                if cellml.validate_model(model) > 0:
                    continue
                valid_models.append(model_url)
                flat_model = model
                if model.hasUnresolvedImports():
                    models_with_imports.append(model_url)
                    # importer = cellml.resolve_remote_imports(model, model_url, strict_mode=False, logger=log)
                    # if model.hasUnresolvedImports():
                    #     log.debug(f'Model has unresolved imports after attempting to resolve remote imports')
                    #     continue
                    # resolveable_models.append(model_url)
                    # if cellml.validate_model(model) > 0:
                    #     log.warning('Validation issues found in model after resolving remote imports')
                    #     continue
                    # resolved_and_valid_models.append(model_url)
                    # log.debug('Model was parsed, resolved, and validated without any issues.')
                    # # need a flattened model for analysing
                    # flat_model = cellml.flatten_model(model, importer)
                analysed_model, error_count = cellml.analyse_model(flat_model, silent=True)
                if error_count != 0:
                    log.warning(f'Errors found when analysing the model: {model_url}')
                    continue
                # if cellml.generate_code(analysed_model, print_code=False):
                #     log.warning(f'Something went wrong trying to generate code for model: {model_url}')
                #     continue
                executable_models.append(model_url)
        print(f'- There are {len(exposed_cellml_models)} CellML models exposed in the metadata of the exposures.')
        print(f'-- {len(parsed_models)} are able to be parsed by libCellML')
        print(f'-- {len(valid_models)} are valid CellML models')
        print(f'-- {len(executable_models)} are able generate code for potential simulation')
        print(f'-- CellML Version:')
        print(f'-- -- {len(cellml_10_models)} CellML 1.0 models')
        print(f'-- -- {len(cellml_11_models)} CellML 1.1 models')
        print(f'-- -- {len(cellml_20_models)} CellML 2.0 models')
        print(f'-- {len(models_with_imports)} are models that have imports')
        print(f'-- -- {len(resolveable_models)} have imports which are resolvable')
        print(f'-- -- {len(resolved_and_valid_models)} are valid after resolving the imports')

    return 0