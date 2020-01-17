"""
Copyright © 2019-2020 Ralph Seichter

Graciously sponsored by sys4 AG <https://sys4.de/>

This file is part of automx2.

automx2 is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

automx2 is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with automx2. If not, see <https://www.gnu.org/licenses/>.
"""
from collections import namedtuple

from ldap3 import ALL_ATTRIBUTES
from ldap3 import Connection
from ldap3 import Server

from automx2 import log

STATUS_SUCCESS = 0
STATUS_BIND_FAILED = 1
STATUS_NO_MATCH = 2

LookupResult = namedtuple('LookupResult', 'status cn uid')


class LdapAccess:
    def __init__(self, hostname, port=636, use_ssl=True, user=None, password=None) -> None:
        self._server = Server(hostname, port=port, use_ssl=use_ssl)
        self._connection = Connection(self._server, lazy=False, user=user, password=password)

    def lookup(self, search_base: str, search_filter: str) -> LookupResult:
        if not self._connection.bind():
            log.error(f'LDAP bind failed: {self._connection.result}')
            return LookupResult(STATUS_BIND_FAILED, None, None)
        self._connection.search(search_base, search_filter, attributes=ALL_ATTRIBUTES, size_limit=1)
        if self._connection.response:
            cn = uid = None
            for entry in self._connection.response:
                log.debug(f'Found {entry["dn"]}')
                cn = self.get_attribute(entry, 'cn')
                uid = self.get_attribute(entry, 'uid')
            result = LookupResult(STATUS_SUCCESS, cn, uid)
        else:
            result = LookupResult(STATUS_NO_MATCH, None, None)
        self._connection.unbind()
        log.debug(result)
        return result

    @staticmethod
    def get_attribute(entry: dict, attribute_name: str):
        attributes = entry['attributes']
        if attribute_name and attribute_name in attributes:
            value = attributes[attribute_name]
            return value[0]
        elif attribute_name:
            log.warning(f"Attribute '{attribute_name}' not found")
        return None
