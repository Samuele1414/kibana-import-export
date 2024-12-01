#!/usr/bin/env python3

import argparse
import requests
import logging
import os
import json
from getpass import getpass

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def parse_nonstandard_json(file_path):
    documents = []
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        json_objects = content.splitlines()
        for obj in json_objects:
            if obj.strip():
                try:
                    documents.append(json.loads(obj))
                except json.JSONDecodeError as e:
                    print(f"Error during parsing: {e}\Object: {obj}")
    return documents

def parse_and_save_documents(input_file, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    documents = parse_nonstandard_json(input_file)

    for i, doc in enumerate(documents):
        title = doc.get('attributes', {}).get('title', f'document_{i + 1}')
        sanitized_title = title.replace(' ', '_').replace('/', '_')
        output_file = os.path.join(output_dir, f'{sanitized_title}.json')
        with open(output_file, 'w', encoding='utf-8') as f_out:
            json.dump(doc, f_out, indent=4, ensure_ascii=False)
        print(f"Document saved: {output_file}")

def get_spaces(session, url):
    """Retrieve all spaces."""
    response = session.get(f"{url}/api/spaces/space")
    response.raise_for_status()
    return response.json()

def export_space_details(spaces, export_dir):
    """Save space details to a JSON file."""
    with open(os.path.join(export_dir, 'spaces_details.json'), 'w') as file:
        json.dump(spaces, file)
    logging.info("Exported space details.")

def export_objects(session, url, export_dir, space, object_types):
    logging.info(f"object_types: {object_types}")
    space_id = space['id']
    export_url = f"{url}/s/{space_id}/api/saved_objects/_export"
    params = {"type": object_types or ["*"]}
    logging.info(f"Requesting URL: {export_url} with params: {json.dumps(params)}")
    response = session.post(export_url, json=params)
    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        logging.error(f"Failed to export objects for space {space_id}: {e}")
        logging.error(f"Response was: {response.text}")
        return
    file_path = os.path.join(export_dir, f"{space_id}.json")
    with open(file_path, 'wb') as file:
        file.write(response.content)
    logging.info(f"Export successful for space {space_id}: {file_path}")

def validate_spaces(spaces, all_spaces):
    valid_spaces = [space['id'] for space in all_spaces]
    invalid_spaces = [space for space in spaces if space not in valid_spaces] if spaces else []

    if invalid_spaces:
        logging.error("The following specified spaces do not exist: " + ", ".join(invalid_spaces))

    if invalid_spaces:
        logging.error("Exiting due to invalid input.")
        exit(1)


def main():
    parser = argparse.ArgumentParser(description="Export objects and details from specified spaces in Kibana, or all spaces if none are specified.",
                                     epilog="Example: export_kibana.py http://localhost:5601 username /path/to/export --spaces space1 space2 --types dashboard visualization")
    parser.add_argument('kibana_url', help="Kibana URL, e.g., http://localhost:5601")
    parser.add_argument('username', help="Username for Kibana")
    parser.add_argument('export_dir', help="Directory to save the NDJSON files and space details")
    parser.add_argument('--types', nargs='+', help="Specify types of objects to export, separated by spaces (e.g., dashboard visualization). If omitted, all types are exported.")
    parser.add_argument('--spaces', nargs='+', help="Specify space IDs to export, separated by spaces (e.g., space1, space2). If omitted, all spaces are exported.")

    args = parser.parse_args()

    password = getpass("Enter your password: ")
    session = requests.Session()
    session.verify = False
    session.auth = (args.username, password)
    session.headers.update({'kbn-xsrf': 'true'})

    if not os.path.exists(args.export_dir):
        os.makedirs(args.export_dir)

    all_spaces = get_spaces(session, args.kibana_url)

    # Validate the specified spaces and types before proceeding
    validate_spaces(args.spaces, all_spaces)
    spaces_to_export = all_spaces if not args.spaces else [space for space in all_spaces if space['id'] in args.spaces]
    export_space_details(spaces_to_export, args.export_dir)
    for space in spaces_to_export:
        output_dir = 'output'
        export_objects(session, args.kibana_url, args.export_dir, space, args.types)
        input_file = 'export/'+space["id"]+'.json' 
        output_dir = output_dir+'_'+space["id"]
        parse_and_save_documents(input_file, output_dir)


    
if __name__ == "__main__":
    main()
