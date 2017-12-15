"""----------------------------------------------------------------------------
  Name:        import_publish_incidents.py
  Purpose:     Load data from a spreadsheet into a feature class.
                 Data may be located by addresses or XY values
                 Data may be published using Server or ArcGIS Online
                 Duplicates may be ignored or updated
                Script requires a configuration file of values as input

  Author:      ArcGIS for Local Government

  Created:     09/01/2014
  Updated:     1/9/2015
----------------------------------------------------------------------------"""

from os.path import dirname, join, exists, splitext, isfile, basename
from datetime import datetime as dt
from time import mktime, time as t
from calendar import timegm
from arcgis.gis import GIS
from arcgis.features import Feature, FeatureLayer
import json
import arcpy
import csv
import getpass
import configparser
from os import rename, walk
#from arcrest.security import AGOLTokenSecurityHandler
#from arcresthelper import securityhandlerhelper
#from arcresthelper import common
#from arcrest.agol import FeatureLayer

# Data timestamp format for deleting duplicates
# Day, month, hours, minutes, and seconds must always be zero-padded values
#   %m      zero-padded month (00-12)
#   %d      zero-padded day (00-31)
#   %Y      year with century (e.g 2014)
#   %y      two digit year (e.g 14)
#   %H      zero-padded hours (00-24)
#   %h      zero-padded hours (01-12)
#   %M      zero-padded minutes (00-59)
#   %S      zero-padded seconds (00-59)
timestamp = "%m/%d/%Y %H:%M"

# Accepted file extensions
file_types = ['.csv', '.txt','.xls','.xlsx'] 

# Locator input fields
#       World Geocode Service values are available here:
#       http://resources.arcgis.com/en/help/arcgis-rest-api/#/Multiple_input_field_geocoding/02r30000001p000000/
all_locator_fields = ["Address", "Address2", "Address3", "Neighborhood", "City", "Subregion", "Region", "Postal", "PostalExt", "CountryCode"]

loc_address_field = "Address" # Field in all_locator_fields for street address (required)
loc_city_field    = "City"    # Field in all_locator_fields for City (optional)
loc_state_field   = "Region"  # Field in all_locator_fields for province or state (optional)
loc_zip_field     = "Postal"  # Field in all_locator_fields for Zip or postal code (optional)

# Geocoding results fields
status = "Status"
addr_type = "Addr_type"

# Accepted levels of geolocation
addrOK = ["AddrPoint", "StreetAddr", "BldgName", "Place", "POI", "Intersection", "PointAddress", "StreetAddress", "SiteAddress"]
match_value = ["M", "T"]

# Feature access options for AGOL hosted service
feature_access = "Query, Create, Update, Delete, Uploads, Editing"

# Log file header date and time formats
date_format = "%Y-%m-%d"
time_format = "%H:%M:%S"

# Reports and log files
prefix = "%Y-%m-%d_%H-%M-%S"
unmatch_name = "UnMatched"
noappend_name = "NotAppended"
errorfield = "ERRORFIELD"
lat_field = "Y"
long_field = "X"

# Temp data
temp_gdb_name = "temp_inc_data"

# Log file messages
l1 = "Run date:       {}\n"
l2 = "User name:      {}\n"
l3 = "Incidents:      {}\n"
l4 = "Feature class:  {}\n"
l5 = "Locator:        {}\n\n"
l10 = "    Incidents summarized by {}\n"
l11 = "       -- {}  # Incidents: {}\n"

# Error messages
gp_error = "GP ERROR"
py_error = "ERROR"

e1 = "{}:{} cannot be found.{}"
e2 = "Field u'{}' does not exist in {}.\nValid fields are {}.{}"
##e3 = "Provide a valid ArcMap document to publish a service."
##e4 = "SD draft analysis errors:\n{}"
e6 = "Feature service {} must store features with point geomentry."
##e8 = "Provide a user name and password with Publisher or Administrative privileges."
e13 = "Provide a locator to geocode addresses. A locator service, local locator, or the World Geocode Service are all acceptable."
e14 = "The locator values provided at the top of the import_publish_incidents.py script for 'loc_address_field', 'loc_city_field', 'loc_zip_field', and 'loc_state_field' must also be included in the list 'all_locator_fields'."
e15 = "Field {} in spreadsheet {} contains a non-date value, or a value in a format other than {}."
e16 = "Report date field required to identify duplicate records."

# Warning messages
##w1 = "*** {} records could not be appended to {}.\nThese records have been copied to {}.\n\n"
w3 = "The following records contain null values in required fields and were not processed:\n{}"
##w4 = "{} (problem field: {})"
w5 = "\nTip: Many values are set in the script configuration file.\n"
w6 = "*** {} records were not successfully geocoded.\nThese records have been copied to {}.\n\n"
w7 = "*** {} records were not geocoded to an acceptable level of accuracy: {}\nThese records have been copied to {}.\n\n"

# Informative messages
m0 = "{} Logged into portal as {}...\n"
m1 = "{}  Creating features...\n"
m2 = "{} Mapping fields to field mapping object...\n"
m3 = "{}  Geocoding incidents...\n"
m4 = "{}  Appending incidents to {}...\n"
##m5 = "{}  Publishing incidents...\n"
m6 = "{} Copying source table to new field mapped table...\n"
m8 = "{}  Completed {}\n"
m13 = "{}  Updating older reports and filtering out duplicate records...\n"
m14 = "  -- {} features updated in {}.\n\n"
m15 = "  -- {} records will not be processed further. They may contain null values in required fields, they may be duplicates of other records in the spreadsheet, or they may be older than records that already exist in {}.\n\n"
m16 = "  -- {} records successfully geocoded.\n\n"
m17 = "  -- {} records found in spreadsheet {}.\n\n"
##m18 = "  -- {} records successfully appended to {}.\n\n"
m19 = "{} records are not included in this summary because they did not contain a valid value in the summary field.\n"

# Environment settings
# Set overwrite output option to True
arcpy.env.overwriteOutput = True

def messages(msg, log, msg_type = 0):
    """Prints messages to the command line, log file, and GP tool dialog"""
    log.write(msg)
    print(msg)
    if msg_type == 0:
        arcpy.AddMessage(msg)
    elif msg_type == 1:
        arcpy.AddWarning(msg)
    else:
        arcpy.AddError(msg)

# End messages function

def field_vals(table,field):
    """Builds a list of all the values in a field"""

    with arcpy.da.SearchCursor(table, field) as rows:
        sumList = [row[0] for row in rows]

    return sumList

# End field_vals function


def sort_records(table, writer, index, vals, inlist=True, remove=False):
    """Sorts records into additional files based on values in a field
        Returns the count of features moved."""
    with arcpy.da.UpdateCursor(table, '*') as rows:
        count = 0
        for row in rows:
            if inlist and row[index] in vals:
                count += 1
                writer.writerow(row)
                if remove:
                    rows.deleteRow()
            elif not inlist and row[index] not in vals:
                count += 1
                writer.writerow(row)
                if remove:
                    rows.deleteRow()

    return count

#End sort_records function


def field_test(in_fc, in_fields, out_fields, required=False):
    """Test existence of field names in datasets"""

    for in_field in in_fields:
        if not in_field in out_fields:
            if required:
                raise Exception(e2.format(in_field, in_fc, out_fields, ""))
            elif not in_field == "":
                raise Exception(e2.format(in_field, in_fc, out_fields, ""))
            else:
                pass

# End field_test function

def compare_locations(fields, servicerow, tablerow, loc_fields):
    """Compares the values of each of a list of fields with
        the corresponding values in a dictionary.
        Compares values accross field types.
        Returns True if the values are different"""

    status = False

    for loc_field in loc_fields:

        if loc_field in fields:
            loc_index = fields.index(loc_field)
            try:
                if tablerow[loc_index].is_integer():
                        tablerow[loc_index] = int(tablerow[loc_index])
            except AttributeError:
                pass

            table_str = str(tablerow[loc_index]).upper().replace(',','')

            serv_str = str(servicerow.get_value(loc_field)).upper().replace(',','')

            if not table_str == serv_str:
                status = True
                break

    return status

# End compare_locs function

def cast_id(idVal, field_type):
    """If possible, re-cast a value to a specific field type
        Otherwise, cast it as a string."""
    if "String" in field_type:
        idVal = str(idVal)
    else:
        try:
            idVal = int(idVal)
        except ValueError:
            idVal = str(idVal)

    return idVal

#End cast_id function

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

def remove_dups(tempgdb, new_features, cur_features: FeatureLayer, fields, id_field, dt_field, loc_fields):
    """Compares records with matching ids and determines which is more recent.
        If the new record is older than the existing record, no updates
        If the new record has the same or a more recent date, the locations
            are compared:

            If the location has changed the existing record is deleted
            If the locations are the same the existing record attributes
                are updated"""
    update_count = 0
    del_count = 0

    # Create temporary table of the new data
##    tempTable = join(tempgdb, "tempTableLE")
    tempTable = arcpy.CopyRows_management(new_features, join('in_memory','tempTableLE'))

    # Field indices for identifying most recent record
    id_index = fields.index(id_field)
    dt_index = fields.index(dt_field)
    # service field types
    service_field_types = {}
    for field in cur_features.properties.fields:
        service_field_types[field['name']] = field['type']

    # Record and delete rows with null values that cannot be processed
    where_null = """{0} IS NULL OR {1} IS NULL""".format(id_field, dt_field)
    null_records = ""
    with arcpy.da.UpdateCursor(tempTable, [id_field, dt_field], where_null) as null_rows:
        if null_rows:
            for null_row in null_rows:
                null_records = "{}{}\n".format(null_records, null_row)
                null_rows.deleteRow()
                del_count += 1

    # Delete all but the most recent report if the table contains duplicates
    all_ids = [str(csvrow[id_index]) for csvrow in arcpy.da.SearchCursor(tempTable, fields)]
    dup_ids = [id for id in list(set(all_ids)) if all_ids.count(id) > 1]
    
    if dup_ids:
        for dup_id in dup_ids:
            where_dup = """{0} = {1}""".format(id_field, dup_id)

            with arcpy.da.UpdateCursor(tempTable, [dt_field,loc_fields], where_dup) as dup_rows:
                recent_date = ""
                while len(dup_rows) > 1:
                    for dup_row in dup_rows:
                        if dup_row[0] > recent_date:
                            recent_date = dup_row[0]
                        else:
                            dup_rows.delete(dup_row)
                            del_count += 1


    # Look for reports that already exist in the service
    service_ids = cur_features.query(where="1=1",out_fields=id_field, returnGeometry=False)

    
    # Use id values common to service and new data to build a where clause
    common_ids = list(set(all_ids).intersection([str(service_id.get_value(id_field)) for service_id in service_ids]))
    if common_ids:
        if not len(list(set(all_ids))) == 1:
            where_clause = """{0} IN {1}""".format(id_field, tuple(common_ids))
        else:
            where_clause = """{0} = {1}""".format(id_field, tuple(common_ids[0]))

        curFeaturesFS = cur_features.query(where=where_clause, out_fields=",".join(fields), returnGeometry=False)

        editFeatures = []

        for servicerow in curFeaturesFS.features:

            # Get the id value for the row
            idVal = cast_id(servicerow.get_value(id_field), service_field_types[id_field])

            # Grab the attributes values associated with that id
            if isinstance(idVal, int):
                where_service_dup = """{} = {}""".format(id_field, idVal)
            else:
                where_service_dup = """{} = '{}'""".format(id_field, idVal)
            with arcpy.da.UpdateCursor(tempTable, fields, where_service_dup) as csvdups:
                for csvdup in csvdups:
                # Test if new record is more recent (date_status = True)
                    try:
                        #Bring in time stamp from service in system time
                        date2 = dt.fromtimestamp(int(str(servicerow.get_value(dt_field))[:10]))

                        #Check to see if spreadsheet date is already a datetime, if not convert to datetime
                        if isinstance(csvdup[dt_index], dt):
                            date1 = csvdup[dt_index]
                        else:
                            date1 = dt.strptime(csvdup[dt_index],timestamp)

                        date1.replace(microsecond = 0)
                        date2.replace(microsecond = 0)
                    except TypeError:
                        raise Exception(e15.format(dt_field, new_features, timestamp))

                    # If new record older, delete the record from the table
                    if date1 < date2:
                        csvdups.deleteRow()
                        del_count += 1

                    # Otherwise, compare location values
                    else:
                        loc_status = compare_locations(fields, servicerow, csvdup, loc_fields)
                        # If the location has changed
                        if loc_status:

                            # Delete the row from the service
                            del_where = """{} = {}""".format(id_field, idVal)
                            cur_features.delete_features(where=del_where)

                        else:
                            # Same location, try to update the service attributes
                            try:
                                field_info = []
                                for i in range(0, len(fields)):
                                    fvals = {}
                                    fvals['FieldName'] = fields[i]

                                    # Make sure doubles get processed as doubles
                                    if 'Double' in service_field_types[fields[i]]:
                                        fvals['ValueToSet'] = float(str(csvdup[i]).replace(',',''))
                                    elif 'Date' in service_field_types[fields[i]]:
                                        try:
                                            #DateString -> Datetime -> UNIX timestamp integer
                                            fvals['ValueToSet'] = int(str(dt.strptime(csvdup[i],timestamp).timestamp()*1000)[:13])
                                        except TypeError:
                                            #Create a unix timestamp integer in UTC time to send to service
                                            fvals['ValueToSet'] = int(str(csvdup[i].timestamp()*1000)[:13])
                                    else:
                                        fvals['ValueToSet'] = csvdup[i]

                                    field_info.append(fvals)
                                
                                #Check to see if any attributes are different between target service and source table
                                updateNeeded = False
                                for fld in field_info:
                                    if servicerow.get_value(fld["FieldName"]) != fld['ValueToSet']:
                                        updateNeeded = True
                                
                                #At least one attribute change detected so send new attributes to service
                                if updateNeeded:
                                    for fld in field_info:
                                        servicerow.set_value(fld["FieldName"],fld['ValueToSet'])
                                    editFeatures.append(servicerow)
                                    update_count += 1

                                # Remove the record from the table
                                csvdups.deleteRow()

                            # If there is a field type mismatch between the service
                            #   and the table, delete the row in the
                            #   service. The table record will be
                            #   re-geocoded and placed in the un-appended report for
                            #   further attention.
                            except RuntimeError:
                                del_where = """{} = {}""".format(id_field, idVal)
                                cur_features.delete_features(where=del_where)

        cur_features.edit_features(updates=editFeatures)

##                    break

    # Return the records to geocode
    return tempTable, null_records, update_count, del_count

# End remove_dups function

def main(config_file, *args):
    """
    Import the incidents to a feature class,
    filtering out duplicates if necessary,
    assign geometry using addresses or XY values,
    and publish the results usign AGOL or ArcGIS for Server.
    Output is an updated feature class, processign reports,
    and optionally a service
    """

    # Current date and time for file names
    fileNow = dt.strftime(dt.now(), prefix)

    if isfile(config_file):
        cfg = configparser.ConfigParser()
        cfg.read(config_file)
    else:
        raise Exception(e1.format("Configuration file", config_file, ""))

    # Get general configuration values
    incidents = cfg.get('GENERAL', 'source_table')
    inc_features = cfg.get('GENERAL', 'target_features')
    id_field = cfg.get('GENERAL', 'incident_id')
    report_date_field = cfg.get('GENERAL', 'report_date_field')
    reports = cfg.get('GENERAL', 'reports')
    summary_field = cfg.get('GENERAL', 'summary_field')
    delete_duplicates = cfg.get('GENERAL', 'delete_duplicates')
    fieldmap_option = cfg.get('GENERAL', 'fieldmap_option')
    fieldmap = cfg.get('GENERAL', 'fieldmap')

    loc_type = "COORDINATES" if cfg.has_section('COORDINATES') else "ADDRESSES"

    if delete_duplicates in ('true', 'True', True):
        delete_duplicates = True
        if report_date_field == "":
            raise Exception(e16)

    if delete_duplicates in ('false', 'False'):
        delete_duplicates = False


    incident_filename = basename(incidents)
    log_name = splitext(incident_filename)[0]

    # Log file
    if exists(reports):
        rptLog = join(reports, "{0}_{1}.log".format(fileNow, log_name))

    else:
        raise Exception(e1.format("Report location", reports, w5))

    # Scratch workspace
    tempgdb = arcpy.env.scratchGDB

    with open(rptLog, "w") as log:
        try:
            # Log file header
            log.write(l1.format(fileNow))
            log.write(l2.format(getpass.getuser()))
            log.write(l3.format(incidents))
            log.write(l4.format(inc_features))
            if loc_type == "ADDRESSES":
                log.write(l5.format(cfg.get('ADDRESSES', 'locator')))

            # connect to incidents service
            proxy_port = None
            proxy_url = None

            portalURL = cfg.get('SERVICE', 'portal_url')
            username = cfg.get('SERVICE', 'username')
            password = cfg.get('SERVICE', 'password')

            timeNow = dt.strftime(dt.now(), time_format)
            portal = GIS(portalURL, username, password)
            messages(m0.format(timeNow, str(portal.properties.user.username)), log)

            fl = FeatureLayer(url=inc_features,gis=portal)
                

            if not fl.properties.geometryType == 'esriGeometryPoint':
                raise Exception(e6.format(inc_features))

            timeNow = dt.strftime(dt.now(), time_format)
            
            # Create Field Mapping Object and Map incidents to new table with new schema    
            messages(m2.format(timeNow), log)
            if fieldmap_option == "Use Field Mapping":
                fieldmap = processFieldMap(fieldmap)
                afm = arcpy.FieldMappings()
                for key, value in fieldmap.items():
                    tempFieldMap = arcpy.FieldMap()
                    tempFieldMap.mergeRule = "First"
                    tempFieldMap.outputField = arcpy.ListFields(inc_features, value['target'])[0]
                    tempFieldMap.addInputField(incidents, key)
                    afm.addFieldMap(tempFieldMap)  
                timeNow = dt.strftime(dt.now(), time_format)
                messages(m6.format(timeNow), log)
                incidents = arcpy.TableToTable_conversion(incidents, tempgdb, "schemaTable",field_mapping=afm)

            # Identify field names in both fc and csv
            csvfieldnames = [f.name for f in arcpy.ListFields(incidents)]
            incfieldnames = [f['name'] for f in fl.properties.fields]

            matchfieldnames = [fieldname for fieldname in csvfieldnames if fieldname in incfieldnames]
            
            #Dont compare objectid values because they will likely be different and will cause updates
            # to be sent to service when its not necessary
            if 'OBJECTID' in matchfieldnames:
                matchfieldnames.remove('OBJECTID') 

            # If data is to be geocoded
            if loc_type == "ADDRESSES":

                # Get geocoding parameters
                address_field = cfg.get('ADDRESSES', 'address_field')
                city_field = cfg.get('ADDRESSES', 'city_field')
                state_field = cfg.get('ADDRESSES', 'state_field')
                zip_field = cfg.get('ADDRESSES', 'zip_field')
                locator = cfg.get('ADDRESSES', 'locator')

                # Geocoding field names
                reqFields = [address_field, id_field]#, report_date_field]
                opFields = [city_field, state_field, zip_field, summary_field, report_date_field]

                if locator == "":
                    raise Exception(e13)

                # Test geolocator fields
                loc_address_fields = [loc_address_field, loc_city_field, loc_zip_field, loc_state_field]
                for a in loc_address_fields:
                    if not a == "":
                        if not a in all_locator_fields:
                            raise Exception(e14)

            # If data has coordinate values
            else:

                # Get coordinate parameters
                lg_field = cfg.get('COORDINATES', 'Xfield')
                lt_field = cfg.get('COORDINATES', 'Yfield')
                coord_system = cfg.get('COORDINATES', 'coord_system')
                remove_zeros = cfg.get('COORDINATES', 'ignore_zeros')
                if remove_zeros in ('true', 'True'):
                    remove_zeros = True
                if remove_zeros in ('false', 'False'):
                    remove_zeros = False

                # Coordinate field names
                reqFields = [id_field, lg_field, lt_field]#, report_date_field]
                opFields = [summary_field, report_date_field]

            # Validate required field names
            field_test(incidents, reqFields, csvfieldnames, True)
            field_test(inc_features, reqFields, incfieldnames, True)

            # Validate optional field names
            field_test(incidents, opFields, csvfieldnames)
            field_test(inc_features, opFields, incfieldnames)

            # Get address fields for geocoding
            if loc_type == "ADDRESSES":

                addresses = ""
                loc_fields = []
                adr_string = "{0} {1} VISIBLE NONE;"

                for loc_field in all_locator_fields:
                    if loc_field == loc_address_field:
                        addresses += adr_string.format(loc_field, address_field)
                        loc_fields.append(address_field)

                    elif loc_field == loc_city_field and city_field != "":
                        addresses += adr_string.format(loc_field, city_field)
                        loc_fields.append(city_field)

                    elif loc_field == loc_state_field and state_field != "":
                        addresses += adr_string.format(loc_field, state_field)
                        loc_fields.append(state_field)

                    elif loc_field == loc_zip_field and zip_field != "":
                        addresses += adr_string.format(loc_field, zip_field)
                        loc_fields.append(zip_field)

                    else:
                        addresses += adr_string.format(loc_field, "<None>")

            # Get coordinate fields
            else:
                loc_fields = [lg_field, lt_field]

            total_records = len(field_vals(incidents,id_field))

            messages(m17.format(total_records, incidents), log)

            if not summary_field == "":
                SumVals = field_vals(incidents, summary_field)
                listSumVals = [val for val in SumVals if val != None]

                if not len(SumVals) == len(listSumVals):
                    print(m19.format(len(SumVals)-len(listSumVals)))
                    log.write(m19.format(len(SumVals)-len(listSumVals)))
                listSumVals.sort()

                log.write(l10.format(summary_field))
                dateCount = 1
                i = 0
                n = len(listSumVals)

                while i < n:

                    try:
                        if listSumVals[i] == listSumVals[i + 1]:
                            dateCount += 1
                        else:
                            log.write(l11.format(listSumVals[i], dateCount))
                            dateCount = 1
                    except:
                        log.write(l11.format(listSumVals[i], dateCount))
                    i += 1

                log.write("\n")

            # Remove duplicate incidents
            if delete_duplicates:
                timeNow = dt.strftime(dt.now(), time_format)
                messages(m13.format(timeNow), log)

                incidents, req_nulls, countUpdate, countDelete = remove_dups(tempgdb,
                                                                                incidents,
                                                                                fl,
                                                                                matchfieldnames,
                                                                                id_field,
                                                                                report_date_field,
                                                                                loc_fields)

                if not req_nulls == "":
                    req_nulls = "{}\n".format(req_nulls)
                    messages(w3.format(req_nulls), log, 1)

                if not countUpdate == 0:
                    messages(m14.format(countUpdate,inc_features), log)

                if countDelete > 0:
                    messages(m15.format(countDelete,inc_features), log)

            # Create features
            tempFC = join(tempgdb, "tempDataLE")

            # Create point features from spreadsheet

            timeNow = dt.strftime(dt.now(), time_format)
            messages(m1.format(timeNow), log)

            records_to_add = 0
            for r in arcpy.da.SearchCursor(incidents, id_field):
                records_to_add += 1

            if records_to_add > 0:
                if loc_type == "ADDRESSES":

                    timeNow = dt.strftime(dt.now(), time_format)
                    messages(m3.format(timeNow), log)

                    # Geocode the incidents
                    arcpy.GeocodeAddresses_geocoding(incidents,
                                                        locator,
                                                        addresses,
                                                        tempFC,
                                                        "STATIC")
                    

                    # Initiate geocoding report counts
                    countMatch = 0
                    countTrueMatch = 0
                    countUnmatch = 0

                    # Create geocoding reports
                    rptUnmatch = join(reports, "{0}_{1}.csv".format(
                                                            fileNow, unmatch_name))

                    fieldnames = [f.name for f in arcpy.ListFields(tempFC)]

                    # Sort incidents based on match status
                    statusIndex = fieldnames.index(status)
                    locIndex = fieldnames.index(addr_type)

                    # Write incidents that were not well geocoded to file and
                    #       delete from temp directory
                    with open (rptUnmatch, "w") as umatchFile:
                        unmatchwriter = csv.writer(umatchFile)
                        unmatchwriter.writerow(fieldnames)

                        # Delete incidents that were not Matched
                        countUnmatch = sort_records(tempFC, unmatchwriter,
                                                    statusIndex, match_value,
                                                    False, True)
                        
                        if not countUnmatch == 0:
                            messages(w6.format(countUnmatch, rptUnmatch), log, 1)

                        # Incidents that were not matched to an acceptable accuracy
                        countMatch = sort_records(tempFC, unmatchwriter,
                                                    locIndex, addrOK, False, True)

                        if not countMatch == 0:
                            messages(w7.format(countMatch, addrOK, rptUnmatch), log, 1)

                        countTrueMatch = len(field_vals(tempFC, "OBJECTID"))

                        messages(m16.format(countTrueMatch, inc_features), log)

                else:
                    # Create temporary output storage

                    tempFL = arcpy.MakeXYEventLayer_management(incidents,
                                                                lg_field,
                                                                lt_field,
                                                                "tempLayerLE",
                                                                coord_system)

                    # Convert the feature layer to a feature class to prevent
                    #   field name changes

                    arcpy.CopyFeatures_management(tempFL, tempFC)
                    arcpy.Delete_management(tempFL)

                timeNow = dt.strftime(dt.now(), time_format)
                messages(m4.format(timeNow, inc_features), log)

                # Fields that will be copied from geocode results to final fc
                copyfieldnames = []
                copyfieldnames.extend(matchfieldnames)
                copyfieldnames.append("SHAPE@XY")

                # Fields for error reporting
                errorfieldnames = []
                errorfieldnames.extend(matchfieldnames)
                errorfieldnames.insert(0, errorfield)
                errorfieldnames += [long_field, lat_field]

                #Remove USER_ from Field Names if Geocoded
                if loc_type == "ADDRESSES":
                    for name in fieldnames:
                        if name.replace("USER_", "") in incfieldnames:
                            arcpy.AlterField_management(tempFC, name, name.replace("USER_", ""))
                        

                # Reproject the features
                sr_output = fl.properties.extent['spatialReference']['wkid']
                proj_out = "{}_proj".format(tempFC)
                arcpy.Project_management(tempFC, proj_out, sr_output)

                dateFields = [field['name'] for field in fl.properties.fields if 'Date' in field['type'] and field['name'] in matchfieldnames]

                #Convert to Feature Set
                fs = arcpy.FeatureSet()
                fs.load(proj_out)
                
                #Create ArcGIS Python API Features List
                fset = []
                for feature in json.loads(fs.JSON)["features"]:
                    tempFeature = Feature(feature['geometry'], feature['attributes'])
                    fset.append(tempFeature)


                #Convert all date values to UTC for records to add
                for feature in fset:
                    for dateField in dateFields:
                        if isinstance(feature.get_value(dateField), int):
                            dateValue = dt.utcfromtimestamp(int(str(feature.get_value(dateField))[:10]))
                        else:
                            dateValue = dt.strptime(feature.get_value(dateField), timestamp)
                        dateValue = int(str(dateValue.timestamp()*1000)[:13])
                        feature.set_value(dateField, dateValue)

                #Append features to service
                fl.edit_features(fset)


        except arcpy.ExecuteError:
            print("{}\n{}\n".format(gp_error, arcpy.GetMessages(2)))
            timeNow = dt.strftime(dt.now(), "{} {}".format(
                                                date_format, time_format))
            arcpy.AddError("{} {}:\n".format(timeNow, gp_error))
            arcpy.AddError("{}\n".format(arcpy.GetMessages(2)))

            log.write("{} ({}):\n".format(gp_error, timeNow))
            log.write("{}\n".format(arcpy.GetMessages(2)))

            for msg in range(0, arcpy.GetMessageCount()):
                if arcpy.GetSeverity(msg) == 2:
                    code = arcpy.GetReturnCode(msg)
                    print("Code: {}".format(code))
                    print("Message: {}".format(arcpy.GetMessage(msg)))

        except Exception as ex:
            print("{}: {}\n".format(py_error, ex))
            timeNow = dt.strftime(dt.now(), "{}".format(time_format))

            arcpy.AddError("{} {}:\n".format(timeNow, py_error))
            arcpy.AddError("{}\n".format(ex))

            log.write("{} {}:\n".format(timeNow, py_error))
            log.write("{}\n".format(ex))

        finally:
             #Clean up
            try:
                arcpy.Delete_management(tempgdb)
            except arcpy.ExecuteError:
                pass

            timeNow = dt.strftime(dt.now(), time_format)
            messages(m8.format(timeNow, incidents), log)

if __name__ == '__main__':
    argv = tuple(arcpy.GetParameterAsText(i)
                 for i in range(arcpy.GetArgumentCount()))
    main(*argv)