# Copyright 2015 OpenStack Foundation.
# All Rights Reserved
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#

from neutronclient.common import utils
from neutronclient.i18n import _
from neutronclient.neutron import v2_0 as l2gatewayV20
from oslo_serialization import jsonutils

L2_GW = 'l2_gateway'
INTERFACE_DELIMITER = ";"
SEGMENTATION_ID_DELIMITER = "#"
INTERFACE_SEG_ID_DELIMITER = "|"


def _format_devices(l2_gateway):
    try:
        return '\n'.join([jsonutils.dumps(gateway) for gateway in
                          l2_gateway['devices']])
    except (TypeError, KeyError):
        return ''


def get_interface(interfaces):
    interface_dict = []
    for interface in interfaces:
        if INTERFACE_SEG_ID_DELIMITER in interface:
            int_name = interface.split(INTERFACE_SEG_ID_DELIMITER)[0]
            segid = interface.split(INTERFACE_SEG_ID_DELIMITER)[1]
            if SEGMENTATION_ID_DELIMITER in segid:
                segid = segid.split(SEGMENTATION_ID_DELIMITER)
            else:
                segid = [segid]
            interface_detail = {'name': int_name, 'segmentation_id': segid}
        else:
            interface_detail = {'name': interface}
        interface_dict.append(interface_detail)
    return interface_dict


def add_known_arguments(self, parser):
    parser.add_argument(
        '--device',
        metavar='name=name,interface_names=INTERFACE-DETAILS',
        action='append', dest='devices', type=utils.str2dict,
        help=_('Device name and Interface-names of l2gateway. '
               'INTERFACE-DETAILS is of form '
               '\"<interface_name1>;[<interface_name2>]'
               '[|<seg_id1>[#<seg_id2>]]\" '
               '(--device option can be repeated)'))


def args2body(self, parsed_args):
    if parsed_args.devices:
        devices = parsed_args.devices
        interfaces = []
    else:
        devices = []
    device_dict = []
    for device in devices:
        if 'interface_names' in device.keys():
            interface = device['interface_names']
            if INTERFACE_DELIMITER in interface:
                interface_dict = interface.split(INTERFACE_DELIMITER)
                interfaces = get_interface(interface_dict)
            else:
                interfaces = get_interface([interface])
        if 'name' in device.keys():
            device = {'device_name': device['name'],
                      'interfaces': interfaces}
        else:
            device = {'interfaces': interfaces}
        device_dict.append(device)
    if parsed_args.name:
        l2gw_name = parsed_args.name
        body = {'l2_gateway': {'name': l2gw_name,
                               'devices': device_dict}, }
    else:
        body = {'l2_gateway': {'devices': device_dict}, }
    return body


class Listl2gateway(l2gatewayV20.ListCommand):
    """List l2gateway that belongs to a given tenant."""

    resource = L2_GW
    _formatters = {'devices': _format_devices, }
    list_columns = ['id', 'name', 'devices']
    pagination_support = True
    sorting_support = True


class Showl2gateway(l2gatewayV20.ShowCommand):
    """Show information of a given l2gateway."""

    resource = L2_GW


class Deletel2gateway(l2gatewayV20.DeleteCommand):
    """Delete a given l2gateway."""

    resource = L2_GW


class Createl2gateway(l2gatewayV20.CreateCommand):
    """Create l2gateway information."""

    resource = L2_GW

    def add_known_arguments(self, parser):
        parser.add_argument(
            'name', metavar='<GATEWAY-NAME>',
            help=_('Descriptive name for logical gateway.'))
        add_known_arguments(self, parser)

    def args2body(self, parsed_args):
        body = args2body(self, parsed_args)
        if parsed_args.tenant_id:
            body['l2_gateway']['tenant_id'] = parsed_args.tenant_id
        return body


class Updatel2gateway(l2gatewayV20.UpdateCommand):
    """Update a given l2gateway."""

    resource = L2_GW

    def add_known_arguments(self, parser):
        parser.add_argument(
            '--name', metavar='name',
            help=_('Descriptive name for logical gateway.'))
        add_known_arguments(self, parser)

    def args2body(self, parsed_args):
        if parsed_args.devices:
            body = args2body(self, parsed_args)
        else:
            body = {'l2_gateway': {'name': parsed_args.name}}
        return body
