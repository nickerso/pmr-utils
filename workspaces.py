import argparse
import json
import re
import pathlib
from urllib.request import Request, urlopen
from urllib.parse import urlparse
from git import Repo
from pmr_cache import PMRCache, Workspace
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

# ==============================================================================
# Module-level logger
# (each module in your project should do this — they all feed into the
#  root "pmr" logger that gets configured once in main())
# ==============================================================================

import logging
log = logging.getLogger("pmr.workspaces")


PMR_INSTANCES = {
    'models': 'https://models.physiomeproject.org/',
    'teaching': 'https://teaching.physiomeproject.org/',
    'staging': 'https://staging.physiomeproject.org/',
}

KNOWN_PROMPTS = [
    'Model Metadata',
    'Launch with OpenCOR',
    'Semantic Metadata',
    'COMBINE Archive',
    'Source View',
    'Cite this model',
    'Generated Code',
    'Mathematics',
    'Documentation'
]

KNOWN_RELS = [
    'bookmark',
    'section',
    'via'
]

def _request_json(url, debug_print=None):
    req = Request(url)
    req.add_header('Accept', 'application/vnd.physiome.pmr2.json.1')
    req.add_header('User-Agent', 'andre.pmr-utils/0.0')
    data = None
    try:
        stream = urlopen(req)
        data = json.load(stream)
        if debug_print:
            print(f'{debug_print} [get JSON request]: {url}')
            print(json.dumps(data, indent=debug_print))
    except:
        print(f"Requested URL did not return JSON: {url}")

    return data


def _parse_args():
    parser = argparse.ArgumentParser(prog="workspaces")
    parser.add_argument("--instance", help="PMR instance to work with.",
                        choices=['models', 'teaching', 'staging'], default='models')
    parser.add_argument("--action", choices=['list', 'update'],
                        default='list',
                        help="the action to perform with this instance of PMR.")
    parser.add_argument("--cache", default="pmr-cache",
                        help="Path to the folder to store the local PMR cache in.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--regex",
                        help='Specify a regex to use in applying the given action to matching workspaces')
    group.add_argument("--workspace",
                        help='Specify a single workspace rather than searching PMR')
    group.add_argument("--all", action='store_true', default=False,
                        help='Iterate over all available (public) content in PMR')
    return parser.parse_args()


def get_workspace_list(instance, regex, workspace, all):
    workspace_list = []
    if workspace:
        # user has given a single workspace to use, check its for this instance of PMR
        if not workspace.startswith(instance):
            log.error(f'The requested workspace, {workspace}, is not from this instance of PMR ({instance}).')
            return workspace_list
        workspace_list.append(workspace)
    elif regex or all:
        # fetch workspaces from the requested instance
        workspace_root = instance + "/workspace"
        data = _request_json(workspace_root)
        collection_links = data['collection']['links']
        entry_count = len(collection_links)
        log.info(f"Total number of workspaces retrieved: {entry_count}")
        workspace_list = []
        for entry in collection_links:
            if (not regex) or re.match(regex, entry['href']):
                workspace_list.append(entry['href'])
        log.info(f"Retrieved {len(workspace_list)} workspace(s) from this PMR instance that match the regex: {regex}")
    return workspace_list


def list_link(link, follow=None):
    href = link['href']
    prompt = link['prompt']
    rel = link['rel']
    link_desc = {
        'href': href,
        'prompt': prompt,
        'relationship': rel
    }
    if not ((rel in KNOWN_RELS) and (prompt in KNOWN_PROMPTS)):
        # maybe something we haven't seen before?
        log.debug(f'Unknown link? Link({rel}): {href}; {prompt}')
    if follow and rel == follow and href.startswith("https://models.physiomeproject.org/"):
        data = _request_json(href)
        link_info = data['collection']['items'][0]
        link_data = link_info['data']
        for d in link_data:
            link_desc[d['name']] = d['value']
        if 'links' in data['collection']:
            link_links = data['collection']['links']
            link_desc['links'] = []
            for l in link_links:
                link_desc['links'].append(list_link(l, follow))
    if rel == 'section':
        if prompt == 'Model Metadata':
            data = _request_json(href)
            mm_data = data['collection']['items'][0]['data']
            mm = {}
            for d in mm_data:
                mm[d['name']] = d['value']
            link_desc['model_metadata'] = mm
    return link_desc


def list_exposure(exposure_url):
    log.debug(f'Exposure: {exposure_url}')
    exposure = {
        'href': exposure_url
    }
    data = _request_json(exposure_url)
    exposure_info = data['collection']['items'][0]
    exposure_data = exposure_info['data']
    for d in exposure_data:
        exposure[d['name']] = d['value']
    exposure_links = data['collection']['links']
    exposure['links'] = []
    for l in exposure_links:
        exposure['links'].append(list_link(l, follow='bookmark'))
    return exposure


def create_workspace(workspace_url) -> Workspace:
    log.debug(f"Workspace: {workspace_url}")
    url = workspace_url + "/workspace_view"
    data = _request_json(url)
    workspace_info = data['collection']['items'][0]
    workspace = {
        'href': workspace_info['href']
    }
    workspace_data = workspace_info['data']
    for d in workspace_data:
        workspace[d['name']] = d['value']
    if 'links' in workspace_info:
        links = workspace_info['links']
        # we only care about the latest exposure, if exists
        for link in links:
            if link['prompt'] == 'Latest Exposure':
                workspace['latest-exposure'] = list_exposure(link['href'])
            else:
                log.warning(f'[list_workspace] Unknown link found and ignored: {link["prompt"]}')

    return Workspace(
        href=workspace['href'],
        id=workspace['id'],
        title=workspace['title'],
        owner=workspace['owner'],
        description=workspace.get('description', ''),
        latest_exposure=workspace.get('latest-exposure', {})
    )


def update_workspaces(workspaces, cache_root):
    for w in workspaces:
        path = pathlib.Path(urlparse(w).path)
        workspace = path.name
        workspace_cache = cache_root / workspace
        if workspace_cache.exists():
            repo = Repo(workspace_cache)
            repo.remotes.origin.pull()
        else:
            repo = Repo.clone_from(w, workspace_cache)


def cache_workspace_information(cache: PMRCache, regex, workspace, all, force_refresh) -> int:
    log.debug(f'Cache workspace information using cache: {cache}')

    workspaces = get_workspace_list(cache.pmr_instance, regex, workspace, all)
    if len(workspaces) > 0:
        log.info(f'Found {len(workspaces)} workspace(s) to cache information for.')
        with logging_redirect_tqdm():
            for w in tqdm(workspaces, desc="Caching workspaces"):
                workspace = cache.get_workspace(w)
                if (workspace and not force_refresh):
                    log.debug(f'Workspace {w} already cached and refresh not forced, skipping.')
                else:
                    log.debug(f'Workspace {w} not cached or refresh forced.')
                    workspace = create_workspace(w)
                    cache.upsert_workspace(workspace)
    else:
        log.warning(f'No requested workspaces found, perhaps you are looking for a workspace that is not public?')
        return -1
    
    return 0

def check_cache(instance, root):
    print(f"Updating the local cache: {root}")
    cache_root = pathlib.Path(root)
    cache_root.mkdir(parents=True, exist_ok=True)
    cache_instance_file = cache_root / ".instance"
    if cache_instance_file.is_file():
        cache_instance = cache_instance_file.read_text()
        if cache_instance != instance:
            print(f"Your local PMR cache originates from {cache_instance}, but {instance} was requested")
            return None
    else:
        cache_instance_file.write_text(instance)
    return cache_root


if __name__ == "__main__":
    args = _parse_args()
    pmr_instance = PMR_INSTANCES[args.instance]
    cache_root = check_cache(pmr_instance, args.cache)
    if not cache_root:
        print(f'Error with local cache')
        exit(-2)

    print(f"PMR Instance: {pmr_instance}")
    workspaces = get_workspace_list(pmr_instance, args.regex, args.workspace, args.all)
    if len(workspaces) > 0:
        if args.action == 'list':
            list_cache = cache_root / 'workspace_list.json'
            list_cache_incremental = cache_root / 'workspace_list_inc.json'
            workspace_descriptions = []
            for w in workspaces:
                desc = list_workspace(w)
                workspace_descriptions.append(desc)
                with open(list_cache_incremental, 'w') as f:
                    json.dump(workspace_descriptions, f, indent=2)

            with open(list_cache, 'w') as f:
                json.dump(workspace_descriptions, f, indent=2)
        elif args.action == 'update':
            update_workspaces(workspaces, cache_root)

    else:
        print(f'No requested workspaces found, perhaps you are looking for a workspace that is not public?')
        exit(-1)

    # url = 'https://staging.physiomeproject.org/workspace'
    # print(url)
    # req = Request(url)
    # req.add_header('Accept', 'application/vnd.physiome.pmr2.json.1')
    # stream = urlopen(req)
    # data = json.load(stream)
    # print(json.dumps(data, indent=3))