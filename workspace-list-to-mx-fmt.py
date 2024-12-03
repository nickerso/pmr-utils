import argparse
import json
from os.path import isfile


def _parse_args():
    parser = argparse.ArgumentParser(description="Convert a workspace listing JSON file to the OMICS DI xml format.")
    parser.add_argument("input", help="The workspace listing JSON file to convert")
    parser.add_argument("--output",
                        help="Output XML file (default print to terminal)")
    return parser.parse_args()

tmpl = '''<database>
  <name>Physiome Model Repository</name>
  <description>The main goal of the Physiome Model Repository is to provide a resource for the community to store, retrieve, search, reference, and reuse models.</description>
  <release>13</release>
  <release_date>2024-11-21</release_date>
  <entry_count>{entry_count}</entry_count>
  <entries>  
    {entries}
  </entries>
</database>
'''

# entry_tmpl = '''
#     <entry id="{entry_id}">
#         <name>{entry_name}</name>
#         <description>{description}</description>
#         <cross_references>
#             <ref dbkey="CHEBI:16551" dbname="ChEBI"/>
#             <ref dbkey="MTBLC16551" dbname="MetaboLights"/>
#             <ref dbkey="CHEBI:16810" dbname="ChEBI"/>
#             <ref dbkey="MTBLC16810" dbname="MetaboLights"/>
#             <ref dbkey="CHEBI:30031" dbname="ChEBI"/>
#         </cross_references>
#         <dates>
#             <date type="created" value="2013-11-19"/>
#             <date type="last_modified" value="2013-11-19"/>
#             <date type="submission" value="2020-03-11"/>
#             <date type="publication" value="2013-11-26"/>
#         </dates>
#         <additional_fields>
#             <field name="submitter">Andre</field>
#             <field name="submitter_mail">d.nickerson@auckland.ac.nz</field>
#             <field name="repository">PMR</field>
#             <field name="full_dataset_link">{entry_url}</field>
#             <field name="omics_type">Models</field>
#             <field name="publication"> ... </field>
#             <field name="modellingApproach">MAMO term goes here</field>
#         </additional_fields>
#     </entry>
# '''

entry_tmpl = '''
    <entry id="{entry_id}">
        <name>{entry_name}</name>
        <description>{entry_description}</description>
        <additional_fields>
            <field name="submitter">David Nickerson</field>
            <field name="submitter_mail">d.nickerson@auckland.ac.nz</field>
            <field name="repository">PMR</field>
            <field name="full_dataset_link">{entry_url}</field>
            <field name="omics_type">Models</field>
            <field name="publication">{entry_publication}</field>
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



if __name__ == "__main__":
    args = _parse_args()

    if not isfile(args.input):
        print(f'Specified input file ({args.input}) is not a file')
        exit(-1)

    with open(args.input, 'r') as f:
        cache = json.load(f)

    print(f'There are {len(cache)} workspaces in the cache')
    entries = []
    for w in cache:
        id = w['id']
        name = str(w['title'] or '').replace('&', '&amp;')
        description = str(w['description'] or '').replace('&', '&amp;')
        url = w['href']
        citations = []
        if 'latest-exposure' in w.keys():
            links = w['latest-exposure']['links']
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
            entry_id=id or '',
            entry_url=url or '',
            entry_name=name or '',
            entry_description=description or '',
            entry_publication=publications or ''
        ))

    mx_xml = tmpl.format(
        entry_count=len(cache),
        entries=''.join(entries),
    )
    if args.output:
        with open(args.output, 'w', encoding="utf-8") as f:
            f.write(mx_xml)
    else:
        print(mx_xml)
