import json
from .._abstract.abstract import BaseAGOLClass, BaseSecurityHandler
from ..security import security
########################################################################
class Services(BaseAGOLClass):
    """
       The administration resource is the root node and initial entry point
       into a Spatial Data Server adminstrative interface. This resource
       represents a catalog of data sources and services published on the
       host.
       The current version and type of the server is also returned in the
       response. The value of the version is a number such that its value
       at a future release is guaranteed to be greater than its value at a
       previous release.
       Inputs:
          url - url to service admin site: http://<web server hostname>/arcgis/rest/admin
          securityHandler - AGOL/Portal
    """

    _url = None
    _currentVersion = None
    _resources = None
    _serverType = None
    _proxy_port = None
    _proxy_url = None
    _securityHandler = None
    _services = None
    _folders = None
    _description = None
    _folderName = None
    #----------------------------------------------------------------------
    def __init__(self,
                 url,
                 securityHandler,
                 initialize=False,
                 proxy_url=None,
                 proxy_port=None):
        """Constructor"""
        self._url = url
        self._proxy_url = proxy_url
        self._proxy_port = proxy_port

        if isinstance(securityHandler, BaseSecurityHandler):
            if hasattr(securityHandler, 'is_portal'):
                if securityHandler.is_portal:
                    if hasattr(securityHandler, 'portalServerHandler'):
                        self._securityHandler = securityHandler.portalServerHandler(serverUrl=url)
                    else:
                        self._securityHandler = securityHandler
                else:
                    self._securityHandler = securityHandler

            else:
                self._securityHandler = securityHandler



        else:
            raise AttributeError("Admin only supports AGOL, ArcGIS, Portal, NTLM, LDAP, PKI and OAuth security handlers")

        if initialize:
            self.__init()
    #----------------------------------------------------------------------
    def __init(self):
        """ initializes the service """
        params = {"f" : "json"}
        json_dict = self._do_get(self._url, params,
                                 proxy_port=self._proxy_port,
                                 securityHandler=self._securityHandler,
                                 proxy_url=self._proxy_url)
        attributes = [attr for attr in dir(self)
                      if not attr.startswith('__') and \
                      not attr.startswith('_')]
        for k,v in json_dict.iteritems():
            if k in attributes:
                setattr(self, "_"+ k, json_dict[k])
            else:
                print k, " - attribute not implemented in hostedservice.Services."
            del k, v
    #----------------------------------------------------------------------
    @property
    def folders(self):
        """returns the service folders"""
        if self._folders is None:
            self.__init()
        return self._folders
    #----------------------------------------------------------------------
    @property
    def description(self):
        """returns the description property"""
        if self._description is None:
            self.__init()
        return self._description
    #----------------------------------------------------------------------
    @property
    def folderName(self):
        """returns the folder name"""
        if self._folderName is None:
            self.__init()
        return self._folderName
    #----------------------------------------------------------------------
    @property
    def securityHandler(self):
        """ gets the security handler """
        return self._securityHandler
    #----------------------------------------------------------------------
    @securityHandler.setter
    def securityHandler(self, value):
        """ sets the security handler """
        if isinstance(value, BaseSecurityHandler):
            if isinstance(value, security.AGOLTokenSecurityHandler):
                self._securityHandler = value

            elif isinstance(value, security.OAuthSecurityHandler):

                self._securityHandler = value
            else:
                pass
    #----------------------------------------------------------------------
    @property
    def currentVersion(self):
        """ returns the software's current version """
        if self._currentVersion is None:
            self.__init()
        return self._currentVersion
    #----------------------------------------------------------------------
    @property
    def resources(self):
        """ list of all resources on the AGOL site """
        if self._resources is None:
            self.__init()
        return self._resources
    #----------------------------------------------------------------------
    @property
    def serverType(self):
        """ returns the server type """
        if self._serverType is None:
            self.__init()
        return self._serverType
    #----------------------------------------------------------------------
    @property
    def services(self):
        """ returns all the service objects in the admin service's page """
        self._services = []
        params = {"f": "json"}
        if not self._url.endswith('/services'):
            uURL = self._url + "/services"
        else:
            uURL = self._url
        res = self._do_get(url=uURL, param_dict=params,
                           securityHandler=self._securityHandler,
                           proxy_port=self._proxy_port,
                           proxy_url=self._proxy_url)
        for k, v in res.iteritems():
            if k == "foldersDetail":
                for item in v:
                    if 'isDefault' in item and item['isDefault'] == False:
                        fURL = self._url + "/services/" + item['folderName']
                        resFolder = self._do_get(url=fURL, param_dict=params,
                                                 securityHandler=self._securityHandler,
                                                 proxy_port=self._proxy_port,
                                                 proxy_url=self._proxy_url)
                        for k1, v1 in resFolder.iteritems():
                            if k1 == "services":
                                self._checkservice(k1,v1,fURL)
            elif k == "services":
                self._checkservice(k,v,uURL)
        return self._services

    def _checkservice(self,k,v,url):
        for item in v:
            if 'adminServiceInfo' in item:
                item = item['adminServiceInfo']
            if 'type' in item and item['type'] == 'MapServer':
                if 'name' in item:
                    name = item['name']
                typefs = item['type']
                if item.has_key('name') == True:
                    name = item['name']
                elif item.has_key('serviceName') == True:
                    name = item['serviceName']

                self._services.append(
                AdminMapService(url=url + r"/%s.%s" % (name,item['type']),
                                        securityHandler=self._securityHandler,
                                       proxy_url=self._proxy_url,
                                       proxy_port=self._proxy_port,
                                       initialize=False)
                        )
            elif 'type' in item and item['type'] == 'FeatureServer':
                if 'name' in item:
                    name = item['name']
                typefs = item['type']
                if item.has_key('adminServiceInfo') == True:
                    name = item['adminServiceInfo']['name']
                    typefs = item['adminServiceInfo']['type']
                elif item.has_key('serviceName') == True:
                    name = item['serviceName']
                    typefs = item['type']

                surl = url + r"/%s.%s" % (name,
                                           typefs)
                self._services.append(
                    AdminFeatureService(url=surl,
                                        securityHandler=self._securityHandler,
                                        initialize=False,
                                        proxy_url=self._proxy_url,
                                        proxy_port=self._proxy_port))
########################################################################
class AdminMapService(BaseAGOLClass):
    """
       A map service offer access to map and layer content.

       The REST API administrative map service resource represents a map
       service. This resource provides basic information about the map,
       including the layers that it contains, whether the map is cached or
       not, its spatial reference, initial and full extents, etc...  The
       administrative map service resource maintains a set of operations
       that manage the state and contents of the service.
    """
    _securityHandler = None
    _url = None
    _initialExtent = None
    _currentJob = None
    _lodInfos = None
    _id = None
    _size = None
    _tileInfo = None
    _jobStatus = None
    _access = None
    _cacheExecutionStatus = None
    _type = None
    _status = None
    _jobs = None
    _sourceType = None
    _fullExtent = None
    _minScale = None
    _count = None
    _maxExportTilesCount = None
    _name = None
    _created = None
    _maxScale = None
    _modified = None
    _serverId = None
    _exportTilesAllowed = None
    _urlService = None
    _readonly = None
    _resampling = None
    _json = None
    _json_dict = None
    #----------------------------------------------------------------------
    def __init__(self, url,
                 securityHandler,
                 initialize=False,
                 proxy_url=None,
                 proxy_port=None):
        """Constructor"""
        self._url = url


        if isinstance(securityHandler, BaseSecurityHandler):
            if hasattr(securityHandler, 'is_portal'):
                if securityHandler.is_portal:
                    if hasattr(securityHandler, 'portalServerHandler'):
                        self._securityHandler = securityHandler.portalServerHandler(serverUrl=url)
                    else:
                        self._securityHandler = securityHandler
                else:
                    self._securityHandler = securityHandler

            else:
                self._securityHandler = securityHandler

        else:
            raise AttributeError("Admin only supports AGOL, ArcGIS, Portal, NTLM, LDAP, PKI and OAuth security handlers")

        self._proxy_url = proxy_url
        self._proxy_port = proxy_port
        if initialize:
            self.__init()
    #----------------------------------------------------------------------
    def __init(self):
        """ initializes the service """
        params = {
            "f" : "json",
        }
        json_dict = self._do_get(self._url, params,
                                 securityHandler=self._securityHandler,
                                 proxy_port=self._proxy_port,
                                 proxy_url=self._proxy_url)
        self._json_dict = json_dict
        self._json = json.dumps(self._json_dict)
        attributes = [attr for attr in dir(self)
                      if not attr.startswith('__') and \
                      not attr.startswith('_')]
        for k,v in json_dict.iteritems():
            if k == "url":
                self._urlService = v

            elif k in attributes:
                setattr(self, "_"+ k, json_dict[k])
            else:
                print k,  " - attribute not implemented. Please log an support request."
            del k, v
    #----------------------------------------------------------------------
    def __iter__(self):
        """returns the key/value pair of the raw JSON"""
        if self._json_dict is None:
            self.__init()
        for k,v in self._json_dict.iteritems():
            yield [k,v]
    #----------------------------------------------------------------------
    def __str__(self):
        """returns raw json from url query"""
        if self._json is None:
            self.__init()
        return self._json
    #----------------------------------------------------------------------
    @property
    def readonly(self):
        """returns the readonly property"""
        if self._readonly is None:
            self.__init()
        return self._readonly
    #----------------------------------------------------------------------
    @property
    def resampling(self):
        """returns the resampling property"""
        if self._resampling is None:
            self.__init()
        return self._resampling

    #----------------------------------------------------------------------
    @property
    def currentJob(self):
        '''gets the currentJob'''
        if self._currentJob is None:
            self.__init()
        return self._currentJob

    #----------------------------------------------------------------------
    @property
    def lodInfos(self):
        '''gets the lodInfos'''
        if self._lodInfos is None:
            self.__init()
        return self._lodInfos
    #----------------------------------------------------------------------
    @property
    def id(self):
        '''gets the id'''
        if self._id is None:
            self.__init()
        return self._id
    #----------------------------------------------------------------------
    @property
    def size(self):
        '''gets the size'''
        if self._size is None:
            self.__init()
        return self._size
    #----------------------------------------------------------------------
    @property
    def tileInfo(self):
        '''gets the tileInfo'''
        if self._tileInfo is None:
            self.__init()
        return self._tileInfo
    #----------------------------------------------------------------------
    @property
    def jobStatus(self):
        '''gets the jobStatus'''
        if self._jobStatus is None:
            self.__init()
        return self._jobStatus
    #----------------------------------------------------------------------
    @property
    def access(self):
        '''gets the access'''
        if self._access is None:
            self.__init()
        return self._access
    #----------------------------------------------------------------------
    @property
    def cacheExecutionStatus(self):
        '''gets the cacheExecutionStatus'''
        if self._cacheExecutionStatus is None:
            self.__init()
        return self._cacheExecutionStatus
    #----------------------------------------------------------------------
    @property
    def type(self):
        '''gets the type'''
        if self._type is None:
            self.__init()
        return self._type

    #----------------------------------------------------------------------
    @property
    def jobs(self):
        '''gets the jobs'''
        if self._jobs is None:
            self.__init()
        return self._jobs

    #----------------------------------------------------------------------
    @property
    def sourceType(self):
        '''gets the sourceType'''
        if self._sourceType is None:
            self.__init()
        return self._sourceType

    #----------------------------------------------------------------------
    @property
    def fullExtent(self):
        '''gets the fullExtent'''
        if self._fullExtent is None:
            self.__init()
        return self._fullExtent

    #----------------------------------------------------------------------
    @property
    def minScale(self):
        '''gets the minScale'''
        if self._minScale is None:
            self.__init()
        return self._minScale

    #----------------------------------------------------------------------
    @property
    def count(self):
        '''gets the count'''
        if self._count is None:
            self.__init()
        return self._count

    #----------------------------------------------------------------------
    @property
    def maxExportTilesCount(self):
        '''gets the maxExportTilesCount'''
        if self._maxExportTilesCount is None:
            self.__init()
        return self._maxExportTilesCount

    #----------------------------------------------------------------------
    @property
    def name(self):
        '''gets the name'''
        if self._name is None:
            self.__init()
        return self._name

    #----------------------------------------------------------------------
    @property
    def created(self):
        '''gets the created'''
        if self._created is None:
            self.__init()
        return self._created

    #----------------------------------------------------------------------
    @property
    def urlService(self):
        '''gets the url'''
        if self._urlService is None:
            self.__init()
        return self._urlService

    #----------------------------------------------------------------------
    @property
    def maxScale(self):
        '''gets the maxScale'''
        if self._maxScale is None:
            self.__init()
        return self._maxScale

    #----------------------------------------------------------------------
    @property
    def modified(self):
        '''gets the modified'''
        if self._modified is None:
            self.__init()
        return self._modified

    #----------------------------------------------------------------------
    @property
    def serverId(self):
        '''gets the serverId'''
        if self._serverId is None:
            self.__init()
        return self._serverId

    #----------------------------------------------------------------------
    @property
    def exportTilesAllowed(self):
        '''gets the exportTilesAllowed'''
        if self._exportTilesAllowed is None:
            self.__init()
        return self._exportTilesAllowed

    #----------------------------------------------------------------------
    @property
    def initialExtent(self):
        """gets the initialExtent"""
        if self._initialExtent is None:
            self.__init()
        return self._initialExtent

    #----------------------------------------------------------------------
    @property
    def status(self):
        """ returns the service status """
        if self._status is None:
            self.__init()
        return self._status

    #----------------------------------------------------------------------
    @property
    def securityHandler(self):
        """ returns the current security handler """
        return self._securityHandler
    #----------------------------------------------------------------------
    @securityHandler.setter
    def securityHandler(self, value):
        """ sets the security handler """
        if isinstance(value, security.AGOLTokenSecurityHandler):
            self._securityHandler = value

        else:
            raise AttributeError("This object only accepts security.AGOLTokenSecurityHandler")
    #----------------------------------------------------------------------
    def refresh(self, serviceDefinition=True):
        """
        The refresh operation refreshes a service, which clears the web
        server cache for the service.
        """
        url = self._url + "/MapServer/refresh"
        params = {
            "f" : "json",
            "serviceDefinition" : serviceDefinition
        }

        res =  self._do_post(url=self._url,
                             param_dict=params,
                             securityHandler=self._securityHandler,
                             proxy_url=self._proxy_url,
                             proxy_port=self._proxy_port)
        self.__init()
        return res
    #----------------------------------------------------------------------
    def cancelJob(self, jobId):
        """
        The cancel job operation supports cancelling a job while update
        tiles is running from a hosted feature service. The result of this
        operation is a response indicating success or failure with error
        code and description.

        Inputs:
           jobId - jobId to cancel
        """
        url = self._url + "/jobs/%s/cancel" % jobId
        params = {
            "f" : "json"
        }
        return self._do_post(url=url,
                             param_dict=params,
                             securityHandler=self._securityHandler,
                             proxy_url=self._proxy_url,
                             proxy_port=self._proxy_port)
    #----------------------------------------------------------------------
    def jobStatistics(self, jobId):
        """
        The delete job operation supports deleting a job from a hosted map
        service. The result of this operation is a response indicating
        success or failure with error code and description.

        """
        url = self._url + "/jobs/%s" % jobId
        params = {
            "f" : "json"
        }
        return self._do_post(url=url,
                             param_dict=params,
                             securityHandler=self._securityHandler,
                             proxy_url=self._proxy_url,
                             proxy_port=self._proxy_port)
    #----------------------------------------------------------------------
    def editTileService(self,
                        serviceDefinition=None,
                        minScale=None,
                        maxScale=None,
                        sourceItemId=None,
                        exportTilesAllowed=False,
                        maxExportTileCount=100000):
        """
        This post operation updates a Tile Service's properties

        Inputs:
           serviceDefinition - updates a service definition
           minScale - sets the services minimum scale for caching
           maxScale - sets the service's maximum scale for caching
           sourceItemId - The Source Item ID is the GeoWarehouse Item ID of the map service
           exportTilesAllowed - sets the value to let users export tiles
           maxExportTileCount - sets the maximum amount of tiles to be exported
             from a single call.
        """
        params = {
            "f" : "json",
        }
        if not serviceDefinition is None:
            params["serviceDefinition"] = serviceDefinition
        if not minScale is None:
            params['minScale'] = float(minScale)
        if not maxScale is None:
            params['maxScale'] = float(maxScale)
        if not sourceItemId is None:
            params["sourceItemId"] = sourceItemId
        if not exportTilesAllowed is None:
            params["exportTilesAllowed"] = exportTilesAllowed
        if not maxExportTileCount is None:
            params["maxExportTileCount"] = int(maxExportTileCount)
        url = self._url + "/edit"
        return self._do_post(url=url,
                             param_dict=params,
                             securityHandler=self._securityHandler,
                             proxy_url=self._securityHandler.proxy_url,
                             proxy_port=self._securityHandler.proxy_port)

########################################################################
class AdminFeatureService(BaseAGOLClass):
    """
       A feature service can contain datasets (e.g. tables, views) with and
       without a spatial column.  Datasets with a spatial column are
       considered layers and without a spatial column are considered
       tables.  A feature service allows clients to query and edit feature
       geometry and attributes.

       This resource provides basic information about the feature service
       including the feature layers and tables that it contains, the
       service description, etc.  The administrative feature service
       resource maintains a set of operations that manage the state and
       contents of the service.  Note, query and edit operations are not
       available via the adminstrative resource.
    """

    _url = None
    _xssPreventionInfo = None
    _size = None
    _adminServiceInfo = None
    _initialExtent = None
    _copyrightText = None
    _layers = None
    _tables = None
    _enableZDefaults = None
    _syncCapabilities = None
    _capabilities = None
    _currentVersion = None
    _hasVersionedData = None
    _units = None
    _supportedQueryFormats = None
    _maxRecordCount = None
    _allowGeometryUpdates = None
    _description = None
    _hasStaticData = None
    _fullExtent = None
    _serviceDescription = None
    _editorTrackingInfo = None
    _supportsDisconnectedEditing = None
    _spatialReference = None
    _syncEnabled = None
    _dict = None
    _json = None
    _json_dict = None
    _error = None
    #----------------------------------------------------------------------
    def __init__(self, url,
                 securityHandler,
                 initialize=False,
                 proxy_url=None,
                 proxy_port=None):
        """Constructor"""
        if url is None:
            return
        if 'rest/services' in url:
            url = url.replace('rest/services', 'rest/admin/services')
        self._url = url


        if isinstance(securityHandler, BaseSecurityHandler):
            if hasattr(securityHandler, 'is_portal'):
                if securityHandler.is_portal:
                    if hasattr(securityHandler, 'portalServerHandler'):
                        self._securityHandler = securityHandler.portalServerHandler(serverUrl=url)
                    else:
                        self._securityHandler = securityHandler
                else:
                    self._securityHandler = securityHandler

            else:
                self._securityHandler = securityHandler


        else:
            raise AttributeError("Admin only supports AGOL, ArcGIS, Portal, NTLM, LDAP, PKI and OAuth security handlers")

        self._proxy_url = proxy_url
        self._proxy_port = proxy_port
        if initialize:
            self.__init()
    #----------------------------------------------------------------------
    def __init(self):
        """ initializes the service """
        params = {
            "f" : "json",
        }

        json_dict = self._do_get(self._url, params,
                                 securityHandler=self._securityHandler,
                                 proxy_port=self._proxy_port,
                                 proxy_url=self._proxy_url)
        self._json_dict = json_dict
        self._dict = json_dict
        self._json = json.dumps(self._dict)
        attributes = [attr for attr in dir(self)
                      if not attr.startswith('__') and \
                      not attr.startswith('_')]
        for k,v in json_dict.iteritems():
            if k == "layers":
                self._layers = []
                for lyr in v:
                    fl = AdminFeatureServiceLayer(url=self._url + "/%s" % lyr['id'],
                                                  securityHandler=self._securityHandler,
                                                  proxy_port=self._proxy_port,
                                                  proxy_url=self._proxy_url)
                    fl.loadAttributes(json_dict = lyr)
                    self._layers.append(fl)
                    del fl
                    del lyr
            elif k == "tables":
                self._tables = []
                for lyr in v:
                    fl = AdminFeatureServiceLayer(url=self._url + "/%s" % lyr['id'],
                                                  securityHandler=self._securityHandler,
                                                  proxy_port=self._proxy_port,
                                                  proxy_url=self._proxy_url)
                    fl.loadAttributes(json_dict = lyr)
                    self._tables.append(fl)
                    del fl
                    del lyr
            elif k in attributes:
                setattr(self, "_"+ k, json_dict[k])
            else:
                print k, " - attribute not implemented in AdminFeatureService."
    #----------------------------------------------------------------------
    @property
    def error(self):
        """gets the error message"""
        if self._error is None:
            self.__init()
        return self._error
    #----------------------------------------------------------------------
    @property
    def securityHandler(self):
        """ returns the security handler """
        return self._securityHandler
    #----------------------------------------------------------------------
    @securityHandler.setter
    def securityHandler(self, value):
        """ sets the security handler """
        if isinstance(value, BaseSecurityHandler):
            if isinstance(value, (security.AGOLTokenSecurityHandler,security.PortalTokenSecurityHandler,security.ArcGISTokenSecurityHandler)):
                self._securityHandler = value

            else:
                raise AttributeError("Admin only supports security.AGOLTokenSecurityHandler")
    #----------------------------------------------------------------------
    def __str__(self):
        """return object as string"""
        if self._json is None:
            self.__init()
        return self._json
    #----------------------------------------------------------------------
    def __iter__(self):
        """returns the key/value pair of the raw JSON"""
        if self._json_dict is None:
            self.__init()
        for k,v in self._json_dict.iteritems():
            yield [k,v]

    #----------------------------------------------------------------------
    @property
    def status(self):
        """ returns the service status """
        uURL = self._url + "/status"
        params = {
            "f" : "json"
        }
        return self._do_get(url=uURL, param_dict=params,
                            securityHandler=self._securityHandler,
                            proxy_port=self._proxy_port,
                            proxy_url=self._proxy_url)
    #----------------------------------------------------------------------
    def refresh(self):
        """ refreshes a service """
        params = {"f": "json"}
        uURL = self._url + "/refresh"
        res = self._do_get(url=uURL, param_dict=params,
                           securityHandler=self._securityHandler,
                           proxy_port=self._proxy_port,
                           proxy_url=self._proxy_url)
        self.__init()
        return res
    #----------------------------------------------------------------------
    @property
    def xssPreventionInfo(self):
        """returns the xssPreventionInfo information """
        if self._xssPreventionInfo is None:
            self.__init()
        return self._xssPreventionInfo
    #----------------------------------------------------------------------
    @property
    def size(self):
        """returns the size parameter"""
        if self._size is None:
            self.__init()
        return self._size
    #----------------------------------------------------------------------
    @property
    def maxRecordCount(self):
        """returns the max record count"""
        if self._maxRecordCount is None:
            self.__init()
        return self._maxRecordCount
    #----------------------------------------------------------------------
    @property
    def supportedQueryFormats(self):
        """"""
        if self._supportedQueryFormats is None:
            self.__init()
        return self._supportedQueryFormats
    #----------------------------------------------------------------------
    @property
    def capabilities(self):
        """ returns a list of capabilities """
        if self._capabilities is None:
            self.__init()
        return self._capabilities
    #----------------------------------------------------------------------
    @property
    def description(self):
        """ returns the service description """
        if self._description is None:
            self.__init()
        return self._description
    #----------------------------------------------------------------------
    @property
    def copyrightText(self):
        """ returns the copyright text """
        if self._copyrightText is None:
            self.__init()
        return self._copyrightText
    #----------------------------------------------------------------------
    @property
    def spatialReference(self):
        """ returns the spatial reference """
        if self._spatialReference is None:
            self.__init()
        return self._spatialReference
    #----------------------------------------------------------------------
    @property
    def initialExtent(self):
        """ returns the initial extent of the feature service """
        if self._initialExtent is None:
            self.__init()
        return self._initialExtent
    #----------------------------------------------------------------------
    @property
    def fullExtent(self):
        """ returns the full extent of the feature service """
        if self._fullExtent is None:
            self.__init()
        return self._fullExtent
    #----------------------------------------------------------------------
    @property
    def allowGeometryUpdates(self):
        """ informs the user if the data allows geometry updates """
        if self._allowGeometryUpdates is None:
            self.__init()
        return self._allowGeometryUpdates
    #----------------------------------------------------------------------
    @property
    def units(self):
        """ returns the measurement unit """
        if self._units is None:
            self.__init()
        return self._units
    #----------------------------------------------------------------------
    @property
    def syncEnabled(self):
        """ informs the user if sync of data can be performed """
        if self._syncEnabled is None:
            self.__init()
        return self._syncEnabled
    #----------------------------------------------------------------------
    @property
    def syncCapabilities(self):
        """ type of sync that can be performed """
        if self._syncCapabilities is None:
            self.__init()
        return self._syncCapabilities
    #----------------------------------------------------------------------
    @property
    def editorTrackingInfo(self):
        """"""
        if self._editorTrackingInfo is None:
            self.__init()
        return self._editorTrackingInfo
    #----------------------------------------------------------------------
    @property
    def hasStaticData(self):
        """"""
        if self._hasStaticData is None:
            self.__init()
        return self._hasStaticData

    #----------------------------------------------------------------------
    @property
    def currentVersion(self):
        """ returns the map service current version """
        if self._currentVersion is None:
            self.__init()
        return self._currentVersion
    #----------------------------------------------------------------------
    @property
    def serviceDescription(self):
        """ returns the serviceDescription of the map service """
        if self._serviceDescription is None:
            self.__init()
        return self._serviceDescription
    #----------------------------------------------------------------------
    @property
    def hasVersionedData(self):
        """ returns boolean for versioned data """
        if self._hasVersionedData is None:
            self.__init()
        return self._hasVersionedData
    #----------------------------------------------------------------------
    @property
    def supportsDisconnectedEditing(self):
        """ returns boolean is disconnecting editted supported """
        if self._supportsDisconnectedEditing is None:
            self.__init()
        return self._supportsDisconnectedEditing
    #----------------------------------------------------------------------
    @property
    def adminServiceInfo(self):
        """ returns the admin service information"""
        if self._adminServiceInfo is None:
            self.__init()
        return self._adminServiceInfo
    #----------------------------------------------------------------------
    @property
    def layers(self):
        """ returns the layers for a service """
        if self._layers is None:
            self.__init()
        return self._layers
    #----------------------------------------------------------------------
    @property
    def tables(self):
        """ returns the layers for a service """
        if self._tables is None:
            self.__init()
        return self._tables
    #----------------------------------------------------------------------
    @property
    def enableZDefaults(self):
        """ returns the layers for a service """
        if self._enableZDefaults is None:
            self.__init()
        return self._enableZDefaults

    #----------------------------------------------------------------------
    @property
    def asDictionary(self):
        """ returns the feature service as a dictionary object """
        if self._dict is None:
            self.__init()
        return self._dict
    #----------------------------------------------------------------------
    @property
    def url(self):
        """ returns boolean is disconnecting editted supported """
        if self._url is None:
            return None
        return self._url
    #----------------------------------------------------------------------
    @property
    def json(self):
        """ returns boolean is disconnecting editted supported """
        if self._dict is None:
            self.__init()
        return self._dict
    #----------------------------------------------------------------------
    def addToDefinition(self, json_dict):
        """
           The addToDefinition operation supports adding a definition
           property to a hosted feature service. The result of this
           operation is a response indicating success or failure with error
           code and description.

           This function will allow users to change add additional values
           to an already published service.

           Input:
              json_dict - part to add to host service.  The part format can
                          be derived from the asDictionary property.  For
                          layer level modifications, run updates on each
                          individual feature service layer object.
           Output:
              JSON message as dictionary
        """
        params = {
            "f" : "json",
            "addToDefinition" : json.dumps(json_dict),
            "async" : False
        }
        uURL = self._url + "/addToDefinition"
        res = self._do_post(url=uURL, param_dict=params,
                             securityHandler=self._securityHandler,
                             proxy_port=self._proxy_port,
                             proxy_url=self._proxy_url)
        self.refresh()
        return res
    #----------------------------------------------------------------------
    def updateDefinition(self, json_dict):
        """
           The updateDefinition operation supports updating a definition
           property in a hosted feature service. The result of this
           operation is a response indicating success or failure with error
           code and description.

           Input:
              json_dict - part to add to host service.  The part format can
                          be derived from the asDictionary property.  For
                          layer level modifications, run updates on each
                          individual feature service layer object.
           Output:
              JSON Message as dictionary
        """

        params = {
            "f" : "json",
            "updateDefinition" : json.dumps(json_dict),
            "async" : False
        }
        uURL = self._url + "/updateDefinition"
        res = self._do_post(url=uURL, param_dict=params,
                            securityHandler=self._securityHandler,
                            proxy_port=self._proxy_port,
                             proxy_url=self._proxy_url)
        self.refresh()
        return res
    #----------------------------------------------------------------------
    def deleteFromDefinition(self, json_dict):
        """
           The deleteFromDefinition operation supports deleting a
           definition property from a hosted feature service. The result of
           this operation is a response indicating success or failure with
           error code and description.
           See: http://resources.arcgis.com/en/help/arcgis-rest-api/index.html#/Delete_From_Definition_Feature_Service/02r30000021w000000/
           for additional information on this function.
           Input:
              json_dict - part to add to host service.  The part format can
                          be derived from the asDictionary property.  For
                          layer level modifications, run updates on each
                          individual feature service layer object.  Only
                          include the items you want to remove from the
                          FeatureService or layer.

           Output:
              JSON Message as dictionary

        """
        params = {
            "f" : "json",
            "deleteFromDefinition" : json.dumps(json_dict),
            "async" : False
        }
        uURL = self._url + "/deleteFromDefinition"
        res = self._do_post(url=uURL, param_dict=params,
                            securityHandler=self._securityHandler,
                            proxy_port=self._proxy_port,
                             proxy_url=self._proxy_url)
        self.refresh()
        return res
########################################################################
class AdminFeatureServiceLayer(BaseAGOLClass):
    """
       The layer resource represents a single feature layer or a non
       spatial table in a feature service.  A feature layer is a table or
       view with at least one spatial column.
       For tables, it provides basic information about the table such as
       its id, name, fields, types and templates.
       For feature layers, in addition to the table information above, it
       provides information such as its geometry type, min and max scales,
       and spatial reference.
       Each type includes information about the type such as the type id,
       name, and definition expression.  Sub-types also include a default
       symbol and a list of feature templates.
       Each feature template includes a template name, description and a
       prototypical feature.
       The property supportsRollbackOnFailures will be true to indicate the
       support for transactional edits.
       The property maxRecordCount returns the maximum number of records
       that will be returned at once for a query.
       The property capabilities returns Query, Create, Delete, Update, and
       Editing capabilities. The Editing capability will be included if
       Create, Delete or Update is enabled for a Feature Service.
       Note, query and edit operations are not available on a layer in the
       adminstrative view.
    """
    _editFieldsInfo = None
    _drawingInfo = None
    _typeIdField = None
    _advancedQueryCapabilities = None
    _supportsRollbackOnFailureParameter = None
    _globalIdField = None
    _supportsAdvancedQueries = None
    _id = None
    _relationships = None
    _capabilities = None
    _indexes = None
    _currentVersion = None
    _geometryType = None
    _hasStaticData = None
    _type = None
    _supportedQueryFormats = None
    _isDataVersioned = None
    _allowGeometryUpdates = None
    _description = None
    _defaultVisibility = None
    _extent = None
    _objectIdField = None
    _htmlPopupType = None
    _types = None
    _hasM = None
    _displayField = None
    _name = None
    _templates = None
    _supportsStatistics = None
    _hasAttachments = None
    _fields = None
    _maxScale = None
    _copyrightText = None
    _hasZ = None
    _maxRecordCount = None
    _minScale = None
    _drawingInfo = None
    _typeIdField = None
    _advancedQueryCapabilities = None
    _supportsRollbackOnFailureParameter = None
    _globalIdField = None
    _supportsAdvancedQueries = None
    _id = None
    _relationships = None
    _capabilities = None
    _indexes = None
    _currentVersion = None
    _geometryType = None
    _hasStaticData = None
    _type = None
    _supportedQueryFormats = None
    _isDataVersioned = None
    _allowGeometryUpdates = None
    _description = None
    _defaultVisibility = None
    _extent = None
    _objectIdField = None
    _htmlPopupType = None
    _types = None
    _hasM = None
    _displayField = None
    _name = None
    _templates = None
    _supportsStatistics = None
    _hasAttachments = None
    _fields = None
    _maxScale = None
    _copyrightText = None
    _hasZ = None
    _maxRecordCount = None
    _minScale = None
    _definitionExpression = None
    _parentLayer = None
    _subLayers = None
    _effectiveMinScale = None
    _effectiveMaxScale = None
    _timeInfo = None
    _canModifyLayer = None
    _hasLabels = None
    _canScaleSymbols = None
    _ownershipBasedAccessControlForFeatures = None
    _adminLayerInfo = None
    _supportsAttachmentsByUploadId = None
    _editingInfo = None
    _supportsCalculate = None
    _supportsValidateSql = None
    _supportsCoordinatesQuantization = None
    _json = None
    _json_dict = None
    _error = None
    _adminLayerInfo = None
    _syncCanReturnChanges = None
    _dateFieldsTimeReference = None
    _enableZDefaults = None
    _ogcGeometryType = None
    _exceedsLimitFactor = None
    _useStandardizedQueries = None
    _definitionQuery = None
    _zDefault = None
    #----------------------------------------------------------------------
    def __init__(self, url,
                 securityHandler,
                 initialize=False,
                 proxy_url=None,
                 proxy_port=None):
        """Constructor"""
        self._url = url
        self._proxy_url = proxy_url
        self._proxy_port = proxy_port

        if isinstance(securityHandler, BaseSecurityHandler):
            if hasattr(securityHandler, 'is_portal'):
                if securityHandler.is_portal:
                    if hasattr(securityHandler, 'portalServerHandler'):
                        self._securityHandler = securityHandler.portalServerHandler(serverUrl=url)
                    else:
                        self._securityHandler = securityHandler
                else:
                    self._securityHandler = securityHandler

            else:
                self._securityHandler = securityHandler

        else:
            raise AttributeError("Admin only supports AGOL, ArcGIS, Portal, NTLM, LDAP, PKI and OAuth security handlers")

        if initialize:
            self.__init()
    #----------------------------------------------------------------------
    def __str__(self):
        """returns the object as a string"""
        if self._json is None:
            self.__init()
        return self._json
    #----------------------------------------------------------------------
    def __iter__(self):
        """returns the key/value pair of the raw JSON"""
        if self._json_dict is None:
            self.__init()
        for k,v in self._json_dict.iteritems():
            yield [k,v]
    #----------------------------------------------------------------------
    @property
    def securityHandler(self):
        """ returns the current security handler """
        return self._securityHandler
    #----------------------------------------------------------------------
    @securityHandler.setter
    def securityHandler(self, value):
        """ sets the security handler """
        if isinstance(value,( security.AGOLTokenSecurityHandler,security.PortalTokenSecurityHandler,security.ArcGISTokenSecurityHandler)):
            self._securityHandler = value

        else:
            raise AttributeError("This object only accepts security.AGOLTokenSecurityHandler")
    #----------------------------------------------------------------------
    def __init(self):
        """ initializes the service """
        params = {
            "f" : "json",
        }
        json_dict = self._do_get(self._url, params,
                                 securityHandler=self._securityHandler,
                                 proxy_port=self._proxy_port,
                                 proxy_url=self._proxy_url)
        self._json = json.dumps(json_dict)
        self._json_dict = json_dict
        self.loadAttributes(json_dict=json_dict)
    #----------------------------------------------------------------------
    def loadAttributes(self,json_dict):
        attributes = [attr for attr in dir(self)
                     if not attr.startswith('__') and \
                     not attr.startswith('_')]
        for k,v in json_dict.iteritems():
            if k in attributes:
                setattr(self, "_"+ k, json_dict[k])
            else:
                print k, " - attribute not implemented AdminFeatureServiceLayer."
            del k, v
    #----------------------------------------------------------------------
    def refresh(self):
        """ refreshes a service """
        params = {"f": "json"}
        uURL = self._url + "/refresh"
        res = self._do_get(url=uURL, param_dict=params,
                            securityHandler=self._securityHandler,
                            proxy_port=self._proxy_port,
                            proxy_url=self._proxy_url)
        self.__init()
        return res
    #----------------------------------------------------------------------
    @property
    def supportsValidateSql(self):
        """gets the support validate sql value"""
        if self._supportsValidateSql is None:
            self.__init()
        return self._supportsValidateSql
    #----------------------------------------------------------------------
    @property
    def error(self):
        """returns error message if error occurs"""
        if self._error is None:
            self.__init()
        return self._error
    #----------------------------------------------------------------------
    @property
    def supportsCoordinatesQuantization(self):
        """gets the supportsCoordinatesQuantization value"""
        if self._supportsCoordinatesQuantization is None:
            self.__init()
        return self._supportsCoordinatesQuantization

    #----------------------------------------------------------------------
    @property
    def editFieldsInfo(self):
        """ returns the edit fields information """
        if self._editFieldsInfo is None:
            self.__init()
        return self._editFieldsInfo
    #----------------------------------------------------------------------
    @property
    def advancedQueryCapabilities(self):
        """ returns the advanced query capabilities """
        if self._advancedQueryCapabilities is None:
            self.__init()
        return self._advancedQueryCapabilities
    #----------------------------------------------------------------------
    @property
    def supportsRollbackOnFailureParameter(self):
        """ returns if rollback on failure supported """
        if self._supportsRollbackOnFailureParameter is None:
            self.__init()
        return self._supportsRollbackOnFailureParameter
    #----------------------------------------------------------------------
    @property
    def hasStaticData(self):
        """boolean T/F if static data is present """
        if self._hasStaticData is None:
            self.__init()
        return self._hasStaticData
    #----------------------------------------------------------------------
    @property
    def indexes(self):
        """gets the indexes"""
        if self._indexes is None:
            self.__init()
        return self._indexes
    #----------------------------------------------------------------------
    @property
    def templates(self):
        """ gets the template """
        if self._templates is None:
            self.__init()
        return self._templates
    #----------------------------------------------------------------------
    @property
    def allowGeometryUpdates(self):
        """ returns boolean if geometry updates are allowed """
        if self._allowGeometryUpdates is None:
            self.__init()
        return self._allowGeometryUpdates
    #----------------------------------------------------------------------
    @property
    def globalIdField(self):
        """ returns the global id field """
        if self._globalIdField is None:
            self.__init()
        return self._globalIdField
    #----------------------------------------------------------------------
    @property
    def objectIdField(self):
        if self._objectIdField is None:
            self.__init()
        return self._objectIdField
    #----------------------------------------------------------------------
    @property
    def currentVersion(self):
        """ returns the current version """
        if self._currentVersion is None:
            self.__init()
        return self._currentVersion
    #----------------------------------------------------------------------
    @property
    def id(self):
        """ returns the id """
        if self._id is None:
            self.__init()
        return self._id
    #----------------------------------------------------------------------
    @property
    def name(self):
        """ returns the name """
        if self._name is None:
            self.__init()
        return self._name
    #----------------------------------------------------------------------
    @property
    def type(self):
        """ returns the type """
        if self._type is None:
            self.__init()
        return self._type
    #----------------------------------------------------------------------
    @property
    def description(self):
        """ returns the layer's description """
        if self._description is None:
            self.__init()
        return self._description
    #----------------------------------------------------------------------
    @property
    def definitionExpression(self):
        """returns the definitionExpression"""
        if self._definitionExpression is None:
            self.__init()
        return self._definitionExpression
    #----------------------------------------------------------------------
    @property
    def geometryType(self):
        """returns the geometry type"""
        if self._geometryType is None:
            self.__init()
        return self._geometryType
    #----------------------------------------------------------------------
    @property
    def hasZ(self):
        """ returns if it has a Z value or not """
        if self._hasZ is None:
            self.__init()
        return self._hasZ
    #----------------------------------------------------------------------
    @property
    def hasM(self):
        """ returns if it has a m value or not """
        if self._hasM is None:
            self.__init()
        return self._hasM
    #----------------------------------------------------------------------
    @property
    def copyrightText(self):
        """ returns the copyright text """
        if self._copyrightText is None:
            self.__init()
        return self._copyrightText
    #----------------------------------------------------------------------
    @property
    def parentLayer(self):
        """ returns information about the parent """
        if self._parentLayer is None:
            self.__init()
        return self._parentLayer
    #----------------------------------------------------------------------
    @property
    def subLayers(self):
        """ returns sublayers for layer """
        if self._subLayers is None:
            self.__init()
        return self._subLayers
    #----------------------------------------------------------------------
    @property
    def minScale(self):
        """ minimum scale layer will show """
        if self._minScale is None:
            self.__init()
        return self._minScale
    #----------------------------------------------------------------------
    @property
    def maxScale(self):
        """ sets the max scale """
        if self._maxScale is None:
            self.__init()
        return self._maxScale
    #----------------------------------------------------------------------
    @property
    def effectiveMinScale(self):
        if self._effectiveMinScale is None:
            self.__init()
        return self._effectiveMinScale
    #----------------------------------------------------------------------
    @property
    def effectiveMaxScale(self):
        if self._effectiveMaxScale is None:
            self.__init()
        return self._effectiveMaxScale
    #----------------------------------------------------------------------
    @property
    def defaultVisibility(self):
        if self._defaultVisibility is None:
            self.__init()
        return self._defaultVisibility
    #----------------------------------------------------------------------
    @property
    def extent(self):
        if self._extent is None:
            self.__init()
        return self._extent
    #----------------------------------------------------------------------
    @property
    def timeInfo(self):
        if self._timeInfo is None:
            self.__init()
        return self._timeInfo
    #----------------------------------------------------------------------
    @property
    def drawingInfo(self):
        if self._drawingInfo is None:
            self.__init()
        return self._drawingInfo
    #----------------------------------------------------------------------
    @property
    def hasAttachments(self):
        if self._hasAttachments is None:
            self.__init()
        return self._hasAttachments
    #----------------------------------------------------------------------
    @property
    def htmlPopupType(self):
        if self._htmlPopupType is None:
            self.__init()
        return self._htmlPopupType
    #----------------------------------------------------------------------
    @property
    def displayField(self):
        if self._displayField is None:
            self.__init()
        return self._displayField
    #----------------------------------------------------------------------
    @property
    def typeIdField(self):
        if self._typeIdField is None:
            self.__init()
        return self._typeIdField
    #----------------------------------------------------------------------
    @property
    def fields(self):
        if self._fields is None:
            self.__init()
        return self._fields
    #----------------------------------------------------------------------
    @property
    def types(self):
        if self._types is None:
            self.__init()
        return self._types
    #----------------------------------------------------------------------
    @property
    def relationships(self):
        if self._relationships is None:
            self.__init()
        return self._relationships
    #----------------------------------------------------------------------
    @property
    def maxRecordCount(self):
        if self._maxRecordCount is None:
            self.__init()
            if self._maxRecordCount is None:
                self._maxRecordCount = 1000
        return self._maxRecordCount
    #----------------------------------------------------------------------
    @property
    def canModifyLayer(self):
        if self._canModifyLayer is None:
            self.__init()
        return self._canModifyLayer
    #----------------------------------------------------------------------
    @property
    def supportsStatistics(self):
        if self._supportsStatistics is None:
            self.__init()
        return self._supportsStatistics
    #----------------------------------------------------------------------
    @property
    def supportsAdvancedQueries(self):
        if self._supportsAdvancedQueries is None:
            self.__init()
        return self._supportsAdvancedQueries
    #----------------------------------------------------------------------
    @property
    def hasLabels(self):
        if self._hasLabels is None:
            self.__init()
        return self._hasLabels
    #----------------------------------------------------------------------
    @property
    def canScaleSymbols(self):
        if self._canScaleSymbols is None:
            self.__init()
        return self._canScaleSymbols
    #----------------------------------------------------------------------
    @property
    def capabilities(self):
        if self._capabilities is None:
            self.__init()
        return self._capabilities
    #----------------------------------------------------------------------
    @property
    def supportedQueryFormats(self):
        if self._supportedQueryFormats is None:
            self.__init()
        return self._supportedQueryFormats
    #----------------------------------------------------------------------
    @property
    def isDataVersioned(self):
        if self._isDataVersioned is None:
            self.__init()
        return self._isDataVersioned
    #----------------------------------------------------------------------
    @property
    def supportsCalculate(self):
        """gets the supportsCalculate value"""
        if self._supportsCalculate is None:
            self.__init()
        return self._supportsCalculate
    #----------------------------------------------------------------------
    @property
    def editingInfo(self):
        """gets the editingInfo value"""
        if self._editingInfo is None:
            self.__init()
        return self._editingInfo
    #----------------------------------------------------------------------
    @property
    def supportsAttachmentsByUploadId(self):
        """gets the supportsAttachmentsByUploadId value"""
        if self._supportsAttachmentsByUploadId is None:
            self.__init()
        return self._supportsAttachmentsByUploadId
    #----------------------------------------------------------------------
    @property
    def ownershipBasedAccessControlForFeatures(self):
        if self._ownershipBasedAccessControlForFeatures is None:
            self.__init()
        return self._ownershipBasedAccessControlForFeatures
    #----------------------------------------------------------------------
    @property
    def useStandardizedQueries(self):
        if self._useStandardizedQueries is None:
            self.__init()
        return self._useStandardizedQueries
    #----------------------------------------------------------------------
    @property
    def adminLayerInfo(self):
        if self._adminLayerInfo is None:
            self.__init()
        return self._adminLayerInfo
    #----------------------------------------------------------------------
    @property
    def syncCanReturnChanges(self):
        if self._syncCanReturnChanges is None:
            self.__init()
        return self._syncCanReturnChanges
    #----------------------------------------------------------------------
    @property
    def dateFieldsTimeReference(self):
        if self._dateFieldsTimeReference is None:
            self.__init()
        return self._dateFieldsTimeReference
    #----------------------------------------------------------------------
    @property
    def enableZDefaults(self):
        if self._enableZDefaults is None:
            self.__init()
        return self._enableZDefaults
    #----------------------------------------------------------------------
    @property
    def ogcGeometryType(self):
        if self._ogcGeometryType is None:
            self.__init()
        return self._ogcGeometryType
    #----------------------------------------------------------------------
    @property
    def exceedsLimitFactor(self):
        if self._exceedsLimitFactor is None:
            self.__init()
        return self._exceedsLimitFactor
    #----------------------------------------------------------------------
    @property
    def definitionQuery(self):
        if self._definitionQuery is None:
            self.__init()
        return self._definitionQuery
    #----------------------------------------------------------------------
    @property
    def zDefault(self):
        if self.zDefault is None:
            self.__init()
        return self.zDefault

    #----------------------------------------------------------------------
    def addToDefinition(self, json_dict):
        """
           The addToDefinition operation supports adding a definition
           property to a hosted feature service. The result of this
           operation is a response indicating success or failure with error
           code and description.

           This function will allow users to change add additional values
           to an already published service.

           Input:
              json_dict - part to add to host service.  The part format can
                          be derived from the asDictionary property.  For
                          layer level modifications, run updates on each
                          individual feature service layer object.
           Output:
              JSON message as dictionary
        """
        params = {
            "f" : "json",
            "addToDefinition" : json.dumps(json_dict),
            #"async" : False
        }
        uURL = self._url + "/addToDefinition"
        res = self._do_post(url=uURL, param_dict=params,
                            securityHandler=self._securityHandler,
                            proxy_port=self._proxy_port,
                             proxy_url=self._proxy_url)
        self.refresh()
        return res
    #----------------------------------------------------------------------
    def updateDefinition(self, json_dict):
        """
           The updateDefinition operation supports updating a definition
           property in a hosted feature service. The result of this
           operation is a response indicating success or failure with error
           code and description.

           Input:
              json_dict - part to add to host service.  The part format can
                          be derived from the asDictionary property.  For
                          layer level modifications, run updates on each
                          individual feature service layer object.
           Output:
              JSON Message as dictionary
        """
        params = {
            "f" : "json",
            "updateDefinition" : json.dumps(json_dict),
            "async" : False
        }

        uURL = self._url + "/updateDefinition"
        res = self._do_post(url=uURL, param_dict=params,
                             securityHandler=self._securityHandler,
                             proxy_port=self._proxy_port,
                             proxy_url=self._proxy_url)
        self.refresh()
        return res
    #----------------------------------------------------------------------
    def deleteFromDefinition(self, json_dict):
        """
           The deleteFromDefinition operation supports deleting a
           definition property from a hosted feature service. The result of
           this operation is a response indicating success or failure with
           error code and description.
           See: http://resources.arcgis.com/en/help/arcgis-rest-api/index.html#/Delete_From_Definition_Feature_Service/02r30000021w000000/
           for additional information on this function.
           Input:
              json_dict - part to add to host service.  The part format can
                          be derived from the asDictionary property.  For
                          layer level modifications, run updates on each
                          individual feature service layer object.  Only
                          include the items you want to remove from the
                          FeatureService or layer.

           Output:
              JSON Message as dictionary

        """
        params = {
            "f" : "json",
            "deleteFromDefinition" : json.dumps(json_dict)
        }
        uURL = self._url + "/deleteFromDefinition"
        res = self._do_post(url=uURL, param_dict=params,
                             securityHandler=self._securityHandler,
                             proxy_port=self._proxy_port,
                             proxy_url=self._proxy_url)
        self.refresh()
        return res
