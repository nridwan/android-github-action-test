import os
import argparse
import requests
import json
import re
import time

DROPBOX_ERROR_CODE = 1
ZAPIER_ERROR_CODE = 2
TEMPLATE_ERROR_CODE = 3
CHANGES_ERROR_CODE = 4
OUTPUT_FILE_PARSING_ERROR = 5

DROPBOX_UPLOAD_ARGS = {
    'path': None,
    'mode': 'overwrite',
    'autorename': True,
    'strict_conflict': True
}
DROPBOX_UPLOAD_URL = 'https://content.dropboxapi.com/2/files/upload'

DROPBOX_SHARE_DATA = {
    'path': None,
    'settings': {
        'requested_visibility': 'public'
    }
}
DROPBOX_SHARE_URL = 'https://api.dropboxapi.com/2/sharing/create_shared_link_with_settings'

DROPBOX_DELETE_DATA = {
    'path' : None
}
DROPBOX_DELETE_URL = 'https://api.dropboxapi.com/2/files/delete_v2'

def upload_to_dropbox(target_file_name, source_file, dropbox_token, dropbox_folder):
    '''Upload file to dropbox
    
    Args:
        target_file_name (str): Uploaded file will be rename to this file name.
        source_file (str): File that is going to be uploaded.
        dropbox_token (str): Dropbox API key.
        dropbox_folder (str): Dropbox target folder.

    Returns:
        str: Shared url for download.
    '''
    dropbox_path = '/{folder}/{file_name}'.format(folder=dropbox_folder, file_name=target_file_name)
    DROPBOX_UPLOAD_ARGS['path'] = dropbox_path
    DROPBOX_SHARE_DATA['path'] = dropbox_path
    DROPBOX_DELETE_DATA['path'] = dropbox_path

    # Try to delete the file before upload
    # It's possible to overwrite but this way is cleaner
    headers = {'Authorization': 'Bearer ' + dropbox_token,
            'Content-Type': 'application/json'}
    
    requests.post(DROPBOX_DELETE_URL, data=json.dumps(DROPBOX_DELETE_DATA), headers=headers)

    headers = {'Authorization': 'Bearer ' + dropbox_token,
               'Dropbox-API-Arg': json.dumps(DROPBOX_UPLOAD_ARGS),
               'Content-Type': 'application/octet-stream'}

    # Upload the file
    r = requests.post(DROPBOX_UPLOAD_URL, data=open(source_file, 'rb'), headers=headers)

    if r.status_code != requests.codes.ok:
        print("Failed: upload file to Dropbox: {errcode}".format(errcode=r.status_code))
        return None

    headers = {'Authorization': 'Bearer ' + dropbox_token,
               'Content-Type': 'application/json'}

    # Share and return downloadable url
    r = requests.post(DROPBOX_SHARE_URL, data=json.dumps(DROPBOX_SHARE_DATA), headers=headers)

    if r.status_code != requests.codes.ok:
        print("Failed: get share link from Dropbox {errcode}".format(errcode=r.status_code))
        return None

    # Replace the '0' at the end of the url with '1' for direct download
    return re.sub('dl=.*', 'raw=1', r.json()['url'])

def get_app(release_dir):
    '''Extract app data
    
    Args:
        release_dir (str): Path to release directory.

    Returns:
        (str, str): App version and path to release apk file.
    '''
    output_path = os.path.join(release_dir, 'output.json')

    with(open(output_path)) as app_output:
        json_data = json.load(app_output)

    apk_details_key = ''
    if 'apkInfo' in json_data[0]:
        apk_details_key = 'apkInfo'
    elif 'apkData' in json_data[0]:
        apk_details_key = 'apkData'
    else:
        print("Failed: parsing json in output file")
        return None, None

    app_version = json_data[0][apk_details_key]['versionName']
    app_file = os.path.join(release_dir, json_data[0][apk_details_key]['outputFile'])
    return app_version, app_file


def get_target_file_name(app_name, app_version):
    '''Generate file name for released apk, using app name and version:
    app_name - MyApp
    version - 1.03
    result: myapp_1_03.apk
    
    Args:
        app_name (str): App name.
        app_version (str): App version.

    Returns:
        str: App file name.
    '''
    app_name = app_name.lower()
    app_version = app_version.replace('.', '_')
    return '{name}-{version}-{timestamp}.apk'.format(name=app_name, version=app_version, timestamp=long(time.time())).replace(' ','')


if __name__ == '__main__':
    # Command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('--release.dir', dest='release_dir', help='path to release folder', required=True)
    parser.add_argument('--app.name', dest='app_name', help='app name that will be used as file name', required=True)
    parser.add_argument('--dropbox.token', dest='dropbox_token', help='dropbox access token', required=True)
    parser.add_argument('--dropbox.folder', dest='dropbox_folder', help='dropbox target folder', required=True)

    options = parser.parse_args()

    # Extract app version and file
    app_version, app_file = get_app(options.release_dir)
    if app_version == None or app_file == None:
        exit(OUTPUT_FILE_PARSING_ERROR)
    
    target_app_file = get_target_file_name(options.app_name, app_version)
    f=open(os.path.dirname(os.path.relpath(__file__))+"/version.txt","w+")
    f.write(app_version)
    f.close()
    exit(0)

    # Upload app file and get shared url
    file_url = upload_to_dropbox(target_app_file, app_file, options.dropbox_token, options.dropbox_folder)
    if file_url == None:
        exit(DROPBOX_ERROR_CODE)
    f=os.path.dirname(os.path.relpath(__file__))+"/url.txt"
    f.write(file_url)
    f.close()