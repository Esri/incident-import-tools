"""----------------------------------------------------------------------------
  Name:        config_import_publish_incidents.py
  Purpose:     Builds a .cfg file containing the parameters for the
               import_publish_incidents.py script
  Author:      ArcGIS for Local Government
  Created:     28/04/2014
----------------------------------------------------------------------------"""

from os.path import dirname, join, realpath
import arcpy
from collections import OrderedDict
import ConfigParser


def write_config(params, config, section):
    """
    Writes the values out to a configuration (.cfg) file
    """
    names = list(params.keys())
    vals = list(params.values())

    config.add_section(section)

    for i in range(0, len(names)):
        if vals[i] in ["#", ""]:
            vals[i] = '""'
        config.set(section, names[i], vals[i])


def main(config_file,

         spreadsheet,
         incident_features,
         reports,
         incident_id,
         delete_duplicates=False,
         report_date_field="",
         summary_field="",
         loc_type="",
         pub_status="",

         address_field="",
         city_field="",
         state_field="",
         zip_field="",
         locator="",

         long_field="",
         lat_field="",
         coord_system="",
         ignore_zeros=False,
         transform_method="",

         mxd="",
         service_name="",
         server_path="",
         folder_name="",
         user_name="",
         password="",

         in_public=False,
         in_organization=False,
         in_groups=[],
         tags="",
         description="",
         max_records="",

         *args):
    """
    Reads in a series of values from a
    GP tool UI and writes them out to a
    configuration file
    """

    config = ConfigParser.RawConfigParser()
    arcpy.AddMessage('Configuration file created')

    if in_public == "true":
        in_public = True

    if in_organization == 'true':
        in_organization = True

    # Add general parameters
    section = 'GENERAL'
    p_dict = OrderedDict([('spreadsheet', spreadsheet),
                          ('incident_features',incident_features),
                          ('reports',reports),
                          ('incident_id',incident_id),
                          ('report_date_field',report_date_field),
                          ('summary_field',summary_field),
                          ('delete_duplicates',delete_duplicates),
                          ('loc_type',loc_type),
                          ('pub_status',pub_status),
                          ('transform_method',transform_method)])

    write_config(p_dict, config, section)

    # Add parameters for creating features from XY values
    section = 'COORDINATES'
    p_dict = OrderedDict([('long_field',long_field),
                          ('lat_field',lat_field),
                          ('coord_system',coord_system),
                          ('ignore_zeros',ignore_zeros)])

    write_config(p_dict, config, section)

    # Add parameters for creating features from addresses
    section = 'ADDRESSES'
    p_dict = OrderedDict([('address_field',address_field),
                          ('city_field',city_field),
                          ('state_field',state_field),
                          ('zip_field',zip_field),
                          ('locator',locator)])

    write_config(p_dict, config, section)

    #Add general publication parameters
    section = 'PUBLISHING'
    p_dict = OrderedDict([('mxd',mxd),
                          ('service_name',service_name),
                          ('user_name',user_name),
                          ('password',password)])

    write_config(p_dict, config, section)

    # Add Server configuration parameters
    section = 'SERVER'
    p_dict = OrderedDict([('folder_name',folder_name),
                          ('server_path',server_path)])

    write_config(p_dict, config, section)

    #Add ArcGIS Online publication parameters
    section = 'AGOL'
    p_dict = OrderedDict([('in_public',in_public),
                          ('in_organization',in_organization),
                          ('in_groups',in_groups),
                          ('tags',tags),
                          ('description',description),
                          ('max_records',max_records)])

    write_config(p_dict, config, section)

    # Save configuration to file
    cfgpath = dirname(realpath(__file__))
    cfgfile = join(cfgpath, "{}.cfg".format(config_file))

    with open(cfgfile, "w") as cfg:
        arcpy.AddMessage('Saving configuration "{}"...'.format(cfgfile))
        config.write(cfg)

    arcpy.AddMessage('Done.')

if __name__ == '__main__':
    argv = tuple(arcpy.GetParameterAsText(i)
                 for i in range(arcpy.GetArgumentCount()))
    main(*argv)