#!/usr/bin/env python
"""
Powerview shades
"""
"""
<plugin key="powerview" name="Hunter Douglas PowerView" version="0.1" author="Joerek van Gaalen">
    <params>
        <param field="Address" label="IP/Host Address" width="200px" required="true" default="127.0.0.1"/>
        <param field="Mode1" label="Reading Interval sec." width="40px" required="true" default="60" />
    </params>
</plugin>
"""

import Domoticz
import requests
import base64

def updateShade(id, name, batteryStrength, position, optionsId):
    unit = GetDomoDeviceInfo(id)
    if (unit == False):
        unit = FreeUnit()
        Domoticz.Log("Found new shade: " + name + " " + str(unit) + " (" + id + ") battlevel: " + str(batteryStrength) + " position: " + position)
        Domoticz.Device(Name=name, DeviceID=id, Unit=unit, TypeName="Switch", Switchtype=16, Used=1).Create()
    if position == 0:
        nv = 0
    elif position == 100:
        nv = 1
    else:
        nv = 2
    if (Devices[unit].BatteryLevel != batteryStrength or Devices[unit].nValue != nv or Devices[unit].sValue != position):
        Domoticz.Log("Update shade " + name + " to position " + position)
        Devices[unit].Update(BatteryLevel=batteryStrength, nValue=nv, sValue=position, Options={'id': optionsId})

def updateShades():
    baseurl = "http://" + Parameters["Address"]
    shades = requests.get(baseurl + "/api/shades").json()

    for shade in shades['shadeData']:
        name = base64.b64decode(shade['name']).decode('utf-8')
        id = str(shade['id'])
        batteryStrength = int (shade['batteryStrength'] * 100 / 255)
        position1 = str(int(shade['positions']['position1'] * 100 / 65535))
        if 'position2' in shade['positions']:
            position2 = str(int(shade['positions']['position2'] * 100 / 65535))
            updateShade(id + '_1', name + ' Bottom', batteryStrength, position1, id)
            updateShade(id + '_2', name + ' Top', batteryStrength, position2, id)
        else:
            updateShade(id, name, batteryStrength, position1, id)

def updateScenes():
    baseurl = "http://" + Parameters["Address"]

    try:
        scenes = requests.get(baseurl + "/api/scenes").json()
        for scenes in scenes['sceneData']:
            name = base64.b64decode(scenes['name']).decode('utf-8')
            id = scenes['id']
            if (GetDomoDeviceInfo(id) == False):
                Domoticz.Log("Found new scene: " + str(id) + " with name " + name)
                unit = FreeUnit()
                Domoticz.Device(Name=name, DeviceID=str(id), Unit=unit, TypeName="Switch", Switchtype=9, Used=1).Create()
                Devices[unit].Update(nValue=0, sValue='0')

    except Exception as err:
        Domoticz.Error("Error retrieving shades and scenes: " + str(err))

def putShade(id):
    baseurl = "http://" + Parameters["Address"]
    body = {}
    Unit = GetDomoDeviceInfo(id)
    if Unit == False:
        position1 = round(int(Devices[GetDomoDeviceInfo(id + '_1')].sValue) / 100 * 65535)
        position2 = round(int(Devices[GetDomoDeviceInfo(id + '_2')].sValue) / 100 * 65535)
        body = {
            'shade': {
                'positions': {
                    'position1': position1,
                    'posKind1': 1,
                    'position2': position2,
                    'posKind2': 2
                }
            }
        }
    else:
        position1 = round(int(Devices[Unit].sValue) / 100 * 65535)
        body = {
            'shade': {
                'positions': {
                    'position1': position1,
                    'posKind1': 1,
                }
            }
        }

    try:
        requests.put(baseurl + "/api/shades/" + id, json=body)

    except Exception as err:
        Domoticz.Error("Error updating shade: " + str(err))


def onStart():
    Domoticz.Log("Hunter Douglas PowerView plugin start")

    updateShades()
    updateScenes()

    Domoticz.Heartbeat(int(Parameters["Mode1"]))

def onCommand(Unit, Command, Level, Hue):
    baseurl = "http://" + Parameters["Address"]

    if Devices[Unit].SwitchType == 9:
        try:
            requests.get(baseurl + "/api/scenes?sceneId=" + Devices[Unit].DeviceID)
        except Exception as err:
            Domoticz.Error("Error requesting scene: " + str(err))

    else:
        if Command == "Off":
            Devices[Unit].Update(nValue=0, sValue='0')
        elif Command == "On":
            Devices[Unit].Update(nValue=1, sValue='100')
        elif Command == "Set Level":
            Devices[Unit].Update(nValue=2, sValue=str(Level))
        putShade(Devices[Unit].Options['id'])
    updateShades()

def onHeartbeat():
    updateShades()

def FreeUnit() :
    FreeUnit = ""
    for x in range(1,256):
        if x not in Devices :
            FreeUnit=x
            return FreeUnit
    if FreeUnit == "" :
        FreeUnit=len(Devices)+1
    return FreeUnit

def GetDomoDeviceInfo(DID):
    for x in Devices:
        if Devices[x].DeviceID == str(DID):
            return x
    return False