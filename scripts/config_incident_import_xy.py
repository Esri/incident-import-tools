"""----------------------------------------------------------------------------
  Name:        config_import_publish_incidents.py
  Purpose:     Builds a .cfg file containing the parameters for the
               import_publish_incidents.py script
  Author:      ArcGIS for Local Government
  Created:     28/04/2014
----------------------------------------------------------------------------"""

from os.path import dirname, join, realpath
import sys
import arcpy
from arcgis.gis import GIS
from collections import OrderedDict
import configparser

def getFullPath(targetfeatures):
    desc = arcpy.Describe(targetfeatures)
    url = desc.path

    if url.startswith('http'):
        try:
            layer_id = int(desc.name)
        except:
            name = desc.name[1:]
            layer_id = ''
            for c in name:
                if c in ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']:
                    layer_id += c
                else:
                    break
            layer_id = int(layer_id)
        return url + "/{}".format(str(layer_id))
    else:
        return url

def write_config(params, config, section):
    """
    Writes the values out to a configuration (.cfg) file
    """
    names = list(params.keys())
    vals = list(params.values())

    config.add_section(section)

    for i in range(0, len(names)):
        if vals[i] in ["#"]:
            vals[i] = '""'
        config.set(section, names[i], vals[i])

def processFieldMap(fieldmapstring):
    fmsObj = {}
    fieldmapstring = fieldmapstring.replace(")' '","|").replace(" (","*").replace(")","").replace("'","")
    tempfieldmaplist = fieldmapstring.split(";")
    for fieldpair in tempfieldmaplist:
        fieldpair = fieldpair.split("|")
        sourceField = fieldpair[0].split("*")[0]
        sourcefieldType = fieldpair[0].split("*")[1]
        targetField = fieldpair[1].split("*")[0]
        targetfieldType = fieldpair[1].split("*")[1]
        fmObj = {}
        fmObj[sourceField] = {}
        fmObj[sourceField]["type"] = sourcefieldType
        fmObj[sourceField]["target"] = targetField
        fmObj[sourceField]["targetType"] = targetfieldType
        fmsObj.update(fmObj)
    return fmsObj

def main(config_file,
         source_table,
         target_features,
         portal_url,
         username,
         password,
         reports,
         summary_field="",
         incident_id="",
         report_date_field="",
         delete_duplicates=False,
         Xfield="",
         Yfield="",
         coord_system="",
         ignore_zeros=False,
         fieldmap_option="",
         fieldmap="",
         timestamp_format="",
         *args):
    """
    Reads in a series of values from a
    GP tool UI and writes them out to a
    configuration file
    """
    arcpy.env.overwriteOutput = True

    e8 = "Error logging into portal please verify that username, password, and URL is entered correctly.\nUsername and password are case-sensitive"

    if portal_url:
        if "https://" not in portal_url[0:8] and "http://" not in portal_url[0:7]:
            portal_url = "https://" + portal_url
        try:
            arcpy.AddMessage("Verifying Login Credentials to: \n" + str(portal_url))
            GIS(portal_url, username, password)
        except:
            arcpy.AddError("{}\n".format(e8))
            sys.exit(1)
        arcpy.AddMessage("Login Credentials Verified")
    
    target_features = getFullPath(target_features)

    errorCount = 0
    if fieldmap_option == "Use Field Mapping":
        arcpy.AddMessage('Validating Field Mapping...\n')
        fms = processFieldMap(fieldmap)
        if Xfield not in fms:
            arcpy.AddError("The target field for the X Coordinate field {} has not been specified in field map".format(Xfield))
            errorCount += 1
        else:
            Xfield = fms[Xfield]["target"]
        if Yfield not in fms:
            arcpy.AddError("The target field for the Y Coordinate field {} has not been specified in field map".format(Yfield))
            errorCount += 1
        else:
            Yfield = fms[Yfield]["target"]
        if summary_field not in fms:
            arcpy.AddError("The target field for the summary field {} has not been specified in the field map".format(summary_field))
            errorCount += 1
        else:
            summary_field = fms[summary_field]["target"]
        if report_date_field not in fms:
            arcpy.AddError("The target field for the Indicent Date field {} has not been specified in field map".format(report_date_field))
            errorCount += 1
        else:
            report_date_field = fms[report_date_field]["target"]
        if incident_id not in fms:
            arcpy.AddError("The target field for the Indicent ID field {} has not been specified in field map".format(incident_id))
            errorCount += 1
        else:
            incident_id = fms[incident_id]["target"]
        if errorCount > 0:
            sys.exit()


    if not timestamp_format:
        timestamp_format = "%m/%d/%Y %H:%M"

    timestamp_format = timestamp_format.replace("%","%%")

    config = configparser.RawConfigParser()
    arcpy.AddMessage('Configuration file created')

    # Add general parameters
    section = 'GENERAL'
    p_dict = OrderedDict([('source_table', source_table),
                          ('target_features', target_features),
                          ('reports',reports),
                          ('incident_id',incident_id),
                          ('report_date_field',report_date_field),
                          ('summary_field',summary_field),
                          ('delete_duplicates',delete_duplicates),
                          ('fieldmap_option', fieldmap_option),
                          ('fieldmap', fieldmap),
                          ('timestamp_format', timestamp_format)])

    write_config(p_dict, config, section)

    #Add general publication parameters
    section = 'SERVICE'
    p_dict = OrderedDict([('portal_url',portal_url),
                          ('username',username),
                          ('password',password)])

    write_config(p_dict, config, section)

    # Add parameters for creating features from XY values
    section = 'COORDINATES'
    p_dict = OrderedDict([('Xfield',Xfield),
                          ('Yfield',Yfield),
                          ('coord_system',coord_system),
                          ('ignore_zeros',ignore_zeros)])

    write_config(p_dict, config, section)

    # Save configuration to file
    #cfgpath = dirname(realpath(__file__))
    #cfgfile = join(cfgpath, "{}.cfg".format(config_file))

    with open(config_file, "w") as cfg:
        arcpy.AddMessage('Saving configuration "{}"...'.format(config_file))
        config.write(cfg)
    
    cfg.close()

    arcpy.AddMessage('Done.')

if __name__ == '__main__':
    argv = tuple(arcpy.GetParameterAsText(i)
                 for i in range(arcpy.GetArgumentCount()))
    main(*argv)

