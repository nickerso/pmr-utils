import json
from pmr_cache import PMRCache, Workspace
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm
from datetime import datetime, timezone


# ===========================================================================
# Module-level logger
# (each module in your project should do this — they all feed into the
#  root "pmr" logger that gets configured once in main())
# ===========================================================================

import logging
log = logging.getLogger("pmr.omicsdi_export")


tmpl = '''<database>
  <name>Physiome Model Repository</name>
  <description>The main goal of the Physiome Model Repository is to provide a resource for the community to store, retrieve, search, reference, and reuse models.</description>
  <release>{release_number}</release>
  <release_date>{today}</release_date>
  <entry_count>{entry_count}</entry_count>
  <entries>  
    {entries}
  </entries>
</database>
'''

entry_tmpl = '''
    <entry id="{entry_id}">
        <name>{entry_name}</name>
        <description>{entry_description}</description>
        <cross_references>
            <ref dbname="pubmed" dbkey="{entry_publication}"/>
        </cross_references>
        <additional_fields>
            <field name="submitter">David Nickerson</field>
            <field name="submitter_mail">d.nickerson@auckland.ac.nz</field>
            <field name="repository">PMR</field>
            <field name="full_dataset_link">{entry_url}</field>
            <field name="omics_type">Models</field>
        </additional_fields>    
    </entry>
'''


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



def export_to_omicsdi(cache: PMRCache) -> str:
    workspaces = cache.list_workspaces()
    log.info(f'There are {len(workspaces)} workspaces in the cache')
    entries = []
    with logging_redirect_tqdm():
        for w in tqdm(workspaces, desc="Processing workspaces for OmicsDI export"):
            id = w.id
            name = str(w.title or '').replace('&', '&amp;')
            description = str(w.description or '').replace('&', '&amp;')
            url = w.href
            citations = []
            if w.latest_exposure:
                links = w.latest_exposure['links']
                for l in links:
                    citation_id = find_in_dict(l, 'citation_id')
                    if citation_id:
                        citations.append(citation_id)
            citation_set = set(citation.lower() for citation in citations)
            pubs = []
            for c in citation_set:
                if c.startswith('urn:miriam:pubmed:'):
                    pubs.append(c.replace('urn:miriam:pubmed:', ''))
                else:
                    print(f'Non pubmed URN found: {c}')
                    pubs.append(c)
            publications = ' ; '.join(pubs)
            entries.append(entry_tmpl.format(
                entry_id=id,
                entry_url=url or '',
                entry_name=name or id,
                entry_description=description or f'Exposure with the id: {id}',
                entry_publication=publications or ''
            ))

    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    release_number = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
    log.info(f'Exporting {len(entries)} entries to OmicsDI format with release number {release_number} and release date {today}')
    mx_xml = tmpl.format(
        entry_count=len(entries),
        entries=''.join(entries),
        today=today,
        release_number=release_number
    )
    
    return mx_xml
