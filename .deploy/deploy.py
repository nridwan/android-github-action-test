import argparse
import requests
import json
import re

DISCORD_ERROR_CODE = 1
ZAPIER_ERROR_CODE = 2
TEMPLATE_ERROR_CODE = 3
CHANGES_ERROR_CODE = 4
OUTPUT_FILE_PARSING_ERROR = 5

ZAPIER_SEND_DATA = {
    'to': None,
    'cc': None,
    'bcc': None,
    'subject': None,
    'body': None
}

DISCORD_SEND_DATA = {
    'content': None
}

def send_discord(discord_hook, subject, body):
    '''Send to discord
    
    Args:
        discord_hook (str): Discord hook url.
        to (str): Email recipients separated by comma.
        subject (str): Email subject.
        body (str): Email body.

    Returns:
        bool: Send success/fail.
    '''

    headers = {'Content-Type': 'application/json'}
    DISCORD_SEND_DATA['content'] = body

    r = requests.post(discord_hook, data=json.dumps(DISCORD_SEND_DATA), headers=headers)

    return r.status_code == 204

def send_email(zapier_hook, to, cc, bcc, subject, body):
    '''Send email with zapier hook
    
    Args:
        zapier_hook (str): Zapier hook url.
        to (str): Email recipients separated by comma.
        subject (str): Email subject.
        body (str): Email body.

    Returns:
        bool: Send success/fail.
    '''
    ZAPIER_SEND_DATA['to'] = to
    ZAPIER_SEND_DATA['cc'] = cc
    ZAPIER_SEND_DATA['bcc'] = bcc
    ZAPIER_SEND_DATA['subject'] = subject
    ZAPIER_SEND_DATA['body'] = body

    headers = {'Content-Type': 'application/json'}

    r = requests.post(zapier_hook, data=json.dumps(ZAPIER_SEND_DATA), headers=headers)

    return r.status_code == requests.codes.ok

def get_changes(change_log_path):
    '''Extract latest changes from changelog file.
    Changes are separated by ##

    Args:
        change_log_path (str): Path to changelog file.

    Returns:
        str: Latest changes.
    '''
    with(open(change_log_path)) as change_log_file:
        change_log = change_log_file.read()

    # Split by '##' and remove lines starting with '#'
    latest_version_changes = change_log.split('##')[0][:-1]
    latest_version_changes = re.sub('^#.*\n?', '', latest_version_changes, flags=re.MULTILINE)

    return latest_version_changes

def get_email(app_name, app_version, app_url, changes, template_file_path):
    '''Use template file to create release email subject and title.

    Args:
        app_name (str): App name.
        app_version (str): App version.
        app_url (str): Url for app download.
        changes (str): Lastest app changelog.
        template_file_path (str): Path to template file.

    Returns:
        (str, str): Email subject and email body.
    '''
    target_subject = 1
    target_body = 2
    target_discord_body = 3
    target = 0

    subject = ''
    body = ''
    discord_body = ''

    template = ''

    with(open(template_file_path)) as template_file:
        # Open template file and replace placeholders with data
        template = template_file.read().format(
            app_download_url=app_url,
            change_log=changes,
            app_name=app_name,
            app_version=app_version
        )
        
    # Iterate over each line and collect lines marked for subject/body
    for line in template.splitlines():
        if line.startswith('#'):
            if line.startswith('#subject'):
                target = target_subject
            elif line.startswith('#body'):
                target = target_body
            elif line.startswith('#discord_body'):
                target = target_discord_body
        else:
            if target == target_subject:
                subject += line + '\n'
            elif target == target_body:
                body += line + '\n'
            elif target == target_discord_body:
                discord_body += line + '\n'
    
    return subject.rstrip(), body.rstrip(), discord_body.rstrip()


if __name__ == '__main__':
    # Command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('--app.url', dest='app_url', help='APK file url', required=True)
    parser.add_argument('--app.version', dest='app_version', help='APK file version', required=True)
    parser.add_argument('--app.name', dest='app_name', help='app name that will be used as file name', required=True)
    parser.add_argument('--changelog.file', dest='changelog_file', help='path to changelog file', required=True)
    parser.add_argument('--template.file', dest='template_file', help='path to email template file', required=True)
    parser.add_argument('--zapier.hook', dest='zapier_hook', help='zapier email web hook', required=True)
    parser.add_argument('--discord.hook', dest='discord_hook', help='discord email web hook', required=True)
    parser.add_argument('--email.to', dest='email_to', help='email recipients', required=True)
    parser.add_argument('--email.cc', dest='email_cc', help='email recipients (CC)', required=False, default='')
    parser.add_argument('--email.bcc', dest='email_bcc', help='email recipients (BCC)', required=False, default='')

    options = parser.parse_args()

    # Extract latest changes
    latest_changes = get_changes(options.changelog_file)
    if latest_changes == None:
        exit(CHANGES_ERROR_CODE)
    
    # Compose email subject and body
    subject, body, discord_body = get_email(options.app_name, options.app_version, options.app_url, latest_changes, options.template_file)
    if subject == None or body == None:
        exit(TEMPLATE_ERROR_CODE)
    
    # Send email with release data
    if not send_email(options.zapier_hook, options.email_to, options.email_cc, options.email_bcc, subject, body):
        exit(ZAPIER_ERROR_CODE)

    if not send_discord(options.discord_hook, subject, discord_body):
        exit(DISCORD_ERROR_CODE)
