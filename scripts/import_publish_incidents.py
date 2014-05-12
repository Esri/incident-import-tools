"""----------------------------------------------------------------------------
  Name:        import_publish_incidents.py
  Purpose:     Load data from a spreadsheet into a feature class.
                 Data may be located by addresses or XY values
                 Data may be published using Server or ArcGIS Online
                 Duplicates may be ignored or updated
                Script requires a configuration file of values as input

  Author:      ArcGIS for Local Government

  Created:     09/01/2014
  Updated:     28/04/2014
----------------------------------------------------------------------------"""

from os.path import dirname, join, exists, splitext, isfile
from datetime import datetime as dt
from time import mktime
from calendar import timegm
import arcpy
import csv
import xml.dom.minidom as DOM
import getpass
import serviceutils
import ConfigParser
from tempfile import mkdtemp
from shutil import rmtree

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
timestamp = "%m/%d/%Y %H:%M:%S"

# Locator input fields
#       World Geocode Service values are available here:
#       http://resources.arcgis.com/en/help/arcgis-rest-api/#/Multiple_input_field_geocoding/02r30000001p000000/
all_locator_fields = ["Address", "Neighborhood", "City", "Subregion", "Region", "Postal", "PostalExt", "CountryCode"]

loc_address_field = "Address" # Field in all_locator_fields for street address (required)
loc_city_field    = "City"    # Field in all_locator_fields for City (optional)
loc_state_field   = "Region"  # Field in all_locator_fields for province or state (optional)
loc_zip_field     = "Postal"  # Field in all_locator_fields for Zip or postal code (optional)

# Geocoding results fields
status = "Status"
addr_type = "Addr_type"

# Accepted levels of geolocation
addrOK = ["AddrPoint", "StreetAddr", "BldgName", "Place", "POI", "Intersection", "PointAddress", "StreetAddress", "SiteAddress"]
match_value = ["M"]

# Feature access options for AGOL hosted service
feature_access = "Query, Create, Update, Delete, Uploads, Editing"

# Log file header date and time formats
date_format = "%Y-%m-%d"
time_format = "%H:%M:%S"

# Reports and log files
prefix = "%Y-%m-%d_%H-%M-%S"
log_name = "Log"
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
e3 = "Provide a valid ArcMap document to publish a service."
e4 = "SD draft analysis errors:\n{}"
e6 = "Feature class {} must store features with point geomentry."
e8 = "Provide a user name and password with Publisher or Administrative privileges."
e13 = "Provide a locator to geocode addresses. A locator service, local locator, or the World Geocode Service are all acceptable."
e14 = "The locator values provided at the top of the import_publish_incidents.py script for 'loc_address_field', 'loc_city_field', 'loc_zip_field', and 'loc_state_field' must also be included in the list 'all_locator_fields'."
e15 = "Field {} in spreadsheet {} contains a non-date value, or a value in a format other than {}."
e16 = "Report date field required to identify duplicate records."

# Warning messages
w1 = "*** {} records could not be appended to {}.\nThese records have been copied to {}.\n\n"
w3 = "The following records contain null values in required fields and were not processed:\n{}"
w4 = "{} (problem field: {})"
w5 = "\nTip: Many values are set in the script configuration file.\n"
w6 = "*** {} records were not successfully geocoded.\nThese records have been copied to {}.\n\n"
w7 = "*** {} records were not geocoded to an acceptable level of accuracy: {}\nThese records have been copied to {}.\n\n"

# Informative messages
m1 = "{}  Creating features...\n"
m3 = "{}  Geocoding incidents...\n"
m4 = "{}  Appending incidents to {}...\n"
m5 = "{}  Publishing incidents...\n"
m8 = "{}  Completed\n"
m13 = "{}  Updating older reports and filtering out duplicate records...\n"
m14 = "  -- {} features updated in {}.\n\n"
m15 = "  -- {} records will not be processed further. They may contain null values in required fields, they may be duplicates of other records in the spreadsheet, or they may be older than records that already exist in {}.\n\n"
m16 = "  -- {} records successfully geocoded.\n\n"
m17 = "  -- {} records found in spreadsheet {}.\n\n"
m18 = "  -- {} records successfully appended to {}.\n\n"
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


def compare_dates(fields, dt_field, row, id_vals):
    """Compares date values in a row and a dictionary.
        Returns True if the row date is the more recent value."""

    status = False

    dt_index = fields.index(dt_field)

    # Create datetime items from string dates if necessary
    try:
        row_date = dt.strptime(row[dt_index],timestamp)
    except TypeError:
        # Date values OK
        if isinstance(row[dt_index], dt):
            row_date = row[dt_index]
        # Fail if non-date value
        else:
            raise Exception(e15.format(dt_field, "", timestamp))

    try:
        dict_date = dt.strptime(id_vals[dt_field],timestamp)
    except TypeError:
        if isinstance(id_vals[dt_field], dt):
            dict_date = id_vals[dt_field]
        else:
            raise Exception(e15.format(dt_field, "", timestamp))

    row_date.replace(microsecond = 0)
    dict_date.replace(microsecond = 0)
    if dict_date < row_date:
        status = True
    else:
        status = False

    return status

# End compare_dates function


def compare_locations(fields, fcrow, id_vals, loc_fields):
    """Compares the values of each of a list of fields with
        the corresponding values in a dictionary.
        Compares values accross field types.
        Returns True if the values are different"""

    status = False

    for loc_field in loc_fields:

        if loc_field in fields:
            loc_index = fields.index(loc_field)

            try:
                if id_vals[loc_field].is_integer():
                        id_vals[loc_field] = int(id_vals[loc_field])
            except AttributeError:
                pass

            if not str(id_vals[loc_field]).upper() == str(fcrow[loc_index]).upper():
                status = True
                break

    return status

# End compare_locs function


def update_dictionary(fields, values, dictionary):
    """Update values in a dictionary using a table row"""
    for i in range(0, len(fields)):
        # Update the dictionary with the more recent values
        dictionary[fields[i]] = values[i]
        i += 1

    return dictionary

# End update_dictionary function


def cast_id(idVal, field_type):
    """If possible, re-cast a value to a specific field type
        Otherwise, cast it as a string."""
    if field_type == "String":
        idVal = str(idVal)
    else:
        try:
            idVal = int(idVal)
        except ValueError:
            idVal = str(idVal)

    return idVal

#End cast_id function


def remove_dups(tempgdb, new_features, cur_features, fields, id_field, dt_field, loc_fields):
    """Compares records with matching ids and determines which is more recent.
        If the new record is older than the existing record, no updates
        If the new record has the same or a more recent date, the locations
            are compared:

            If the location has changed the existing record is deleted
            If the locations are the same the existing record attributes
                are updated"""
    # Create temporary table of the new data
    tempTable = join(tempgdb, "tempTableLE")

    tv = arcpy.MakeTableView_management(new_features, 'tempIncTableView')
    arcpy.CopyRows_management(tv, tempTable)
    del tv

    # Dictionary of attributes from most recent report
    att_dict = {}

    # Field indices for identifying most recent record
    id_index = fields.index(id_field)
    dt_index = fields.index(dt_field)

    # Field type of ID field in feature class
    desc = arcpy.Describe(cur_features)
    all_fields = desc.fields
    for f in all_fields:
        if f.name == id_field:
            field_type = f.type
            break

    # Records with null values that cannot be processed
    null_records = ""

    # Build dictionary of most recent occurance of each incident in the spreadsheet
    with arcpy.da.SearchCursor(tempTable, fields) as csvrows:

        for csvrow in csvrows:

            idVal = csvrow[id_index]
            dtVal = csvrow[dt_index]

            # Process only rows containing all required values
            if idVal is None or dtVal is None:

                # If required values are missing, write the row out
                null_records = "{}{}\n".format(null_records, csvrow)

            else:
                try:
                    if idVal.is_integer():
                        idVal = int(idVal)
                except AttributeError:
                    pass

                idVal = cast_id(idVal, field_type)

                try:
                    # Try to find the id in the dictionary
                    id_vals = att_dict[idVal]

                    # Test if the new row is more recent
                    status = compare_dates(fields, dt_field, csvrow, id_vals)

                    # If it is, update the values in the dictionary
                    if status:
                        id_vals = update_dictionary(fields, csvrow, id_vals)

                except KeyError:
                    # If the id isn't in the dictionary, build a dictionary
                    id_vals = {}
                    id_vals = update_dictionary(fields, csvrow, id_vals)
                    att_dict[idVal] = id_vals

    # Compare the existing features to the dictionary to find updated incidents

    update_count = 0

    if len(att_dict) > 0:

        # Use the dictionary keys to build a where clause
        if not len(att_dict) == 1:
            vals = tuple(att_dict.keys())
            where_clause = """{0} IN {1}""".format(id_field, vals)
        else:
            where_clause = """{0} = {1}""".format(id_field, att_dict.keys()[0])

        with arcpy.da.UpdateCursor(cur_features, fields, where_clause) as fcrows:
            for fcrow in fcrows:

                # Get the id value for the row
                idVal = fcrow[id_index]

                idVal = cast_id(idVal, field_type)

                try:
                    # Grab the attributes values associated with that id
                    id_vals = att_dict[idVal]

                    # Test if fc record is more recent (date_status = True)
                    try:
                        date_status = compare_dates(fields,dt_field, fcrow, id_vals)

                    except TypeError:
                        raise Exception(e15.format(dt_field, new_features, timestamp))

                    # If fc more recent, update the values in the dictionary
                    if date_status:
                        id_vals = update_dictionary(fields, fcrow, id_vals)

                    else:
                        loc_status = compare_locations(fields, fcrow, id_vals, loc_fields)

                        # If the location has changed
                        if loc_status:

                            # Delete the row from the feature class
                            fcrows.deleteRow()

                        else:
                            # Same location, try to update the feature attributes
                            try:
                                i = 0
                                while i <= len(fields) - 1:
                                    fcrow[i] = id_vals[fields[i]]
                                    i += 1
                                fcrows.updateRow(fcrow)

                                # Delete the record from the dictionary
                                del att_dict[idVal]

                                update_count += 1

                            # If there is a field type mismatch between the dictionary
                            #   value and the feature class, delete the row in the
                            #   feature class. The spreadsheet record will be
                            #   re-geocoded and placed in the un-appended report for
                            #   further attention.
                            except RuntimeError:
                                fcrows.deleteRow()

                except KeyError:
                    pass

    # Clean up new data to reflect updates from current data
    with arcpy.da.UpdateCursor(tempTable, fields) as updaterows:
        del_count = 0

        for updaterow in updaterows:
            idVal = updaterow[id_index]

            try:
                if idVal.is_integer():
                    idVal = int(idVal)
            except AttributeError:
                pass

            idVal = cast_id(idVal, field_type)

            try:
                id_vals = att_dict[idVal]

                try:
                    dtVal = dt.strptime(updaterow[dt_index], timestamp)
                    dtVal.replace(microsecond=0)
                except TypeError:
                    dtVal = updaterow[dt_index]

                try:
                    dict_date = dt.strptime(id_vals[dt_field], timestamp)
                    dict_date.replace(microsecond=0)
                except TypeError:
                    dict_date = id_vals[dt_field]

                if not dict_date == dtVal:
                    updaterows.deleteRow()
                    del_count += 1

            except KeyError:
                # Delete incidents removed from the dictionary
                updaterows.deleteRow()
                del_count += 1

    # Return the records to geocode

    return tempTable, null_records, update_count, del_count - update_count

# End remove_dups function


def convert_to_utc(table, fields):
    """Convert the values in a list of fields
        from system time to UTC
    """
    # Convert each timestamp value from system timezone to UTC
    with arcpy.da.UpdateCursor(table, fields) as utc_rows:
        for row in utc_rows:
            for i in range(0, len(row)):
                try:
                    row[i] = dt.utcfromtimestamp(mktime(row[i].timetuple()))
                except AttributeError:
                    pass

            utc_rows.updateRow(row)

# End convert_to_utc function


def convert_from_utc(table, fields):
    """Convert the values in a list of fields
        from UTC to system time
    """
    # Convert each timestamp value from system timezone to UTC
    with arcpy.da.UpdateCursor(table, fields) as utc_rows:
        for row in utc_rows:
            for i in range(0, len(row)):
                try:
                    row[i] = dt.fromtimestamp(timegm(row[i].timetuple()))
                except AttributeError:
                    pass
            utc_rows.updateRow(row)

# End convert_from_utc function


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
        cfg = ConfigParser.ConfigParser()
        cfg.read(config_file)
    else:
        raise Exception(e1.format("Configuration file", config_file, ""))

    # Get general configuration values
    incidents = cfg.get('GENERAL', 'spreadsheet')
    inc_features = cfg.get('GENERAL', 'incident_features')
    id_field = cfg.get('GENERAL', 'incident_id')
    report_date_field = cfg.get('GENERAL', 'report_date_field')
    reports = cfg.get('GENERAL', 'reports')
    loc_type = cfg.get('GENERAL', 'loc_type')
    summary_field = cfg.get('GENERAL', 'summary_field')
    transform_method = cfg.get('GENERAL', 'transform_method')
    pub_status = cfg.get('GENERAL', 'pub_status')
    delete_duplicates = cfg.get('GENERAL', 'delete_duplicates')

    if delete_duplicates in ('true', 'True', True):
        delete_duplicates = True
        if report_date_field == "":
            raise Exception(e16)
    if delete_duplicates in ('false', 'False'):
        delete_duplicates = False

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

            # Validate output feature class geometry type
            desc = arcpy.Describe(inc_features)
            if not desc.shapeType == "Point":
                raise Exception(e6.format(inc_features))

            # Identify field names in both fc and csv
            if arcpy.Exists(incidents):
                csvfieldnames = [f.name for f in arcpy.ListFields(incidents)]

            else:
                raise Exception(e1.format("Spreadsheet", incidents, ""))

            if arcpy.Exists(inc_features):
                incfieldnames = [f.name for f in arcpy.ListFields(inc_features)]
            else:
                raise Exception(e1.format("Feature Class", inc_features, ""))

            matchfieldnames = []
            for name in csvfieldnames:
                if name in incfieldnames:
                    matchfieldnames.append(name)

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
                lg_field = cfg.get('COORDINATES', 'long_field')
                lt_field = cfg.get('COORDINATES', 'lat_field')
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

            # Validate basic publishing parameters
            if not pub_status == "":

                # Get general publishing parameters
                mxd = cfg.get('PUBLISHING', 'mxd')
                username = cfg.get('PUBLISHING', 'user_name')
                password = cfg.get('PUBLISHING', 'password')

                # Test for required inputs
                if not arcpy.Exists(mxd):
                    raise Exception(e1.format("Map document", mxd, ""))

                if splitext(mxd)[1] != ".mxd":
                    raise Exception(e3)

                # Test for required inputs
                if username == "" or password == "":
                    if pub_status == "ARCGIS_ONLINE":
                        raise Exception(e8)

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
                    print m19.format(len(SumVals)-len(listSumVals))
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
                                                                             inc_features,
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
                with open (rptUnmatch, "wb") as umatchFile:
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

            # Reproject the features
            sr_input = arcpy.Describe(tempFC).spatialReference
            sr_output = arcpy.Describe(inc_features).spatialReference

            if sr_input != sr_output:
                proj_out = "{}_proj".format(tempFC)

                arcpy.Project_management(tempFC,
                                         proj_out,
                                         sr_output,
                                         transform_method)
                tempFC = proj_out

            # Append geocode results to fc
            rptNoAppend = join(reports, "{0}_{1}.csv".format(fileNow, noappend_name))

            with arcpy.da.SearchCursor(tempFC, copyfieldnames) as csvrows:
                with arcpy.da.InsertCursor(inc_features, copyfieldnames) as incrows:
                    # Open csv for un-appended records
                    with open(rptNoAppend, "wb") as appendFile:

                        appendwriter = csv.writer(appendFile)
                        appendwriter.writerow(errorfieldnames)

                        # Index of field with incident ID
                        record = errorfieldnames.index(id_field)

                        # Initiate count of successfully appended records
                        countAppend = 0

                        # List of ids of records not successfully appended
                        errorRecords = []

                        for csvrow in csvrows:
                            try:
                                if loc_type == "COORDINATES":
                                    if remove_zeros:
                                        lt_index = copyfieldnames.index(lt_field)
                                        lg_index = copyfieldnames.index(lg_field)

                                        ltVal = csvrow[lt_index]
                                        lgVal = csvrow[lg_index]

                                        if ltVal == 0 and lgVal == 0:
                                            raise Exception("invalid_coordinates")

                                # If the row can be appended
                                incrows.insertRow(csvrow)
                                countAppend += 1

                            except Exception as reason:
                                # e.g. 'The value type is incompatible with the
                                #       field type. [INCIDENTDAT]'
                                # Alternatively, the exception
                                #      'invalid_coordinates' raised by the
                                #       remove_zeros test above

                                # Get the name of the problem field
                                badfield = reason[0].split(" ")[-1]
                                badfield = badfield.strip(" []")

                                # Append field name to start of record
                                csvrow = list(csvrow)
                                csvrow.insert(0, badfield)

                                # Split the coordinate tuple into X and Y
                                lng, lat = list(csvrow[-1])
                                csvrow[-1] = lng
                                csvrow.append(lat)
                                csvrow = tuple(csvrow)

                                # Write the record out to csv
                                appendwriter.writerow(csvrow)

                                # Add id and field to issue list
                                errorRecords.append(w4.format(csvrow[record], badfield))

            # If issues were reported, print them
            if len(errorRecords) != 0:
                messages(w1.format(len(errorRecords), inc_features, rptNoAppend), log, 1)

            messages(m18.format(countAppend, inc_features), log)

            del incrows, csvrows

            # Convert times to UTC if publishing to AGOL
            if pub_status == "ARCGIS_ONLINE":

                # Get date fields
                date_fields = [f.name for f in arcpy.ListFields(inc_features) if f.type == "Date" and f.name in matchfieldnames]

                # Convert from system timezone to UTC
                convert_to_utc(inc_features, date_fields)

            # Publish incidents
            if not pub_status == "":

                timeNow = dt.strftime(dt.now(), time_format)
                messages(m5.format(timeNow), log)

                errors = serviceutils.publish_service(cfg, pub_status, mxd, username, password)

                # Print analysis errors
                if errors:
                    raise Exception(e4.format(errors))

            # Convert times from UTC to system timezone
            if pub_status == "ARCGIS_ONLINE":
                convert_from_utc(inc_features, date_fields)

            timeNow = dt.strftime(dt.now(), time_format)
            messages(m8.format(timeNow), log)

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
            # Clean up
            try:
                arcpy.Delete_management(tempgdb)
            except:
                pass

if __name__ == '__main__':
    argv = tuple(arcpy.GetParameterAsText(i)
                 for i in range(arcpy.GetArgumentCount()))
    main(*argv)