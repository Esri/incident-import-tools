##incident-import-tools

Toolbox and scripts for importing spreadsheets to a gdb and optionally publishing out to ArcGIS Online (feature service) or ArcGIS for Server (dynamic map service).   

Geometry can be assigned to features using provided coordinate values in a known spatial reference system, or by geocoding an address associated with each incident.   

These scripts can be scheduled using Windows Task Scheduler to automatically update the feature class and service.

## Features

* Publish features from a spreadsheet to an existing service using ArcGIS Online or ArcGIS for Server
* Features can be located using addresses or coordinate pairs
* Optionally, avoid creating duplicate records by update existing records and only adding new features to the service
* Run the tools manually through ArcMap or ArcCatalog, or schedule them to run regularly using Windows Task Sceduler


## Usage Notes

- Tool imports spreadsheet data to a point feature class in a file, enterprise, or workgroup geodatabase with a similar schema. Only values in fields that exist in both the spreadsheet and feature class will be copied. Field names are case-sensitive.
- Spreadsheet and feature class must have fields with a unique identifier for each record. These fields must have the same field name.
- To filter for duplicates, both the spreadsheet and the feature class must have fields with the date, and optionally time, of the incident or incident report. These fields must have the same field name and dates must be in a the format mm/dd/yyyy hh:mm. This format can be modified by changing the value of the timestamp variable at the top of the import\_publish_incidents.py script.
- All date, time, and timestamp fields must be formatted in the spreadsheet to display, in order of requirement:
	1. year
	- month
	- day
	- hour
	- minute

	For example, a field containing only the time 16:45 will cause the tool to fail because it is missing the year, month and day information associated with that time.
- These tools are set up to use the World Geocode service, which requires,  and consumes credits from, an ArcGIS Online organizational account.
	
	[Learn more about setting up a connection to the World Geocode Service](http://resources.arcgis.com/en/help/main/10.1/index.html#//00250000004v000000)
	
	Optionally, use your own locator or geocode service. This requires some additional configuration of the scripts. Open import\_publish_incidents.py in IDLE or a text editor and modify the values of the following parameters located near the top of the script:
	- all\_locator_fields: in order, all the input address fields accepted by your locator
	- loc\_address_field: Your locator's input address field that looks for the house number and street name information
	- loc\_city_field: Your locator's input address field that looks for the city information
	- loc\_state_field: Your locator's input address field that looks for the state or province information
	- loc\_zip_field: Your locator's input address field that looks for the ZIP or postal code information

## Instructions

1. Download and unzip these tools.
2. Download and unzip requests-master.zip.
3. Open requests-master and copy the requests folder into the scripts folder of the incident import tools.
4. In ArcMap or ArcCatalog, open the Configure Incident Imports tool. Complete the parameters and click OK to create a configuration file storing these parameter values.
5. Run the Import Incidents tool, using the previously created configuration file as input. Be default this configuration file is saved to the scripts folder, but it may be moved to another location if necessary.
6. Examine the output messaging and reports for comments on failures and data errors.
7. Optionally, set up Windows Task Scheduler to run import\_publish_incidents.py automatically on a schedule with the configuration file as input.

## Requirements


- ArcGIS for Desktop
- [Requests module](https://github.com/kennethreitz/requests/) for Python
- ArcGIS Online organizational account or ArcGIS for Server if data is to be published (optional)


## Resources


* [ArcGIS Solutions](http://solutions.arcgis.com/)
* [ArcGIS Blog](http://blogs.esri.com/esri/arcgis/)
* [twitter@esri](http://twitter.com/esri)


## Issues


Find a bug or want to request a new feature?  Please let us know by submitting an issue.


## Contributing


Esri welcomes contributions from anyone and everyone. Please see our [guidelines for contributing](https://github.com/esri/contributing).


## Licensing
Copyright 2013 Esri


Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at


   http://www.apache.org/licenses/LICENSE-2.0


Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.


A copy of the license is available in the repository's [license.txt]( https://raw.github.com/Esri/quickstart-map-js/master/license.txt) file.


[](Esri Tags: Local-Government Local Government Law Fire Incident Import)
[](Esri Language: Python)​