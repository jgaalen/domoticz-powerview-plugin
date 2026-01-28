#!/usr/bin/env python
"""
Powerview shades
"""
"""
<plugin key="powerview" name="Hunter Douglas PowerView" version="1.2" author="Joerek van Gaalen">
    <params>
        <param field="Address" label="IP/Host Address" width="200px" required="true" default="127.0.0.1"/>
        <param field="Mode1" label="Reading Interval sec." width="40px" required="true" default="60" />
    </params>
</plugin>
"""

import Domoticz
import requests
import base64
from requests.adapters import HTTPAdapter, Retry

def getSession():
    """Create a requests session with retry logic for robustness."""
    s = requests.Session()
    retries = Retry(total=5, backoff_factor=1)
    s.mount('http://', HTTPAdapter(max_retries=retries))
    return s

def convertLevelToPosition(level):
    """Convert Domoticz level (0-100) to PowerView position (0-65535).
    Clamp to valid range to prevent overflow issues."""
    try:
        level = max(0, min(100, int(level)))
    except (ValueError, TypeError):
        level = 0
    position = round(level / 100 * 65535)
    return max(0, min(65535, position))

def updateShade(id, name, batteryStrength, position, optionsId):
    unit = GetDomoDeviceInfo(id)
    if (unit == False):
        unit = FreeUnit()
        Domoticz.Log("Found new shade: " + name + " " + str(unit) + " (" + id + ") battlevel: " + str(batteryStrength) + " position: " + position)
        Domoticz.Device(Name=name, DeviceID=id, Unit=unit, Type=244, Subtype=73, Switchtype=13, Used=1).Create()
    
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

    try:
        s = getSession()
        shades = s.get(baseurl + "/api/shades").json()

        for shade in shades['shadeData']:
            name = base64.b64decode(shade['name']).decode('utf-8')
            id = str(shade['id'])
            batteryStrength = int(shade['batteryStrength'] * 100 / 255)
            position1 = str(int(shade['positions']['position1'] * 100 / 65535))
            if 'position2' in shade['positions']:
                # For top-down/bottom-up shades:
                # position1 = bottom bar (0% = down/closed, 100% = up/open)
                # position2 = top bar - INVERTED so 100% = up/open, 0% = down/closed
                position2_raw = int(shade['positions']['position2'] * 100 / 65535)
                position2 = str(100 - position2_raw)
                updateShade(id + '_1', name + ' Bottom', batteryStrength, position1, id)
                updateShade(id + '_2', name + ' Top', batteryStrength, position2, id)
            else:
                updateShade(id, name, batteryStrength, position1, id)
    except Exception as err:
        Domoticz.Error("Error retrieving shades: " + str(err))

def updateScenes():
    baseurl = "http://" + Parameters["Address"]

    try:
        s = getSession()
        scenes = s.get(baseurl + "/api/scenes").json()
        for scenes in scenes['sceneData']:
            name = base64.b64decode(scenes['name']).decode('utf-8')
            id = scenes['id']
            if (GetDomoDeviceInfo(id) == False):
                Domoticz.Log("Found new scene: " + str(id) + " with name " + name)
                unit = FreeUnit()
                Domoticz.Device(Name=name, DeviceID=str(id), Unit=unit, TypeName="Switch", Switchtype=9, Used=1).Create()
                Devices[unit].Update(nValue=0, sValue='0')

    except Exception as err:
        Domoticz.Error("Error retrieving scenes: " + str(err))

def putShade(id, level):
    baseurl = "http://" + Parameters["Address"]
    body = {'shade': {'positions': {}}}
    
    unit = GetDomoDeviceInfo(id)
    if unit == False:
        Domoticz.Error("Device not found for id: " + str(id))
        return
        
    shadeId = Devices[unit].Options.get('id', id)

    if id.endswith('_1'):
        # Bottom bar - no inversion needed
        id2 = id[:-1] + '2'
        unit2 = GetDomoDeviceInfo(id2)
        body['shade']['positions']['position1'] = convertLevelToPosition(level)
        body['shade']['positions']['posKind1'] = 1
        if unit2:
            # Get top bar value and invert it back for API
            top_level = int(Devices[unit2].sValue) if Devices[unit2].sValue else 0
            body['shade']['positions']['position2'] = convertLevelToPosition(100 - top_level)
            body['shade']['positions']['posKind2'] = 2
    elif id.endswith('_2'):
        # Top bar - invert the level for API (100% in UI = 0 in API = fully up)
        id1 = id[:-1] + '1'
        unit1 = GetDomoDeviceInfo(id1)
        if unit1:
            body['shade']['positions']['position1'] = convertLevelToPosition(Devices[unit1].sValue)
            body['shade']['positions']['posKind1'] = 1
        body['shade']['positions']['position2'] = convertLevelToPosition(100 - level)
        body['shade']['positions']['posKind2'] = 2  
    else:
        body['shade']['positions']['position1'] = convertLevelToPosition(level)
        body['shade']['positions']['posKind1'] = 1

    try:
        s = getSession()
        s.put(baseurl + "/api/shades/" + shadeId, json=body)
    except Exception as err:
        Domoticz.Error("Error updating shade: " + str(err))

def onStart():
    Domoticz.Log("Hunter Douglas PowerView plugin start")

    try:
        updateShades()
        updateScenes()
    except Exception as err:
        Domoticz.Error("Error during plugin start: " + str(err))

    Domoticz.Heartbeat(int(Parameters["Mode1"]))

def onCommand(Unit, Command, Level, Hue):
    try:
        baseurl = "http://" + Parameters["Address"]

        if Devices[Unit].SwitchType == 9:
            try:
                s = getSession()
                s.get(baseurl + "/api/scenes?sceneId=" + Devices[Unit].DeviceID)
            except Exception as err:
                Domoticz.Error("Error requesting scene: " + str(err))
        else:
            if Command == "Off":
                Level = 0
                Devices[Unit].Update(nValue=0, sValue='0')
            elif Command == "On":
                Level = 100
                Devices[Unit].Update(nValue=1, sValue='100')
            elif Command == "Set Level":
                Devices[Unit].Update(nValue=2, sValue=str(Level))
            putShade(Devices[Unit].DeviceID, Level)
        
        updateShades()
    except Exception as err:
        Domoticz.Error("Error in onCommand: " + str(err))

def onHeartbeat():
    try:
        updateShades()
    except Exception as err:
        Domoticz.Error("Error in onHeartbeat: " + str(err))

def FreeUnit():
    FreeUnit = ""
    for x in range(1, 256):
        if x not in Devices:
            FreeUnit = x
            return FreeUnit
    if FreeUnit == "":
        FreeUnit = len(Devices) + 1
    return FreeUnit

def GetDomoDeviceInfo(DID):
    for x in Devices:
        if Devices[x].DeviceID == str(DID):
            return x
    return False
