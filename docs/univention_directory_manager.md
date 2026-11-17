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
+superordinate (string) | None | When creating a new object, set its superordinate to this DN. Only affects newly created LDAP objects, this option is ingored for modifications and removals of existing entries.
set_properties (list) | | A list of dictionaries with the keys property and value. Properties of the objects are to be set to the given values. For multivalued properties the values are added to the existing ones.
unset_properties (list) | | A list of dictionaries with the key property and optional key value. The listed properties are unset. For multivalued properties with a value, only that value is removed; without value all values are removed.
policies (list) | | A list of policies to apply to the given object. You have to define all policies you expect at the users object.

## Notes

### Multivalued properties

- `set_properties`: for a multivalued property (e.g. `groups`) the given value, a single value or a list of values, is **added** to the existing values. Existing values are kept and values already present are not duplicated, so repeated runs are idempotent. To remove values, use `unset_properties`.
- **Exception, dict values overwrite:** if the value is a dictionary (e.g. `displayName` with `en_US: ...`, `de_DE: ...`), the property is **set as a whole** and replaces the existing value. It is not merged.
- `unset_properties`:
  - Only `property`: all values of the property are removed.
  - `property` and `value` (single value or list): only these values are removed, all others are kept.
  - For single-valued properties `value` is ignored and the property is always unset.
- Some values cannot be removed because UDM requires them, e.g. the primary group of a user always stays in `groups`.

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

# create an extended attribute
- name: "create an extended attribute with superordinary param and complex attributes"
  univention_directory_manager:
    module: "settings/extended_attribute"
    superordinate: "cn=custom attributes,cn=univention,dc=example,dc=org"
    state: "present"
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

# remove a single value of a multivalued property
- name: modify testuser3 - remove from one group only
  univention_directory_manager:
    module: 'users/user'
    state: 'present'
    filter: '(uid=testuser3)'
    unset_properties:
      - property: 'groups'
        value: 'cn=local users,cn=groups,$ldap_base'

# assign a policy
- name: modify testuser3 - assign policy
  univention_directory_manager:
    module: 'users/user'
    state: 'present'
    filter: '(uid=testuser3)'
    policies:
      - "cn=udm-license,cn=operations,cn=UMC,cn=univention,dc=example,dc=org"
      - "cn=anotherone,cn=operations,cn=UMC,cn=univention,dc=example,dc=org"
      -
 ```

## Return Values
Key | Returned | Description
--- | --- | ---
`meta['changed_objects']`(list) | always | A list of all objects that were changed. |
`message`(string) | always | A human-readable information about which objects were changed. |
