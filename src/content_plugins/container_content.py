#
# Copyright (c) 2014 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public License,
# version 2 (GPLv2). There is NO WARRANTY for this software, express or
# implied, including the implied warranties of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. You should have received a copy of GPLv2
# along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.
#
# Red Hat trademarks are not licensed under GPLv2. No permission is
# granted to use or replicate Red Hat trademarks that are incorporated
# in this software or its documentation.
#

"""
A subscription-manager plugin to watch for docker content in
entitlement certificates, and correctly configure to use them.
"""

from subscription_manager import base_plugin
requires_api_version = "1.1"

from subscription_manager.plugin.container import \
    ContainerContentUpdateActionCommand

# Default location where we'll manage hostname specific directories of
# certificates.
HOSTNAME_CERT_DIR = "/etc/docker/certs.d/"


class ContainerContentPlugin(base_plugin.SubManPlugin):
    """Plugin for adding docker content action to subscription-manager"""
    name = "container_content"

    def update_content_hook(self, conduit):
        """
        Hook to update for any Docker content we have.

        Args:
            conduit: An UpdateContentConduit
        """
        conduit.log.info("Updating container content.")
        registry_hostnames = conduit.conf_string('main', 'registry_hostnames')
        conduit.log.info("registry hostnames = %s" % registry_hostnames)
        cmd = ContainerContentUpdateActionCommand(
            ent_source=conduit.ent_source,
            registry_hostnames=registry_hostnames.split(','),
            host_cert_dir=HOSTNAME_CERT_DIR)
        report = cmd.perform()
        conduit.reports.add(report)

    def configure_content_hook(self, conduit):
        conduit.log.debug("YumRepoContentPlugin.configure_content_hook")

        action_invoker = repolib.RepoActionInvoker(ent_source=conduit.ent_source)
        conduit.log.debug("yum configure_content_hook action_invoker=%s", action_invoker)
        conduit.log.debug("conduit.configure_info BEFORE=%s", conduit.content_config)
        result = action_invoker.configure(conduit.content_config)
        conduit.log.debug("yum configure_content_hook result=%s", result)
        conduit.log.debug("conduit.configure_info AFTER=%s", conduit.content_config)

        # FIXME: pass the content config in to the conduit it, modify it, and return it
        conduit.content_config = result

