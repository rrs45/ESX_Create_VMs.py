#!/bin/env python
 
"""Usage: create_vm.py -t <template> -f <config_file>
 
Options:
     -t             : Template Vm name
     -f             : INI config file path
     -h, --help     : Print help
 
"""
from configobj import ConfigObj
from netaddr import IPNetwork
from docopt import docopt
from pyVmomi import vim, vmodl
from pyVim import connect
import time
import sys
import os
 
 
def WaitTask(task, actionName='job', hideResult=False):
    while task.info.state == vim.TaskInfo.State.running:
            time.sleep(2)
     
    if task.info.state == vim.TaskInfo.State.success:
            if task.info.result is not None and not hideResult:
                out = '%s completed successfully, result: %s' % (actionName, task.info.result)
            else:
                out = '%s completed successfully.' % actionName
        else:
        out = '%s did not complete successfully: %s' % (actionName, task.info.error)
            print out
            raise task.info.error # should be a Fault... check XXX
     
    # may not always be applicable, but can't hurt.
        return task.info.result
 
def create_spec(config_file, vm_type, vm_name, DC, NETWORK):
    conf=ConfigObj('%s' %config_file,unrepr=True)
    relospec = vim.vm.RelocateSpec()
    relospec.pool = DC.hostFolder.childEntity[0].resourcePool
    relospec.datastore = [ ds for ds in DC.datastore if ds.name == "%s" %conf['%s' %vm_type]['%s' %vm_name]['datastore']][0]
    i=0
    devices=[]
    adaptermaps=[]
     
    for net , ip in conf['%s' %vm_type]['%s' %vm_name]['network']['IP_list'].iteritems():
        i+=1
        print "IP: %s, mask: %s" %( ip.split('/')[0], str(IPNetwork('%s' %ip).netmask ))
        nic = vim.vm.device.VirtualDeviceSpec()
        nic.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
        nic.device = vim.vm.device.VirtualVmxnet3()
        nic.device.wakeOnLanEnabled = True
        nic.device.addressType = 'assigned'
        nic.device.key = 4000
        nic.device.deviceInfo = vim.Description()
        nic.device.deviceInfo.label = "Network Adapter %s " %i
        nic.device.deviceInfo.summary = "%s" %net
        nic.device.backing = vim.vm.device.VirtualEthernetCard.NetworkBackingInfo()
        nic.device.backing.network = [n for n in NETWORK if n.name == '%s' %net][0]
        nic.device.backing.deviceName = "%s" %net
        nic.device.backing.useAutoDetect = False
        nic.device.connectable = vim.vm.device.VirtualDevice.ConnectInfo()
        nic.device.connectable.startConnected = True
        nic.device.connectable.allowGuestControl = True
        devices.append(nic)
        guest_map = vim.vm.customization.AdapterMapping()
        guest_map.adapter = vim.vm.customization.IPSettings()
        guest_map.adapter.ip = vim.vm.customization.FixedIp()
        guest_map.adapter.ip.ipAddress = ip.split('/')[0]
        guest_map.adapter.subnetMask = str(IPNetwork('%s' %ip).netmask)
        adaptermaps.append(guest_map)
    vmconf = vim.vm.ConfigSpec()
    vmconf.numCPUs = conf['%s' %vm_type]['%s' %vm_name]['cpu']
    vmconf.memoryMB = int(conf['%s' %vm_type]['%s' %vm_name]['memory'][:-1]) * 1024
    vmconf.cpuHotAddEnabled = True
    vmconf.memoryHotAddEnabled = True
    vmconf.deviceChange = devices
    globalip = vim.vm.customization.GlobalIPSettings()
    globalip.dnsServerList = conf['global']['dns']
     
    ident = vim.vm.customization.LinuxPrep()
    ident.domain = 'local'
    ident.hostName = vim.vm.customization.FixedName()
    ident.hostName.name = "%s" %vm_name
     
     
    customspec = vim.vm.customization.Specification()
    customspec.nicSettingMap = adaptermaps
    customspec.globalIPSettings = globalip
    customspec.identity = ident
     
    clonespec = vim.vm.CloneSpec()
     
    clonespec.location = relospec
    clonespec.config = vmconf
    clonespec.customization = customspec
    clonespec.powerOn = True
    clonespec.template = False
    return clonespec    
 
def initialize(template, config_file):
    si = connect.SmartConnect(host='10.51.16.61', user='xxx', pwd='xxx')
    inv=si.RetrieveContent()
    DC=inv.rootFolder.childEntity[0]
    vm=DC.vmFolder
    NETWORK=DC.network
    vm_obj=[i for i in vm.childEntity if i.name == '%s' %template][0] 
    conf1=ConfigObj('%s' %config_file,unrepr=True)
    print conf1.keys()
    i=0
     
    for vm_type in conf1.keys()[1:]:
        for vm_name in conf1['%s' %vm_type]:
            clonespec=create_spec(config_file,vm_type,vm_name, DC,NETWORK )
            task = vm_obj.Clone(folder=vm, name = '%s' %vm_name, spec=clonespec)
            result = WaitTask(task, 'Create %s from template: %s' %(vm_name,template) )
            print result
                 
 
 
         
     
if __name__ == '__main__':
    global args
    args = docopt(__doc__)
    initialize(args['<template>'], args['<config_file>'])
