# -*- coding: utf-8 -*-

from ..qcloudsdkcore.request import Request

class EipBindBmNatGatewayRequest(Request):

    def __init__(self):
        super(EipBindBmNatGatewayRequest, self).__init__(
            'bmvpc', 'qcloudcliV1', 'EipBindBmNatGateway', 'bmvpc.api.qcloud.com')

    def get_assignedEipSet(self):
        return self.get_params().get('assignedEipSet')

    def set_assignedEipSet(self, assignedEipSet):
        self.add_param('assignedEipSet', assignedEipSet)

    def get_autoAllocEipNum(self):
        return self.get_params().get('autoAllocEipNum')

    def set_autoAllocEipNum(self, autoAllocEipNum):
        self.add_param('autoAllocEipNum', autoAllocEipNum)

    def get_natId(self):
        return self.get_params().get('natId')

    def set_natId(self, natId):
        self.add_param('natId', natId)

    def get_unVpcId(self):
        return self.get_params().get('unVpcId')

    def set_unVpcId(self, unVpcId):
        self.add_param('unVpcId', unVpcId)

    def get_vpcId(self):
        return self.get_params().get('vpcId')

    def set_vpcId(self, vpcId):
        self.add_param('vpcId', vpcId)
