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
         spreadsheet_dir,
         completed_spreadsheets,
         reports,
         server_url,
         user_name,
         password,
         incident_service,
         incident_id,
         delete_duplicates=False,
         report_date_field="",
         summary_field="",
         loc_type="",
         address_field="",
         city_field="",
         state_field="",
         zip_field="",
         locator="",
         long_field="",
         lat_field="",
         coord_system="",
         ignore_zeros=False,
         *args):
    """
    Reads in a series of values from a
    GP tool UI and writes them out to a
    configuration file
    """

    config = ConfigParser.RawConfigParser()
    arcpy.AddMessage('Configuration file created')

    # Add general parameters
    section = 'GENERAL'
    p_dict = OrderedDict([('spreadsheet_directory', spreadsheet_dir),
                          ('completed_spreadsheets', completed_spreadsheets),
                          ('incident_service',incident_service),
                          ('reports',reports),
                          ('incident_id',incident_id),
                          ('report_date_field',report_date_field),
                          ('summary_field',summary_field),
                          ('delete_duplicates',delete_duplicates),
                          ('loc_type',loc_type)])

    write_config(p_dict, config, section)

    #Add general publication parameters
    section = 'SERVICE'
    p_dict = OrderedDict([('server_url', server_url),
                          ('user_name',user_name),
                          ('password',password)])

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