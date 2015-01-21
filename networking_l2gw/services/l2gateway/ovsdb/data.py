# Copyright (c) 2015 OpenStack Foundation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from neutron import context as ctx
from neutron.openstack.common import log as logging

from networking_l2gw.services.l2gateway.common import constants as n_const
from networking_l2gw.services.l2gateway.common import topics
from networking_l2gw.services.l2gateway.ovsdb import lib as db
from networking_l2gw.services.l2gateway import plugin as l2gw_plugin

from oslo.config import cfg
from oslo import messaging

LOG = logging.getLogger(__name__)


class L2GatewayOVSDBCallbacks(object):
    """Implement the rpc call back functions from OVSDB."""

    target = messaging.Target(version='1.0')

    def __init__(self, plugin):
        super(L2GatewayOVSDBCallbacks, self).__init__()
        self.plugin = plugin
        context = ctx.get_admin_context()
        self.agent_rpc = l2gw_plugin.L2gatewayAgentApi(
            topics.L2GATEWAY_AGENT, context, cfg.CONF.host)

    def update_ovsdb_changes(self, context, ovsdb_data):
        """RPC to update the changes from OVSDB in the database."""
        self.ovsdb = OVSDBData(
            ovsdb_data.get(n_const.OVSDB_IDENTIFIER))
        self.ovsdb.update_ovsdb_changes(context, ovsdb_data)


class OVSDBData(object):
    """Process the data coming from OVSDB."""

    def __init__(self, ovsdb_identifier=None):
        self.ovsdb_identifier = ovsdb_identifier
        self._setup_entry_table()

    def update_ovsdb_changes(self, context, ovsdb_data):
        """RPC to update the changes from OVSDB in the database."""

        for item, value in ovsdb_data.items():
            if item != n_const.OVSDB_IDENTIFIER:
                self.entry_table.get(item)(context, value)

    def _setup_entry_table(self):
        self.entry_table = {'new_logical_switches':
                            self._process_new_logical_switches,
                            'new_physical_ports':
                            self._process_new_physical_ports,
                            'new_physical_switches':
                            self._process_new_physical_switches,
                            'new_physical_locators':
                            self._process_new_physical_locators,
                            'new_local_macs':
                            self._process_new_local_macs,
                            'new_remote_macs':
                            self._process_new_remote_macs,
                            'modified_physical_ports':
                            self._process_modified_physical_ports,
                            'deleted_logical_switches':
                            self._process_deleted_logical_switches,
                            'deleted_physical_ports':
                            self._process_deleted_physical_ports,
                            'deleted_physical_switches':
                            self._process_deleted_physical_switches,
                            'deleted_physical_locators':
                            self._process_deleted_physical_locators,
                            'deleted_local_macs':
                            self._process_deleted_local_macs,
                            'deleted_remote_macs':
                            self._process_deleted_remote_macs,
                            }

        return

    def _process_new_logical_switches(self,
                                      context,
                                      new_logical_switches):
        for logical_switch in new_logical_switches:
            ls_dict = logical_switch
            ls_dict[n_const.OVSDB_IDENTIFIER] = self.ovsdb_identifier
            l_switch = db.get_logical_switch(context, ls_dict)
            if not l_switch:
                db.add_logical_switch(context, ls_dict)

    def _process_new_physical_switches(self,
                                       context,
                                       new_physical_switches):
        for physical_switch in new_physical_switches:
            ps_dict = physical_switch
            ps_dict[n_const.OVSDB_IDENTIFIER] = self.ovsdb_identifier
            if (ps_dict.get('tunnel_ip'))[0] == 'set':
                ps_dict['tunnel_ip'] = None
            p_switch = db.get_physical_switch(context, ps_dict)
            if not p_switch:
                db.add_physical_switch(context, ps_dict)

    def _process_new_physical_ports(self,
                                    context,
                                    new_physical_ports):
        for physical_port in new_physical_ports:
            pp_dict = physical_port
            pp_dict[n_const.OVSDB_IDENTIFIER] = self.ovsdb_identifier
            p_port = db.get_physical_port(context, pp_dict)
            if not p_port:
                db.add_physical_port(context, pp_dict)
            if pp_dict.get('vlan_bindings'):
                for vlan_binding in pp_dict.get('vlan_bindings'):
                    vlan_binding[
                        n_const.OVSDB_IDENTIFIER] = self.ovsdb_identifier
                    vlan_binding['port_uuid'] = pp_dict.get('uuid')
                    v_binding = db.get_vlan_binding(context, vlan_binding)
                    if not v_binding:
                        db.add_vlan_binding(context, vlan_binding)

    def _process_new_physical_locators(self,
                                       context,
                                       new_physical_locators):
        for physical_locator in new_physical_locators:
            pl_dict = physical_locator
            pl_dict[n_const.OVSDB_IDENTIFIER] = self.ovsdb_identifier
            p_locator = db.get_physical_locator(context, pl_dict)
            if not p_locator:
                db.add_physical_locator(context, pl_dict)

    def _process_new_local_macs(self,
                                context,
                                new_local_macs):
        for local_mac in new_local_macs:
            lm_dict = local_mac
            lm_dict[n_const.OVSDB_IDENTIFIER] = self.ovsdb_identifier
            lm_dict['logical_switch_uuid'] = local_mac.get('logical_switch_id')
            l_mac = db.get_ucast_mac_local(context, lm_dict)
            if not l_mac:
                db.add_ucast_mac_local(context, lm_dict)

    def _process_new_remote_macs(self,
                                 context,
                                 new_remote_macs):
        for remote_mac in new_remote_macs:
            rm_dict = remote_mac
            rm_dict[n_const.OVSDB_IDENTIFIER] = self.ovsdb_identifier
            r_mac = db.get_ucast_mac_remote(context, rm_dict)
            if not r_mac:
                db.add_ucast_mac_remote(context, rm_dict)

    def _process_modified_physical_ports(self,
                                         context,
                                         modified_physical_ports):
        for physical_port in modified_physical_ports:
            pp_dict = physical_port
            pp_dict[n_const.OVSDB_IDENTIFIER] = self.ovsdb_identifier
            modified_port = db.get_physical_port(context, pp_dict)
            if modified_port:
                port_vlan_bindings = physical_port.get('vlan_bindings')
                vlan_bindings = db.get_all_vlan_bindings_by_physical_port(
                    context, pp_dict)
                for vlan_binding in vlan_bindings:
                    db.delete_vlan_binding(context, vlan_binding)
                for port_vlan_binding in port_vlan_bindings:
                    port_vlan_binding['port_uuid'] = pp_dict['uuid']
                    port_vlan_binding[
                        n_const.OVSDB_IDENTIFIER] = self.ovsdb_identifier
                    db.add_vlan_binding(context, port_vlan_binding)
            else:
                db.add_physical_port(context, pp_dict)

    def _process_deleted_logical_switches(self,
                                          context,
                                          deleted_logical_switches):
        for logical_switch in deleted_logical_switches:
            ls_dict = logical_switch
            ls_dict[n_const.OVSDB_IDENTIFIER] = self.ovsdb_identifier
            db.delete_logical_switch(context, ls_dict)

    def _process_deleted_physical_switches(self,
                                           context,
                                           deleted_physical_switches):
        for physical_switch in deleted_physical_switches:
            ps_dict = physical_switch
            ps_dict[n_const.OVSDB_IDENTIFIER] = self.ovsdb_identifier
            db.delete_physical_switch(context, ps_dict)

    def _process_deleted_physical_ports(self,
                                        context,
                                        deleted_physical_ports):
        for physical_port in deleted_physical_ports:
            pp_dict = physical_port
            pp_dict[n_const.OVSDB_IDENTIFIER] = self.ovsdb_identifier
            db.delete_physical_port(context, pp_dict)

    def _process_deleted_physical_locators(self,
                                           context,
                                           deleted_physical_locators):
        for physical_locator in deleted_physical_locators:
            pl_dict = physical_locator
            pl_dict[n_const.OVSDB_IDENTIFIER] = self.ovsdb_identifier
            db.delete_physical_locator(context, pl_dict)

    def _process_deleted_local_macs(self,
                                    context,
                                    deleted_local_macs):
        for local_mac in deleted_local_macs:
            lm_dict = local_mac
            lm_dict[n_const.OVSDB_IDENTIFIER] = self.ovsdb_identifier
            db.delete_ucast_mac_local(context, lm_dict)

    def _process_deleted_remote_macs(self,
                                     context,
                                     deleted_remote_macs):
        for remote_mac in deleted_remote_macs:
            rm_dict = remote_mac
            rm_dict[n_const.OVSDB_IDENTIFIER] = self.ovsdb_identifier
            db.delete_ucast_mac_remote(context, rm_dict)