"""
Configuration generator for Apple's property-list based mobileconfig
"""
from xml.etree.ElementTree import Element
from xml.etree.ElementTree import SubElement
from xml.etree.ElementTree import tostring

from automx2 import DomainNotFound
from automx2 import InvalidServerType
from automx2 import NoProviderForDomain
from automx2 import NoServersForDomain
from automx2.generators import ConfigGenerator
from automx2.generators import branded_id
from automx2.model import Domain
from automx2.model import Provider
from automx2.util import expand_placeholders
from automx2.util import unique

TYPE_DIRECTION_MAP = {
    'imap': 'Incoming',
    'smtp': 'Outgoing',
}


def _bool_element(parent: Element, key: str, value: bool):
    SubElement(parent, 'key').text = key
    if value:
        v = 'true'
    else:
        v = 'false'
    SubElement(parent, v)


def _int_element(parent: Element, key: str, value: int):
    SubElement(parent, 'key').text = key
    SubElement(parent, 'integer').text = str(value)


def _str_element(parent: Element, key: str, value: str):
    SubElement(parent, 'key').text = key
    SubElement(parent, 'string').text = value


def _subtree(parent: Element, key: str, value):
    if isinstance(value, bool):
        _bool_element(parent, key, value)
    elif isinstance(value, dict):
        p = SubElement(parent, 'dict')
        for k, v in value.items():
            _subtree(p, k, v)
    elif isinstance(value, int):
        _int_element(parent, key, value)
    elif isinstance(value, list):
        SubElement(parent, 'key').text = key
        p = SubElement(parent, 'array')
        for v in value:
            _subtree(p, 'dunno', v)
    else:
        _str_element(parent, key, value)


def _payload(local, domain):
    address = f'{local}@{domain}'
    uuid = unique()
    inner = {
        'EmailAccountDescription': address,
        'EmailAccountName': None,
        'EmailAccountType': 'EmailTypeIMAP',
        'EmailAddress': address,
        'IncomingMailServerAuthentication': 'EmailAuthPassword',
        'IncomingMailServerHostName': None,
        'IncomingMailServerPortNumber': -1,
        'IncomingMailServerUseSSL': None,
        'IncomingMailServerUsername': None,
        'IncomingPassword': None,
        'OutgoingMailServerAuthentication': 'EmailAuthPassword',
        'OutgoingMailServerHostName': None,
        'OutgoingMailServerPortNumber': -1,
        'OutgoingMailServerUseSSL': None,
        'OutgoingMailServerUsername': None,
        'OutgoingPasswordSameAsIncomingPassword': True,
        'PayloadDescription': f'Email account configuration for {address}',
        'PayloadDisplayName': domain,
        'PayloadIdentifier': f'com.apple.mail.managed.{uuid}',
        'PayloadType': 'com.apple.mail.managed',
        'PayloadUUID': uuid,
        'PayloadVersion': 1,
        'SMIMEEnablePerMessageSwitch': False,
        'SMIMEEnabled': False,
        'SMIMEEncryptionEnabled': False,
        'SMIMESigningEnabled': False,
        'allowMailDrop': False,
        'disableMailRecentsSyncing': False,
    }
    uuid = unique()
    outer = {
        'PayloadContent': [inner],
        'PayloadDisplayName': f'Mail account {domain}',
        'PayloadIdentifier': branded_id(uuid),
        'PayloadRemovalDisallowed': False,
        'PayloadType': 'Configuration',
        'PayloadUUID': uuid,
        'PayloadVersion': 1,
    }
    return inner, outer


def _sanitise(data: dict, local: str, domain: str):
    for key, value in data.items():
        if value is None:
            raise TypeError(f'Missing value for payload key "{key}"')
        if isinstance(value, list):
            for v in value:
                _sanitise(v, local, domain)
        elif isinstance(value, dict):
            _sanitise(value, local, domain)
        elif isinstance(value, str):
            new = expand_placeholders(value, local, domain)
            data[key] = new


def _use_ssl(authentication: str) -> bool:
    if 'SSL' == authentication or 'STARTTLS' == authentication:
        return True
    return False


class AppleGenerator(ConfigGenerator):
    def client_config(self, local_part, domain_part: str, realname: str, password: str) -> str:
        domain: Domain = Domain.query.filter_by(name=domain_part).first()
        if not domain:
            raise DomainNotFound(f'Domain "{domain_part}" not found')
        provider: Provider = domain.provider
        if not provider:
            raise NoProviderForDomain(f'No provider for domain "{domain_part}"')
        if not domain.servers:
            raise NoServersForDomain(f'No servers for domain "{domain_part}"')
        inner, outer = _payload(local_part, domain_part)
        for server in domain.servers:
            if server.type not in TYPE_DIRECTION_MAP:
                raise InvalidServerType(f'Invalid server type "{server.type}"')
            direction = TYPE_DIRECTION_MAP[server.type]
            inner[f'{direction}MailServerHostName'] = server.name
            inner[f'{direction}MailServerPortNumber'] = server.port
            inner[f'{direction}MailServerUsername'] = server.user_name
            inner[f'{direction}MailServerUseSSL'] = _use_ssl(server.socket_type)
        inner['EmailAccountName'] = realname
        inner['IncomingPassword'] = password
        _sanitise(outer, local_part, domain_part)
        plist = Element('plist', attrib={'version': '1.0'})
        _subtree(plist, '', outer)
        data = tostring(plist, 'utf-8')
        return data