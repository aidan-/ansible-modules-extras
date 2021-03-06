#!/usr/bin/python
# -*- coding: utf-8 -*-
# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.

DOCUMENTATION = '''
---
module: iam_saml_federation
version_added: "2.3"
short_description: maintain iam saml federation configuration.
description:
    - Maintains IAM SAML identity federation configurations. This module has a dependency on python-boto >= 2.5.
options:
    name:
        description:
            - The name of the provider to create.
        required: true
    saml_metadata_document:
        description:
            - The XML document generated by an identity provider (IdP) that supports SAML 2.0.  More information on what this document is and how it is created is available in the AWS docs (http://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_create_saml.html#idp-manage-identityprovider-console)
    state:
        description:
            - Whether to create or delete identity provider. If 'present' is specified it will attempt to update the identity provider matching the name field.
        default: present
        choices: [ "present", "absent" ]
extends_documentation_fragment:
    - aws
author: "Aidan Rowe (@aidan-)"
'''

EXAMPLES = '''
# Note: None of these examples set aws_access_key or aws_secret_key.
# It is assumed that their matching environment variables are set.

# Creates a new iam saml identity provider if not present
- name: saml provider
    iam_saml_federation:
        name: example1
        saml_metadata_document: > # the > here opens an indented block, so no escaping/quoting is needed when in the indentation level under this key
            <?xml version="1.0"?>...
            <md:EntityDescriptor

# Creates a new iam saml identity provider if not present
- name: saml provider
    iam_saml_federation:
        name: example2
        saml_metadata_document: "{{ item }}"
    with_file: /path/to/idp/metdata.xml

# Removes iam saml identity provider
- name: remove saml provider
    iam_saml_federation:
        name: example3
        state: absent
'''

RETURN = '''
provider_arn:
    description: The ARN of the SAML Identity Provider that was created/modified.
    type: string
    sample: "arn:aws:iam::123456789012:saml-provider/my_saml_provider"
'''

try:
    import boto3
    import botocore.exceptions
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False
import sys

class SAMLProviderManager:
    """Handles SAML Identity Provider configuration"""

    def __init__(self, module, **aws_connection_params):
        self.module = module
        self.aws_connection_params = aws_connection_params

        try:
            self.conn= boto3_conn(module, conn_type='client', resource='iam', **self.aws_connection_params)
        except botocore.exceptions.ClientError as e:
            self.module.fail_json(msg=str(e))

    def _get_provider_arn(self, name):
        provider_arn = ""
        providers = self.conn.list_saml_providers()
        for p in providers['SAMLProviderList']:
            provider_name = p['Arn'].split('/', 1)[1]
            if name == provider_name:
                return p['Arn']

        return None

    def create_or_update_saml_provider(self, name, metadata):
        if not metadata:
            self.module.fail_json(changed=changed, msg="saml_metadata_document must be defined for present state")

        res = { 'changed' : False }
        arn = self._get_provider_arn(name)
        if arn: #see if metadata needs updating
            resp = self.conn.get_saml_provider(SAMLProviderArn=arn)

            if metadata.strip() != resp['SAMLMetadataDocument'].strip():
                # provider needs updating
                res['changed'] = True
                if not self.module.check_mode:
                    try:
                        resp = self.conn.update_saml_provider(SAMLProviderArn=arn, SAMLMetadataDocument=metadata)
                        res['provider_arn'] = resp['SAMLProviderArn']
                    except botocore.exceptions.ClientError as e:
                        res['msg'] = str(e)
                        res['debug'] = [arn, metadata]
                        self.module.fail_json(**res)

        else: #create
            res['changed'] = True
            if not self.module.check_mode:
                try:
                    resp = self.conn.create_saml_provider(SAMLMetadataDocument=metadata, Name=name)
                    res['provider_arn'] = resp['SAMLProviderArn']
                except botocore.exceptions.ClientError as e:
                    res['msg'] = str(e)
                    res['debug'] = [name, metadata]
                    self.module.fail_json(**res)

        self.module.exit_json(**res)

    def delete_saml_provider(self, name):
        arn = self._get_provider_arn(name)
        res = { 'changed' : False }

        if arn: #delete
            res['changed'] = True     
            if not self.module.check_mode:     
                try:
                    resp = self.conn.delete_saml_provider(SAMLProviderArn=arn)
                    changed = True
                except botocore.exceptions.ClientError as e:
                    res['msg'] = str(e)
                    res['debug'] = [arn]
                    self.module.fail_json(**res)
        
        self.module.exit_json(**res)

def main():
    argument_spec = aws_common_argument_spec()
    argument_spec.update(dict(
            name=dict(required=True),
            saml_metadata_document=dict(default=None, required=False),
            state=dict(default='present', required=False, choices=['present', 'absent']),
        )
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    if not HAS_BOTO:
        module.fail_json(msg='boto required for this module')

    region, ec2_url, aws_connect_kwargs = get_aws_connection_info(module, boto3=True)

    name = module.params['name']
    state = module.params.get('state')
    saml_metadata_document = module.params.get('saml_metadata_document')

    sp_man = SAMLProviderManager(module, **aws_connect_kwargs)

    if state == 'present':
        sp_man.create_or_update_saml_provider(name, saml_metadata_document)
    elif state == 'absent':
        sp_man.delete_saml_provider(name)

from ansible.module_utils.basic import *
from ansible.module_utils.ec2 import *

if __name__ == '__main__':
    main()
