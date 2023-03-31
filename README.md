# Univention Corporate Server Modules

The Ansible Univention Corporate Server Modules Collections contains a variety of Ansible modules to help automate the
management of Univention Corporate Server instances.

## Compatibilities

### Univention version compatibility

This collection has been tested against following UCS versions: < 4.2

Since UCS 5.0 `ansible_python_interpreter=/usr/bin/python3` is required.

### Ansible version compatibility

This collection has been tested against following Ansible versions: >= 2.11

Plugins and modules within a collection may be tested with only specific Ansible versions. A collection may contain
metadata that identifies these versions.

### Python version compatibility

This collection has been tested against following Python versions: >= 2.7 or >= 3.9

## Included content

### Modules
Name | Description
--- | ---
[univention.ucs_modules.univention_config_registry](./docs/univention_config_registry.md)|Manage Univention Config Registry (UCR) variables
[univention.ucs_modules.univention_directory_manager](./docs/univention_directory_manager.md)|Manage objects via Univention Directory Manager (UDM)

## Installing this collection

You can install the Univention Corporate Server Modules collection with the Ansible Galaxy CLI:

```shell
ansible-galaxy collection install univention.ucs_modules
```

You can also include it in a `requirements.yml` file and install it with `ansible-galaxy collection install -r requirements.yml`, using the format:

```yaml
---
collections:
  - name: "univention.ucs_modules"
    source: "https://galaxy.ansible.com"
```

A specific version of the collection can be installed by using the version keyword in the `requirements.yml` file:

```yaml
---
collections:
  - name: "univention.ucs_modules"
    source: "https://galaxy.ansible.com"
    version: "1.0.0"
```

## Licensing

GNU General Public License v3.0 or later.

See [LICENSE](https://www.gnu.org/licenses/gpl-3.0.txt) to see the full text.
