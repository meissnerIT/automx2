"""
App views: Autoconfigure mail, Mozilla-style.
"""
from flask import Response

from automx2.generators.mozilla import MozillaGenerator
from automx2.views import BaseView


class MailConfig(BaseView):
    def config_response(self, domain_name: str) -> Response:
        data = MozillaGenerator().client_config(domain_name)
        return self.xml_response(data)