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
from neutron.callbacks import events
from neutron.callbacks import registry
from neutron.callbacks import resources
from neutron.common import exceptions
from neutron import manager
from neutron.openstack.common import uuidutils

from networking_l2gw.db.l2gateway import db_query
from networking_l2gw.db.l2gateway import l2gateway_models as models
from networking_l2gw.extensions import l2gateway
from networking_l2gw.extensions import l2gatewayconnection
from networking_l2gw.services.l2gateway.common import config
from networking_l2gw.services.l2gateway.common import constants
from networking_l2gw.services.l2gateway.common import l2gw_validators
from networking_l2gw.services.l2gateway import exceptions as l2gw_exc

from oslo_log import log as logging
from sqlalchemy.orm import exc as sa_orm_exc

LOG = logging.getLogger(__name__)


class L2GatewayMixin(l2gateway.L2GatewayPluginBase,
                     db_query.L2GatewayCommonDbMixin,
                     l2gatewayconnection.L2GatewayConnectionPluginBase):
    """Class L2GatewayMixin for handling l2_gateway resource."""
    gateway_resource = constants.GATEWAY_RESOURCE_NAME
    connection_resource = constants.CONNECTION_RESOURCE_NAME
    config.register_l2gw_opts_helper()

    def _get_l2_gateway(self, context, gw_id):
        try:
            gw = context.session.query(models.L2Gateway).get(gw_id)
        except sa_orm_exc.NoResultFound:
            raise l2gw_exc.L2GatewayNotFound(gateway_id=gw_id)
        return gw

    def _get_l2_gateways(self, context):
        return context.session.query(models.L2Gateway).all()

    def _get_l2_gw_interfaces(self, context, id):
        return context.session.query(models.L2GatewayInterface).filter_by(
            device_id=id).all()

    def _is_vlan_configured_on_any_interface_for_l2gw(self,
                                                      context,
                                                      l2gw_id):
        devices_db = self._get_l2_gateway_devices(context, l2gw_id)
        for device_model in devices_db:
            interfaces_db = self._get_l2_gw_interfaces(context,
                                                       device_model.id)
            for int_model in interfaces_db:
                query = context.session.query(models.L2GatewayInterface)
                int_db = query.filter_by(id=int_model.id).first()
                seg_id = int_db[constants.SEG_ID]
                if seg_id > 0:
                    return True
        return False

    def _get_l2_gateway_devices(self, context, l2gw_id):
        return context.session.query(models.L2GatewayDevice).filter_by(
            l2_gateway_id=l2gw_id).all()

    def _get_l2gw_devices_by_name_andl2gwid(self, context, device_name,
                                            l2gw_id):
        return context.session.query(models.L2GatewayDevice).filter_by(
            device_name=device_name, l2_gateway_id=l2gw_id).all()

    def _get_l2_gateway_connection(self, context, cn_id):
        try:
            con = context.session.query(models.L2GatewayConnection).get(cn_id)
        except sa_orm_exc.NoResultFound:
            raise l2gw_exc.L2GatewayConnectionNotFound(id=cn_id)
        return con

    def _make_l2gw_connections_dict(self, gw_conn, fields=None):
        if gw_conn is None:
            raise l2gw_exc.L2GatewayConnectionNotFound(id="")
        segmentation_id = gw_conn['segmentation_id']
        if segmentation_id == 0:
            segmentation_id = ""
        res = {'id': gw_conn['id'],
               'network_id': gw_conn['network_id'],
               'l2_gateway_id': gw_conn['l2_gateway_id'],
               'tenant_id': gw_conn['tenant_id'],
               'segmentation_id': segmentation_id
               }
        return self._fields(res, fields)

    def _make_l2_gateway_dict(self, l2_gateway, fields=None):
        device_list = []
        for d in l2_gateway.devices:
            interface_list = []
            for interfaces_db in d.interfaces:
                seg_id = interfaces_db[constants.SEG_ID]
                if seg_id == 0:
                    seg_id = ""
                interface_list.append({'name':
                                       interfaces_db['interface_name'],
                                       constants.SEG_ID:
                                       seg_id})
            device_list.append({'device_name': d['device_name'],
                                'id': d['id'],
                                'interfaces': interface_list})
        res = {'id': l2_gateway['id'],
               'name': l2_gateway['name'],
               'devices': device_list,
               'tenant_id': l2_gateway['tenant_id']}
        return self._fields(res, fields)

    def _set_mapping_info_defaults(self, mapping_info):
        if not mapping_info.get(constants.SEG_ID):
            mapping_info[constants.SEG_ID] = 0

    def _retrieve_gateway_connections(self, context, gateway_id,
                                      mapping_info={}, only_one=False):
        filters = {'l2_gateway_id': [gateway_id]}
        for k, v in mapping_info.iteritems():
            if v and k != constants.SEG_ID:
                filters[k] = [v]
        query = self._get_collection_query(context,
                                           models.L2GatewayConnection,
                                           filters)
        return query.one() if only_one else query.all()

    def create_l2_gateway(self, context, l2_gateway):
        """Create a logical gateway."""
        self._admin_check(context, 'CREATE')
        gw = l2_gateway[self.gateway_resource]
        tenant_id = self._get_tenant_id_for_create(context, gw)
        devices = gw['devices']
        self._validate_any_seg_id_empty_in_interface_dict(devices)
        with context.session.begin(subtransactions=True):
                gw_db = models.L2Gateway(
                    id=gw.get('id', uuidutils.generate_uuid()),
                    tenant_id=tenant_id,
                    name=gw.get('name'))
                context.session.add(gw_db)
                l2gw_device_dict = {}
                for device in devices:
                    l2gw_device_dict['l2_gateway_id'] = id
                    device_name = device['device_name']
                    l2gw_device_dict['device_name'] = device_name
                    l2gw_device_dict['id'] = uuidutils.generate_uuid()
                    uuid = self._generate_uuid()
                    dev_db = models.L2GatewayDevice(id=uuid,
                                                    l2_gateway_id=gw_db.id,
                                                    device_name=device_name)
                    context.session.add(dev_db)
                    for interface_list in device['interfaces']:
                        int_name = interface_list.get('name')
                        if constants.SEG_ID in interface_list:
                            seg_id_list = interface_list.get(constants.SEG_ID)
                            for seg_ids in seg_id_list:
                                uuid = self._generate_uuid()
                                interface_db = self._get_int_model(uuid,
                                                                   int_name,
                                                                   dev_db.id,
                                                                   seg_ids)
                                context.session.add(interface_db)
                        else:
                            uuid = self._generate_uuid()
                            interface_db = self._get_int_model(uuid,
                                                               int_name,
                                                               dev_db.id,
                                                               0)
                            context.session.add(interface_db)
                        context.session.query(models.L2GatewayDevice).all()
        return self._make_l2_gateway_dict(gw_db)

    def update_l2_gateway(self, context, id, l2_gateway):
        """Update l2 gateway."""
        self._admin_check(context, 'UPDATE')
        gw = l2_gateway[self.gateway_resource]
        if 'devices' in gw:
            devices = gw['devices']
        with context.session.begin(subtransactions=True):
                l2gw_db = self._get_l2_gateway(context, id)
                if l2gw_db.network_connections:
                    raise l2gw_exc.L2GatewayInUse(gateway_id=id)
                dev_db = self._get_l2_gateway_devices(context, id)
                if not gw.get('devices'):
                    l2gw_db.name = gw.get('name')
                    return self._make_l2_gateway_dict(l2gw_db)
                for device in devices:
                    dev_name = device['device_name']
                    dev_db = self._get_l2gw_devices_by_name_andl2gwid(context,
                                                                      dev_name,
                                                                      id)
                    if not dev_db:
                        raise l2gw_exc.L2GatewayDeviceNotFound(device_id="")
                    interface_db = self._get_l2_gw_interfaces(context,
                                                              dev_db[0].id)
                    self._delete_l2_gateway_interfaces(context, interface_db)
                    interface_dict_list = []
                    self.validate_device_name(context, dev_name, id)
                    for interfaces in device['interfaces']:
                        interface_dict_list.append(interfaces)
                    self._update_interfaces_db(context, interface_dict_list,
                                               dev_db)
        if gw.get('name'):
            l2gw_db.name = gw.get('name')
        return self._make_l2_gateway_dict(l2gw_db)

    def _update_interfaces_db(self, context, interface_dict_list, device_db):
        for interfaces in interface_dict_list:
            int_name = interfaces.get('name')
            if constants.SEG_ID in interfaces:
                seg_id_list = interfaces.get(constants.SEG_ID)
                for seg_ids in seg_id_list:
                    uuid = self._generate_uuid()
                    int_db = self._get_int_model(uuid,
                                                 int_name,
                                                 device_db[0].id,
                                                 seg_ids)
                    context.session.add(int_db)
            else:
                uuid = self._generate_uuid()
                interface_db = self._get_int_model(uuid,
                                                   int_name,
                                                   device_db[0].id,
                                                   0)
                context.session.add(interface_db)

    def get_l2_gateway(self, context, id, fields=None):
        """get the l2 gateway by id."""
        self._admin_check(context, 'GET')
        gw_db = self._get_l2_gateway(context, id)
        if gw_db:
            return self._make_l2_gateway_dict(gw_db, fields)
        else:
            return []

    def delete_l2_gateway(self, context, id):
        """delete the l2 gateway  by id."""
        self._admin_check(context, 'DELETE')
        with context.session.begin(subtransactions=True):
            gw_db = self._get_l2_gateway(context, id)
            if gw_db is None:
                raise l2gw_exc.L2GatewayNotFound(gateway_id=id)
            if gw_db.network_connections:
                raise l2gw_exc.L2GatewayInUse(gateway_id=id)
            context.session.delete(gw_db)
        LOG.debug("l2 gateway '%s' was deleted.", id)

    def get_l2_gateways(self, context, filters=None, fields=None,
                        sorts=None,
                        limit=None,
                        marker=None,
                        page_reverse=False):
        """list the l2 gateways available in the neutron DB."""
        self._admin_check(context, 'GET')
        marker_obj = self._get_marker_obj(
            context, 'l2_gateway', limit, marker)
        return self._get_collection(context, models.L2Gateway,
                                    self._make_l2_gateway_dict,
                                    filters=filters, fields=fields,
                                    sorts=sorts, limit=limit,
                                    marker_obj=marker_obj,
                                    page_reverse=page_reverse)

    def _update_segmentation_id(self, context, l2gw_id, segmentation_id):
        """Update segmentation id for interfaces."""
        device_db = self._get_l2_gateway_devices(context, l2gw_id)
        for device_model in device_db:
            interface_db = self._get_l2_gw_interfaces(context,
                                                      device_model.id)
            for interface_model in interface_db:
                interface_model.segmentation_id = segmentation_id

    def _delete_l2_gateway_interfaces(self, context, int_db_list):
        """delete the l2 interfaces  by id."""
        with context.session.begin(subtransactions=True):
            for interfaces in int_db_list:
                context.session.delete(interfaces)
        LOG.debug("l2 gateway interfaces was deleted.")

    def create_l2_gateway_connection(self, context, l2_gateway_connection):
        """Create l2 gateway connection."""
        self._admin_check(context, 'CREATE')
        gw_connection = l2_gateway_connection[self.connection_resource]
        l2_gw_id = gw_connection.get('l2_gateway_id')
        network_id = gw_connection.get('network_id')
        nw_map = {}
        nw_map['network_id'] = network_id
        nw_map['l2_gateway_id'] = l2_gw_id
        segmentation_id = ""
        if constants.SEG_ID in gw_connection:
            segmentation_id = gw_connection.get(constants.SEG_ID)
            nw_map[constants.SEG_ID] = segmentation_id
        is_vlan = self._is_vlan_configured_on_any_interface_for_l2gw(context,
                                                                     l2_gw_id)
        network_id = l2gw_validators.validate_network_mapping_list(nw_map,
                                                                   is_vlan)
        with context.session.begin(subtransactions=True):
            gw_db = self._get_l2_gateway(context, l2_gw_id)
            tenant_id = self._get_tenant_id_for_create(context, gw_db)
            if self._retrieve_gateway_connections(context,
                                                  l2_gw_id,
                                                  nw_map):
                raise l2gw_exc.L2GatewayConnectionExists(mapping=nw_map,
                                                         gateway_id=l2_gw_id)
            nw_map['tenant_id'] = tenant_id
            connection_id = uuidutils.generate_uuid()
            nw_map['id'] = connection_id
            if not segmentation_id:
                nw_map['segmentation_id'] = "0"
            gw_db.network_connections.append(
                models.L2GatewayConnection(**nw_map))
            gw_db = models.L2GatewayConnection(id=connection_id,
                                               tenant_id=tenant_id,
                                               network_id=network_id,
                                               l2_gateway_id=l2_gw_id,
                                               segmentation_id=segmentation_id)
        return self._make_l2gw_connections_dict(gw_db)

    def get_l2_gateway_connections(self, context, filters=None,
                                   fields=None,
                                   sorts=None, limit=None, marker=None,
                                   page_reverse=False):
        """List l2 gateway connections."""
        self._admin_check(context, 'GET')
        marker_obj = self._get_marker_obj(
            context, 'l2_gateway_connection', limit, marker)
        return self._get_collection(context, models.L2GatewayConnection,
                                    self._make_l2gw_connections_dict,
                                    filters=filters, fields=fields,
                                    sorts=sorts, limit=limit,
                                    marker_obj=marker_obj,
                                    page_reverse=page_reverse)

    def get_l2_gateway_connection(self, context, id, fields=None):
        """Get l2 gateway connection."""
        self._admin_check(context, 'GET')
        """Get the l2 gateway  connection  by id."""
        gw_db = self._get_l2_gateway_connection(context, id)
        return self._make_l2gw_connections_dict(gw_db, fields)

    def delete_l2_gateway_connection(self, context, id):
        """Delete the l2 gateway connection by id."""
        self._admin_check(context, 'DELETE')
        with context.session.begin(subtransactions=True):
            gw_db = self._get_l2_gateway_connection(context, id)
            context.session.delete(gw_db)
        LOG.debug("l2 gateway '%s' was destroyed.", id)

    def _admin_check(self, context, action):
        """Admin role check helper."""
        # TODO(selva): his check should be required if the tenant_id is
        # specified inthe request, otherwise the policy.json do a trick
        # this need further revision.
        if not context.is_admin:
            reason = _('Cannot %s resource for non admin tenant') % action
            raise exceptions.AdminRequired(reason=reason)

    def _generate_uuid(self):
        """Generate uuid helper."""
        uuid = uuidutils.generate_uuid()
        return uuid

    def _get_int_model(self, uuid, interface_name, dev_id, seg_id):
        return models.L2GatewayInterface(id=uuid,
                                         interface_name=interface_name,
                                         device_id=dev_id,
                                         segmentation_id=seg_id)

    def get_l2gateway_devices_by_gateway_id(self, context, l2_gateway_id):
        """Get l2gateway_devices_by id."""
        session = context.session
        with session.begin():
            return session.query(models.L2GatewayDevice).filter_by(
                l2_gateway_id=l2_gateway_id).all()

    def get_l2gateway_interfaces_by_device_id(self, context, device_id):
        """Get all l2gateway_interfaces_by device_id."""
        session = context.session
        with session.begin():
            return session.query(models.L2GatewayInterface).filter_by(
                device_id=device_id).all()

    def validate_device_name(self, context, device_name, l2gw_id):
        if device_name:
            devices_db = self._get_l2gw_devices_by_name_andl2gwid(context,
                                                                  device_name,
                                                                  l2gw_id)
        if not devices_db:
            raise l2gw_exc.L2GatewayDeviceNameNotFound(device_name=device_name)

    def _validate_any_seg_id_empty_in_interface_dict(self, devices):
        """Validate segmentation_id for consistency."""
        for device in devices:
            interface_list = device['interfaces']
            if not interface_list:
                raise l2gw_exc.L2GatewayInterfaceRequired()
            if constants.SEG_ID in interface_list[0]:
                for interfaces in interface_list[1:len(interface_list)]:
                    if constants.SEG_ID not in interfaces:
                        raise l2gw_exc.L2GatewaySegmentationRequired()
            if constants.SEG_ID not in interface_list[0]:
                for interfaces in interface_list[1:len(interface_list)]:
                    if constants.SEG_ID in interfaces:
                        raise l2gw_exc.L2GatewaySegmentationRequired()


def l2gw_callback(resource, event, trigger, **kwargs):
    l2gwservice = manager.NeutronManager.get_service_plugins().get(
        constants.L2GW)
    context = kwargs.get('context')
    port_dict = kwargs.get('port')
    if l2gwservice:
        if event in [events.AFTER_CREATE, events.AFTER_UPDATE]:
            l2gwservice.add_port_mac(context, port_dict)
        elif event == events.AFTER_DELETE:
            l2gwservice.delete_port_mac(context, port_dict)


def subscribe():
    interested_events = (events.AFTER_CREATE,
                         events.AFTER_UPDATE,
                         events.AFTER_DELETE)
    for x in interested_events:
        registry.subscribe(
            l2gw_callback, resources.PORT, x)
