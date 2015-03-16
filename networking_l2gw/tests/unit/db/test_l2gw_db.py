# Copyright 2015 OpenStack Foundation
# Copyright (c) 2015 Hewlett-Packard Development Company, L.P.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
import mock

from neutron.callbacks import events
from neutron.callbacks import resources
from neutron import context
from neutron import manager
from neutron.tests.unit import testlib_api

from networking_l2gw.db.l2gateway import l2gateway_db
from networking_l2gw.services.l2gateway.common import constants
from networking_l2gw.services.l2gateway import exceptions

from oslo.utils import importutils
from oslo_log import log as logging

DB_PLUGIN_KLASS = 'neutron.db.db_base_plugin_v2.NeutronDbPluginV2'
LOG = logging.getLogger(__name__)


class L2GWTestCase(testlib_api.SqlTestCase):

    """Unit test for l2 Gateway DB support."""

    def setUp(self):
        super(L2GWTestCase, self).setUp()
        self.ctx = context.get_admin_context()
        self.mixin = l2gateway_db.L2GatewayMixin()
        self.gw_resource = constants.L2_GATEWAYS
        self.con_resource = constants.CONNECTION_RESOURCE_NAME
        self.plugin = importutils.import_object(DB_PLUGIN_KLASS)

    def _create_l2gateway(self, l2gateway):
        """Create l2gateway helper method."""
        with self.ctx.session.begin(subtransactions=True):
            return self.mixin.create_l2_gateway(self.ctx, l2gateway)

    def _get_l2_gateway_data(self, name, device_name):
        """Get l2 gateway data helper method."""
        data = {"l2_gateway": {"name": name,
                               "devices":
                               [{"interfaces": [{"name": "port1",
                                                 "segmentation_id": ["111"]}],
                                 "device_name": device_name}]}}
        return data

    def _get_l2_gateway_data_with_multiple_segid(self, name, device_name):
        """Get l2 gateway data helper method for multiple seg id."""
        data = {"l2_gateway": {"name": name,
                               "devices":
                               [{"interfaces": [{"name": "port1",
                                                 "segmentation_id": ["111",
                                                                     "123"]}],
                                 "device_name": device_name}]}}
        return data

    def _get_l2_gateway_multiple_interface_data(self, name, device_name):
        """Get l2 gateway data helper method with multiple interface data."""
        data = {"l2_gateway": {"name": name,
                               "devices":
                               [{"interfaces": [{"name": "port1",
                                                 "segmentation_id": ["4076"]},
                                                {"name": "port1",
                                                 "segmentation_id": ["4074"]}],
                                 "device_name": device_name}]}}
        return data

    def _get_l2_gw_multiple_interface_partial_seg_id_data(self, name,
                                                          device_name):
        """Get l2 gateway data helper method with partial seg id."""
        data = {"l2_gateway": {"name": name,
                               "devices":
                               [{"interfaces": [{"name": "port1",
                                                 "segmentation_id": ["4076"]},
                                                {"name": "port1"}],
                                 "device_name": device_name}]}}
        return data

    def _get_nw_data(self):
        return {'network': {'id': 'fake-id',
                            'name': 'net1',
                            'admin_state_up': True,
                            'tenant_id': 'test-tenant',
                            'shared': False}}

    def _get_l2_gateway_data_without_seg_id(self, name, device_name):
        """Get l2 gateway data helper method."""
        data = {"l2_gateway": {"name": name,
                               "devices":
                               [{"interfaces": [{"name": "port1"}],
                                "device_name": device_name}]}}
        return data

    def test_l2_gateway_create(self):
        """Test l2 gateway create."""
        name = "l2gw_1"
        device_name = "device1"
        data = self._get_l2_gateway_data(name, device_name)
        result = self._create_l2gateway(data)
        self.assertEqual(result['name'], name)

    def _get_l2_gateways(self):
        """Update l2gateway helper."""
        with self.ctx.session.begin(subtransactions=True):
            return self.mixin.get_l2_gateways(self.ctx)

    def test_l2gateway_list(self):
        """Test l2 gateway list."""
        name = "l2gw_1"
        device_name = "device1"
        data = self._get_l2_gateway_data(name, device_name)
        self._create_l2gateway(data)
        result2 = self._get_l2_gateways()
        self.assertIn('id', result2[0])

    def _update_l2_gateway(self, id, l2gateway):
        """Update l2gateway helper."""
        with self.ctx.session.begin(subtransactions=True):
            return self.mixin.update_l2_gateway(self.ctx, id, l2gateway)

    def test_l2_gateway_update(self):
        """Test l2 gateway update."""
        name_create = "l2gw_1"
        name_update = "l2gw_2"
        device_name = "device1"
        data_l2gw_create = self._get_l2_gateway_data(name_create,
                                                     device_name)
        gw_org = self._create_l2gateway(data_l2gw_create)
        l2gw_id = gw_org['id']
        l2_gw_update_dict = self._get_l2_gateway_data(name_update,
                                                      device_name)
        result = self._update_l2_gateway(l2gw_id, l2_gw_update_dict)
        self.assertNotEqual(result['name'], name_create)

    def test_l2_gateway_update_without_devices(self):
        """Test l2 gateway update without devices."""
        name_create = "l2gw_1"
        name_update = "l2gw_updated"
        device_name = "device1"
        data_l2gw_create = self._get_l2_gateway_data(name_create,
                                                     device_name)
        gw_org = self._create_l2gateway(data_l2gw_create)
        l2gw_id = gw_org['id']
        l2_gw_update_dict = {"l2_gateway": {"name": name_update}}
        result = self._update_l2_gateway(l2gw_id, l2_gw_update_dict)
        self.assertNotEqual(result['name'], name_create)
        self.assertEqual(result['name'], name_update)

    def _create_l2gateway_connection(self, l2gateway_con):
        """Create L2 gateway connection resource helper method."""
        with self.ctx.session.begin(subtransactions=True):
            return self.mixin.create_l2_gateway_connection(self.ctx,
                                                           l2gateway_con)

    def _list_l2gateway_connection(self):
        """Create L2 gateway connection resource helper method."""
        with self.ctx.session.begin(subtransactions=True):
            return self.mixin.get_l2_gateway_connections(self.ctx)

    def test_l2gateway_connection_create_delete_list(self):
        """Test l2 gateway connection create and delete."""
        name = "l2gw_con1"
        device_name = "device_name1"
        data_l2gw = self._get_l2_gateway_data(name, device_name)
        gw = self._create_l2gateway(data_l2gw)
        net_data = self._get_nw_data()
        net = self.plugin.create_network(self.ctx, net_data)
        l2gw_id = gw['id']
        data_con = {self.con_resource: {'l2_gateway_id': l2gw_id,
                                        'network_id': net['id']}}
        gw_con = self._create_l2gateway_connection(data_con)
        exp_net_id = gw_con['network_id']
        self.assertEqual(net['id'], exp_net_id)
        cn_id = gw_con['id']
        list_con = self._list_l2gateway_connection()
        self.assertIn('id', list_con[0])
        result = self._delete_l2gw_connection(cn_id)
        self.assertIsNone(result)

    def test_l2gateway_con_create_and_delete_in_use_without_seg_id(self):
        """Test l2 gateway connection create without seg id when use."""
        name = "l2gw_con2"
        device_name = "device_name2"
        data_l2gw = self._get_l2_gateway_data(name,
                                              device_name)
        gw = self._create_l2gateway(data_l2gw)
        net_data = self._get_nw_data()
        net = self.plugin.create_network(self.ctx, net_data)
        l2gw_id = gw['id']
        data_con = {self.con_resource: {'l2_gateway_id': l2gw_id,
                                        'network_id': net['id']}}
        self._create_l2gateway_connection(data_con)
        self.assertRaises(exceptions.L2GatewayInUse,
                          self._delete_l2gateway, l2gw_id)

    def _delete_l2gateway(self, l2gw_id):
        """Delete l2 gateway helper method."""
        with self.ctx.session.begin(subtransactions=True):
            return self.mixin.delete_l2_gateway(self.ctx,
                                                l2gw_id)

    def test_l2gateway_delete(self):
        """Test l2 gateway delete."""
        data_l2gw = self._get_l2_gateway_data("gateway_delete",
                                              "device_name")
        gw_actual = self._create_l2gateway(data_l2gw)
        l2gw_id = gw_actual['id']
        result = self._delete_l2gateway(l2gw_id)
        self.assertIsNone(result)

    def _delete_l2gw_connection(self, con_id):
        """Delete l2 gateway connection."""
        with self.ctx.session.begin(subtransactions=True):
            return self.mixin.delete_l2_gateway_connection(self.ctx, con_id)

    def test_l2_gateway_create_with_mul_interfaces(self):
        """Test l2 gateway create with multiple interfaces all seg id."""
        name = "l2gw_1"
        device_name = "device1"
        data = self._get_l2_gateway_multiple_interface_data(name, device_name)
        result = self._create_l2gateway(data)
        self.assertEqual(result['name'], name)

    def test_l2_gateway_create_with_mul_interfaces_inconsitent_seg_id(self):
        """Test l2 gateway create with multiple interfaces."""
        name = "l2gw_1"
        dev_name = "device1"
        data = self._get_l2_gw_multiple_interface_partial_seg_id_data(name,
                                                                      dev_name)
        self.assertRaises(exceptions.L2GatewaySegmentationRequired,
                          self._create_l2gateway, data)

    def test_l2_gateway_create_with_multiple_segid(self):
        """Test l2 gateway create with multiple seg id."""
        name = "l2gw_1"
        device_name = "device1"
        data = self._get_l2_gateway_data_with_multiple_segid(name, device_name)
        result = self._create_l2gateway(data)
        self.assertEqual(result['name'], name)

    def test_l2_gateway_update_invalid_device_name(self):
        """Test l2 gateway update with invalid device name."""
        name_create = "l2gw_1"
        device_name = "device1"
        invalid_device_name = "invalid_device"
        data_l2gw_create = self._get_l2_gateway_data(name_create,
                                                     device_name)
        data_l2gw_update = self._get_l2_gateway_data(name_create,
                                                     invalid_device_name)
        gw_org = self._create_l2gateway(data_l2gw_create)
        l2gw_id = gw_org['id']
        self.assertRaises(exceptions.L2GatewayDeviceNotFound,
                          self._update_l2_gateway, l2gw_id, data_l2gw_update)

    def test_l2gw_callback_add_port(self):
        service_plugins = mock.MagicMock()
        fake_context = mock.Mock()
        fake_port = mock.Mock()
        fake_kwargs = {'context': fake_context,
                       'port': fake_port}
        with mock.patch.object(manager.NeutronManager,
                               'get_service_plugins',
                               return_value=service_plugins):
            l2gateway_db.l2gw_callback(resources.PORT,
                                       events.AFTER_CREATE,
                                       mock.Mock(),
                                       **fake_kwargs)
            service_plugins.return_value[constants.L2GW
                                         ].add_port_mac.assert_called()

    def test_l2gw_callback_update_port(self):
        service_plugins = mock.MagicMock()
        fake_context = mock.Mock()
        fake_port = mock.Mock()
        fake_kwargs = {'context': fake_context,
                       'port': fake_port}
        with mock.patch.object(manager.NeutronManager,
                               'get_service_plugins',
                               return_value=service_plugins):
            l2gateway_db.l2gw_callback(resources.PORT,
                                       events.AFTER_UPDATE,
                                       mock.Mock(),
                                       **fake_kwargs)
            service_plugins.return_value[constants.L2GW
                                         ].add_port_mac.assert_called()

    def test_l2gw_callback_delete_port(self):
        service_plugins = mock.MagicMock()
        fake_context = mock.Mock()
        fake_port = mock.Mock()
        fake_kwargs = {'context': fake_context,
                       'port': fake_port}
        with mock.patch.object(manager.NeutronManager,
                               'get_service_plugins',
                               return_value=service_plugins):
            l2gateway_db.l2gw_callback(resources.PORT,
                                       events.AFTER_DELETE,
                                       mock.Mock(),
                                       **fake_kwargs)
            service_plugins.return_value[constants.L2GW
                                         ].delete_port_mac.assert_called()
