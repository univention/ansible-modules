# univention.ucs_modules.univention_directory_manager

**Manage objects via Univention Directory Manager (UDM).**

Version added: 1.2.0

## Synopsis

- Create nonexistent objects
- Modify properties of given objects
- Delete objects

## Requirements

The below requirements are needed on the host that executes this module.

- Python `>= 2.7` or `>= 3.9`

## Parameters

Parameter | Defaults | Comments
--- | --- | ---
module (string) | | The udm module for which objects are to be modified.
position (string) | | The position within the LDAP-tree.
dn (string) | | The distinguished name of the LDAP object.
filter (string) | | A LDAP search filter to select objects.
state (string) | "present" | Either 'present' for creating of modifying the objects given or 'absent' for deleting the objects.
superordinate (string) | None | When creating a new object, set its superordinate to this DN. Only affects newly created LDAP objects, this option is ingored for modifications and removals of existing entries.
set_properties (list) | | A list of dictionaries with the keys property and value. Properties of the objects are to be set to the given values.
unset_properties (list) | | A list of dictionaries with the key property. The listed properties of the objects are to be unset.

## Notes

## Examples

```yaml
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
        value: 'univention'

# create a DNS record object
- name: create a dns record
  univention_directory_manager:
    module: 'dns/host_record'
    state: 'present'
    superordinate: 'zoneName=example.org,cn=dns,dc=example,dc=org'
    set_properties:
      - property: 'name'
        value: 'test'
      - property: 'a'
        value: '192.0.2.42'
      - property: 'a'
        value: '2001:db8::42'

# delete one or more objects
- name: delete a user with a search filter
  univention_directory_manager:
    module: 'users/user'
    state: 'absent'
    filter: '(uid=testuser1)'

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
        value: 'univention'

# remove specific properties
- name: modify testuser3 - remove property
  univention_directory_manager:
    module: 'users/user'
    state: 'present'
    filter: '(uid=testuser3)'
    unset_properties:
      - property: 'firstname'
        value: 'does not matter'
 ```

## Return Values
Key | Returned | Description
--- | --- | ---
`meta['changed_objects']`(list) | always | A list of all objects that were changed. |
`message`(string) | always | A human-readable information about which objects were changed. |
