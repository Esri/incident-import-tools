"""----------------------------------------------------------------------------
  Name:        serviceutils.py
  Purpose:     Publishes a map document as either:
                - AGOL hosted feature service
                - ArcGIS for Server map service
                Service must overwrite an existing service

  Author:      ArcGIS for Local Government

  Created:     09/01/2014
  Updated:     28/04/2014
----------------------------------------------------------------------------"""

# Import system modules
import urllib
import urllib2
import json
import sys
import os
import requests
import arcpy
from collections import OrderedDict
import ConfigParser
from xml.etree import ElementTree as ET


# Messages
m1 = "Error creating token for ArcGIS Online\n{}\n"
m2 = "Service definition (.sd) file not uploaded. Check the server errors and try again.\n{}\n"

# Errors
e1 = "Service {} not found. Check the service name in the configuration file\n"
e2 = "SD file analysis failed. Please provide the following values in the map document properties and the configuration file: {}"


class AGOLHandler(object):
    """
    Get information necessary to connect to AGOL
    """

    def __init__(self, username, password, serviceName):
        self.username = username
        self.password = password
        self.serviceName = serviceName
        self.token, self.http = self.getToken(username, password)
        #If service doesn't exist, next two items fail
        self.itemID = self.findItem("Feature Service")
        self.SDitemID = self.findItem("Service Definition")

    def getToken(self, username, password, exp=60):
        """
        Get AGOL token
        """

        referer = "http://www.arcgis.com/"
        query_dict = {'username': username,
                      'password': password,
                      'expiration': str(exp),
                      'client': 'referer',
                      'referer': referer,
                      'f': 'json'}

        query_string = urllib.urlencode(query_dict)
        url = "https://www.arcgis.com/sharing/rest/generateToken"

        token = json.loads(urllib.urlopen(url + "?f=json", query_string).read())

        if "token" not in token:
            print(token['error'])
            raise Exception(m1.format(token['error']))
        else:
            httpPrefix = "http://www.arcgis.com/sharing/rest"
            if token['ssl']:
                httpPrefix = "https://www.arcgis.com/sharing/rest"

            return token['token'], httpPrefix

    def findItem(self, findType):
        """
        Find the itemID of whats being updated
        """
        searchURL = self.http + "/search"

        query_dict = {'token': self.token,
                      'q': "title:\""+ self.serviceName + "\"AND owner:\"" + self.username + "\" AND type:\"" + findType + "\""}

        jsonResponse = sendAGOLReq(searchURL, query_dict)

        if jsonResponse['total'] == 0:
            raise Exception(e1.format(self.serviceName))

        else:
            print("found {} : {}").format(findType, jsonResponse['results'][0]["id"])
            pass

        return jsonResponse['results'][0]["id"]


def urlopen(url, data=None):
    """
    monkey-patch URLOPEN
    """
    referer = "http://www.arcgis.com/"
    req = urllib2.Request(url)
    req.add_header('Referer', referer)

    if data:
        response = urllib2.urlopen(req, data)
    else:
        response = urllib2.urlopen(req)

    return response


def createSD(SDdraft, tempDir, serviceName, pub_type, max_records = ""):
    """
    Create a draft SD and modify the properties to overwrite an existing FS
    """

    newSDdraft = os.path.join(tempDir, "updatedDraft.sddraft")
    finalSD = os.path.join(tempDir, serviceName + ".sd")

    # Read the contents of the original SDDraft into an xml parser
    doc = ET.parse(SDdraft)

    root_elem = doc.getroot()
    if root_elem.tag != "SVCManifest":
        raise ValueError("Root tag is incorrect. Is {} a .sddraft file?".format(SDDraft))

    if pub_type == "ARCGIS_ONLINE":

        # Change service type from map service to feature service
        for config in doc.findall("./Configurations/SVCConfiguration/TypeName"):
            if config.text == "MapServer":
                config.text = "FeatureServer"

        #Turn off caching
        for prop in doc.findall("./Configurations/SVCConfiguration/Definition/" +
                                    "ConfigurationProperties/PropertyArray/" +
                                    "PropertySetProperty"):

            if prop.find("Key").text == 'isCached':
                prop.find("Value").text = "false"
            if prop.find("Key").text == 'maxRecordCount':
                prop.find("Value").text = max_records

        # Turn on feature access capabilities
        for prop in doc.findall("./Configurations/SVCConfiguration/Definition/Info/PropertyArray/PropertySetProperty"):
            if prop.find("Key").text == 'WebCapabilities':
                prop.find("Value").text = "Query"

    else:
        for prop in doc.findall("./Configurations/SVCConfiguration/Definition/Extensions/SVCExtension"):
            if prop.find("TypeName").text == 'KmlServer':
                prop.find("Enabled").text = "false"

    # Add the namespaces which get stripped, back into the .SD
    root_elem.attrib["xmlns:typens"] = 'http://www.esri.com/schemas/ArcGIS/10.1'
    root_elem.attrib["xmlns:xs"] = 'http://www.w3.org/2001/XMLSchema'

    # Write the new draft to disk
    with open(newSDdraft, 'w') as f:
        doc.write(f, 'utf-8')

    # Analyze the service
    analysis = arcpy.mapping.AnalyzeForSD(newSDdraft)

    if analysis['errors'] == {}:
        # Stage the service
        arcpy.StageService_server(newSDdraft, finalSD)
        print("Created {}".format(finalSD))

    else:
        raise Exception(e2.format(analysis['errors']))

    # If the sddraft analysis contained errors, return them.
    return finalSD


def upload(agol, fileName, tags, description):
    """
    Overwrite the SD on AGOL with the new SD.
    This method uses 3rd party module: requests
    """

    updateURL = agol.http+'/content/users/{}/items/{}/update'.format(agol.username, agol.SDitemID)

    filesUp = {"file": open(fileName, 'rb')}

    url = updateURL + "?f=json&token=" + agol.token + \
        "&filename=" + fileName + \
        "&type=Service Definition" \
        "&title=" + agol.serviceName + \
        "&tags=" + tags + \
        "&description=" + description

    response = requests.post(url, files=filesUp)
    itemPartJSON = json.loads(response.text)

    if "success" in itemPartJSON:
        itemPartID = itemPartJSON['id']
        print("updated SD:   {}").format(itemPartID)
        return True
    else:
        print(m2)
        print(itemPartJSON)
        raise Exception(m2.format(itemPartJSON))


def publish(agol):
    """
    Publish the existing SD on AGOL (it will be turned into a Feature Service)
    """

    publishURL = agol.http + '/content/users/{}/publish'.format(agol.username)

    query_dict = {'itemID': agol.SDitemID,
                  'filetype': 'serviceDefinition',
                  'token': agol.token}

    jsonResponse = sendAGOLReq(publishURL, query_dict)

    print("successfully updated...{}...").format(jsonResponse['services'])

    return jsonResponse['services'][0]['serviceItemId']


def deleteExisting(agol):
    """
    Delete the item from AGOL
    """

    deleteURL = agol.http+'/content/users/{}/items/{}/delete'.format(agol.username, agol.itemID)

    query_dict = {'token': agol.token}

    jsonResponse = sendAGOLReq(deleteURL, query_dict)

    print("successfully deleted...{}...").format(jsonResponse['itemId'])


def enableSharing(agol, newItemID, everyone, orgs, groups):
    """
    Share an item with everyone, the organization and/or groups
    """
    shareURL = agol.http + '/content/users/{}/items/{}/share'.format(agol.username, newItemID)

    if groups is None:
        groups = ''

    query_dict = {'everyone': everyone,
                  'org': orgs,
                  'groups': groups,
                  'token': agol.token}

    jsonResponse = sendAGOLReq(shareURL, query_dict)

    print("successfully shared...{}...").format(jsonResponse['itemId'])


def sendAGOLReq(URL, query_dict):
    """
    Helper function which takes a URL and a dictionary and sends the request
    """
    query_string = urllib.urlencode(query_dict)
    jsonOuput = json.loads(urllib.urlopen(URL + "?f=json", query_string).read())

    wordTest = ["success", "results", "services", "notSharedWith"]
    if any(word in jsonOuput for word in wordTest):
        return jsonOuput
    else:
        print("\nfailed:")
        print(jsonOuput)
        raise Exception(jsonOutput)


def publish_service(cfg, pub_type, mxd, username, password):
    """
    Publish either a feature service to AGOL
    or a map service usign Server
    """
    service_name = cfg.get("PUBLISHING", "service_name")

    # Create a temp directory under the script
    localPath = os.path.dirname(__file__)
    tempDir = os.path.join(localPath, "tempDir")
    if not os.path.isdir(tempDir):
        os.mkdir(tempDir)

    SDdraft = os.path.join(tempDir, "tempdraft.sddraft")

    # Initialize AGOLHandler class
    if pub_type == "ARCGIS_ONLINE":
        agol = AGOLHandler(username, password, service_name)

    # Create sd file
    if pub_type == "ARCGIS_ONLINE":

        max_records = cfg.get("AGOL", "max_records")

        arcpy.mapping.CreateMapSDDraft(mxd,
                                       SDdraft,
                                       service_name,
                                       "MY_HOSTED_SERVICES")
        finalSD = createSD(SDdraft, tempDir, service_name, pub_type, max_records)

    else:
        server_path = cfg.get("SERVER", "server_path")
        folder = cfg.get("SERVER", "folder_name")

        arcpy.mapping.CreateMapSDDraft(mxd,
                                       SDdraft,
                                       service_name,
                                       "ARCGIS_SERVER",
                                       "{}.ags".format(server_path),
                                       folder_name=folder)

        # Turn map document into .SD file for uploading
        finalSD = createSD(SDdraft, tempDir, service_name, pub_type)

    if pub_type == "ARCGIS_ONLINE":
        tags = cfg.get("AGOL", "tags")
        description = cfg.get("AGOL", "description")
        in_public = cfg.get("AGOL", "in_public")
        in_org = cfg.get("AGOL", "in_organization")
        in_groups = cfg.get("AGOL", "in_groups")

        # overwrite the existing .SD on arcgis.com
        if upload(agol, finalSD, tags, description):

            # delete the existing service
            deleteExisting(agol)

            # publish the sd which was just uploaded
            newItemID = publish(agol)

            # share the item
            enableSharing(agol, newItemID, in_public, in_org, in_groups)

    else:
        server_path = cfg.get("SERVER", "server_path")
        folder_name = cfg.get("SERVER", "folder_name")

        if not folder_name == "":
            arcpy.server.UploadServiceDefinition(finalSD,
                                                 server_path,
                                                 service_name,
                                                 in_folder=folder_name)

        else:
            arcpy.server.UploadServiceDefinition(finalSD,
                                                 server_path,
                                                 service_name)

    arcpy.Delete_management(tempDir)