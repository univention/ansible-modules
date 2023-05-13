#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2020-2021, Univention GmbH
# Written by Lukas Zumvorde <zumvorde@univention.de>, Jan-Luca Kiok <kiok@univention.de>
# Based on univention_apps module written by Alexander Ulpts <ulpts@univention.de>

# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

ANSIBLE_METADATA = {
    'metadata_version': '1.2',
    'status': ['preview'],
    'supported_by': 'comunity'
}

DOCUMENTATION = '''
---
module: univention_directory_manager

short_description: Accessing the Univention Directory Manager

description:
    - "You can create and modify Objects in the LDAP with Univention Directory Manager."

options:
    module:
        description:
            - The udm module for which objects are to be modified
        type: str
        required: True
    position:
        description:
            - The position in the tree
        type: str
        required: False
    dn:
        description:
            - The distinguished name of the LDAP object.
        type: str
        required: false
    filter:
        description:
            - A LDAP search filter to select objects.
        type: str
        required: false
    state:
        description:
            - Either 'present' for creating or modifying the objects given with
              'dn' and 'filter' or 'absent' for deleting the objects from the LDAP.
              Default is 'present'.
        type: str
        choices: [ absent, present ]
        default: present
    superordinate:
        description:
            - When creating a new object, set its superordinate to this DN.
            - Only affects newly created LDAP objects, this option is ignored for
              modifications and removals of existing entries.
        type: str
        required: False
    set_properties:
        description:
            - A list of dictionaries with the keys property and value.
            - Properties of the objects are to be set to the given values.
        type: list
        required: False
    unset_properties:
        description:
            - A list of dictionaries with the key property.
            - The listed properties of the objects are to be unset.
        type: list
        required: False

author:
    - Lukas Zumvorde
    - Jan-Luca Kiok
'''

EXAMPLES = '''
# create a new user object
- name: create a user
  univention_directory_manager:
    module: 'users/user'
    state: 'present'
    set_properties:
      - property: 'username'
        value: 'testuser1'
      - property: 'lastname'
        value: 'testuser1'
      - property: 'password'
        value: 'mypassword'

# delete one or more objects
- name: delete a user with a search filter
  univention_directory_manager:
    module: 'users/user'
    state: 'absent'
    filter: '(uid=testuser1)'

# create an extended attribute
- name: "create an extended attribute with superordinary param and complex attributes"
  univention_directory_manager:
    module: "settings/extended_attribute"
    state: "present"
    superordinate: "cn=custom attributes,cn=univention,dc=example,dc=org"
    set_properties:
      - property: "name"
        value: "testAttribute"
      - property: "shortDescription"
        value: "This is a test attribute"
      - property: "module"
        # Multivalued properties must be provided as a list
        value: ["users/user", "groups/group"]
      - property: "translationShortDescription"
        # Complex types must be provided in their parsed tuple form, always nested inside a list
        value: [["de_DE", "Dies ist ein Test-Attribut"]]
      - property: "objectClass"
        value: "customAttributeGroups"
      - property: "ldapMapping"
        value: "customAttributeTestAttribute"

# use position to place the object in the directory tree
- name: create a user with position
  univention_directory_manager:
    module: 'users/user'
    state: 'present'
    position: 'cn=users,ou=DEMOSCHOOL,dc=t1,dc=intranet'
    set_properties:
      - property: 'username'
        value: 'testuser2'
      - property: 'lastname'
        value: 'testuser2'
      - property: 'password'
        value: 'mypassword'

# delete on very specific object
- name: delete the user with position
  univention_directory_manager:
    module: 'users/user'
    state: 'absent'
    dn: 'uid=testuser2,cn=users,ou=DEMOSCHOOL,dc=t1,dc=intranet'

# add or change specific properties
- name: modify testuser3 - add or change a property
  univention_directory_manager:
    module: 'users/user'
    state: 'present'
    filter: '(uid=testuser3)'
    set_properties:
      - property: 'firstname'
        value: 'max'

# remove specific properties
- name: modify testuser3 - remove property
  univention_directory_manager:
    module: 'users/user'
    state: 'present'
    filter: '(uid=testuser3)'
    unset_properties:
      - property: 'firstname'
        value: 'does not matter'
'''

RETURN = '''
meta['changed_objects']:
    description: A list of all objects that were changed.
msg:
    description: A human-readable information about which objects were changed.
'''

import traceback # noqa F401

from ansible.module_utils.basic import AnsibleModule  # noqa F401

UDM_IMP_ERR = None
try:
    import univention.udm
    HAS_UDM = True
except ModuleNotFoundError:
    HAS_UDM = False
    UDM_IMP_ERR = traceback.format_exc()


class UDMAnsibleModule():
    '''UDMAnsibleModule
    '''

    udm_api_version = 2
    udm_module = None

    changed_objects = []
    result = dict(
        changed=False,
        meta=dict(
            changed_objects=changed_objects,
            ),
        msg='',
    )

    def __init__(self, module):
        # Class
        self.ansible_module = module
        self.ansible_params = module.params

    def _check_univention_import_errors(self):
        if not HAS_UDM:
            self.result['msg'] = "The python module 'univention.udm' is not available."
            self.result['exception'] = UDM_IMP_ERR
            self.ansible_module.fail_json(**self.result)

    def _get_udm_connection(self):
        try:
            udm_con = univention.udm.UDM.admin().version(self.udm_api_version)
        except univention.udm.exceptions.ConnectionError:
            self.result['msg'] = "Does your user have access to '/etc/ldap.secret'?"
            self.result['exception'] = traceback.format_exc()
            self.ansible_module.fail_json(**self.result)
        return udm_con

    def _get_udm_module(self, udm_con, udm_module):
        try:
            _udm_module = udm_con.get(udm_module)
        except univention.udm.exceptions.UnknownModuleType:
            self.result['msg'] = "UDM not up to date? Module '{}' not found.".format(udm_module)
            self.result['exception'] = traceback.format_exc()
            self.ansible_module.fail_json(**self.result)
        return _udm_module

    def _extract_properties_from_dn(self):
        if not self.ansible_params['dn']:
            return None
        try:
            name, position = self.ansible_params['dn'].split(',', 1)
            name = name.split('=', 1)[1]
            if not self.ansible_params['set_properties']:
                self.ansible_params['set_properties'] = []
            self.ansible_params['set_properties'].append(
                {'property': self.udm_module.meta.identifying_property, 'value': name}
            )
            self.ansible_params['position'] = position
        except IndexError:
            self.result['msg'] = 'Invalid parameter dn'
            self.ansible_module.fail_json(**self.result)

    def _get_object_by_property(self):
        try:
            for prop in self.ansible_params['set_properties']:
                if prop['property'] == self.udm_module.meta.identifying_property:
                    return self.udm_module.get_by_id(prop['value'])
            else:
                return None
        except univention.udm.exceptions.NoObject:
            return None
        except univention.udm.exceptions.MultipleObjects:
            return None
        except TypeError:
            return None

    def _get_udm_obj_by_property(self):
        obj_by_property = []
        obj = self._get_object_by_property()
        if obj:
            obj_by_property.append(obj)
        return obj_by_property

    def _get_udm_obj_by_filter(self):
        obj_by_filter = []
        if self.ansible_params['filter']:
            for obj in self.udm_module.search(self.ansible_params['filter']):
                obj_by_filter.append(obj)
        return obj_by_filter

    def _encoder(self, obj, prop):
        """
        :params: obj : udm_obj
        :params: prop : str
        :returns: The _encoder class for the given prop
        """
        return obj.props._encoders.get(prop)(
            property_name=prop,
            connection=self.udm_module.connection,
            api_version=self.udm_api_version,
        )

    def _decode_value(self, obj, prop, value):
        """
        :returns: the decoded value
        """
        if prop in obj.props._encoders:
            value = self._encoder(obj, prop).decode(value)
        return value

    def _encode_value(self, obj, prop, value):
        """
        :returns: the encoded value
        """
        if prop in obj.props._encoders:
            value = self._encoder(obj, prop).encode(value)
        return value

    def _set_property(self, obj, prop, value):
        setattr(obj.props, prop, self._decode_value(obj, prop, value))

    def _apply_policies(self, obj):
        if self.ansible_params['policies']:
            obj.policies = self.ansible_params['policies']

    def _apply_options(self, obj):
        if self.ansible_params['options']:
            obj.options = []
            for option in self.ansible_params['options']:
                obj.options.append(option)

    def _create_object(self):
        obj = self.udm_module.new(
            superordinate=self.ansible_params.get('superordinate')
        )
        if self.ansible_params['position']:
            obj.position = self.ansible_params['position']
        self._apply_options(obj)
        self._apply_policies(obj)
        if self.ansible_params['set_properties']:
            for attr in self.ansible_params['set_properties']:
                prop_name = attr['property']
                prop_value = attr['value']
                self._set_property(obj, prop_name, prop_value)
        if not self.ansible_module.check_mode:
            obj.save()
            self.changed_objects.append(obj.dn)

    def _modify_object(self, obj):
        self._apply_options(obj)
        self._apply_policies(obj)
        if self.ansible_params['unset_properties']:
            for attr in self.ansible_params['unset_properties']:
                prop_name = attr['property']
                self._set_property(obj, prop_name, None)
        if self.ansible_params['set_properties']:
            for attr in self.ansible_params['set_properties']:
                prop_name = attr['property']
                prop_value = attr['value']
                self._set_property(obj, prop_name, prop_value)
        if not self.ansible_module.check_mode:
            obj.save()
            self.changed_objects.append(obj.dn)

    def _remove_objects(self, obj):
        if not self.ansible_module.check_mode:
            obj.delete()
            self.changed_objects.append(obj.dn)

    def run(self):
        # univention module
        self._check_univention_import_errors()
        udm_con = self._get_udm_connection()
        self.udm_module = self._get_udm_module(udm_con, self.ansible_params['module'])
        self._extract_properties_from_dn()
        # get udm_objects
        udm_objects = self._get_udm_obj_by_filter()
        udm_objects += self._get_udm_obj_by_property()
        # State present
        if self.ansible_params['state'] == 'present':
            for obj in udm_objects:
                self._modify_object(obj)
            if not udm_objects:
                self._create_object()
        # State absent
        elif self.ansible_params['state'] == 'absent':
            for obj in udm_objects:
                self._remove_objects(obj)
        self.result['msg'] = 'changed objects: %s' " ".join(self.changed_objects)
        self.ansible_module.exit_json(**self.result)


def run_module():
    module_args = dict(
        module=dict(
            type='str',
            required=True
        ),
        position=dict(
            type='str',
            required=False
        ),
        set_properties=dict(
            type='list',
            required=False
        ),
        unset_properties=dict(
            type='list',
            required=False
        ),
        dn=dict(
            type='str',
            required=False
        ),
        filter=dict(
            type='str',
            required=False
        ),
        state=dict(
            type='str',
            default='present',
            choices=['present', 'absent'],
            required=False
        ),
        options=dict(
            type='list',
            required=False
        ),
        policies=dict(
            type='list',
            required=False
        ),
        superordinate=dict(
            type='str',
            default=None,
            required=False
        ),
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    udm_ansible_module = UDMAnsibleModule(module)
    udm_ansible_module.run()


if __name__ == '__main__':
    run_module()
