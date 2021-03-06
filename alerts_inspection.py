# -*- coding: utf-8 -*-
"""
/***************************************************************************
 AlertsInspection
                                 A QGIS plugin
 Deforestation Alerts Inspection Plugin
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2022-07-17
        git sha              : $Format:%H$
        copyright            : (C) 2022 by Tharles de Sousa Andrade
        email                : irtharles@gmail.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from audioop import add
from os.path import expanduser
import json
import time
import os
import requests as req
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, Qt
from qgis.PyQt.QtGui import QIcon, QPixmap
from qgis.PyQt.QtWidgets import QAction, QFileDialog, QMessageBox
from qgis.core import Qgis, QgsProject, QgsRasterLayer, QgsVectorLayer, QgsFillSymbol, QgsRectangle, QgsFeatureRequest, QgsCoordinateReferenceSystem
from qgis.PyQt.QtWidgets import QAction
# Initialize Qt resources from file resources.py
from .resources import *

# Import the code for the DockWidget
from .alerts_inspection_dockwidget import AlertsInspectionDockWidget
from .resources import *
from .sources import connections
from .src.inspections import InspectionController


class AlertsInspection:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface

        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)

        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'AlertsInspection_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&Deforestation Alerts Inspection')
        # TODO: We are going to let the user set this up in a future iteration
        self.toolbar = self.iface.addToolBar(u'AlertsInspection')
        self.toolbar.setObjectName(u'AlertsInspection')

        #print "** INITIALIZING AlertsInspection"

        self.pluginIsActive = False
        self.dockwidget = None
        self.tilesLayer = None
        self.polygonsLayer = None
        self.workDir = None
        self.canvas = None
        self.root = None
        self.group = None
        self.tiles = []
        self.currentTileIndex = 0
        self.selectedClass = None
        self.inspectionController = None


    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('AlertsInspection', message)


    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action


    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/alerts_inspection/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'Alerts Inspection'),
            callback=self.run,
            parent=self.iface.mainWindow())

    #--------------------------------------------------------------------------

    def onClosePlugin(self):
        """Cleanup necessary items here when plugin dockwidget is closed"""

        #print "** CLOSING AlertsInspection"
        QgsProject.instance().clear()
        self.dockwidget.fieldFileName.setText("")
        self.dockwidget.polygonsFileName.setText("")
        self.dockwidget.interpreterName.setText("")
        self.dockwidget.fieldWorkingDirectory.setText("")
        self.iface.actionPan().trigger() 

        # disconnects
        self.dockwidget.btnFile.clicked.disconnect(self.openTilesFile)
        self.dockwidget.btnPolygons.clicked.disconnect(self.openPolygonsFile)
        self.dockwidget.btnWorkingDirectory.clicked.disconnect(self.getDirPath)
        self.dockwidget.btnClearSelection.clicked.disconnect(self.inspectionController.removeSelection)
        self.dockwidget.btnInitInspections.clicked.disconnect(self.initInspections)
        self.dockwidget.closingPlugin.disconnect(self.onClosePlugin)
        self.dockwidget = None

        # remove this statement if dockwidget is to remain
        # for reuse if plugin is reopened
        # Commented next statement since it causes QGIS crashe
        # when closing the docked window:
        # self.dockwidget = None

        self.pluginIsActive = False


    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""

        #print "** UNLOAD AlertsInspection"

        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&Deforestation Alerts Inspection'),
                action)
            self.iface.removeToolBarIcon(action)
        # remove the toolbar
        del self.toolbar

    #--------------------------------------------------------------------------
    #                               PLUGIN CODE                               #
    #--------------------------------------------------------------------------

    def openGoogleSatellite(self):
    
        url = 'https://mt1.google.com/vt/lyrs=s&x=%7Bx%7D&y=%7By%7D&z=%7Bz%7D'
        service_url = url.replace("=", "%3D").replace("&", "%26")
        qgis_tms_uri = 'type=xyz&zmin={0}&zmax={1}&url={2}'.format(0, 19, service_url)

        layer = QgsRasterLayer(qgis_tms_uri, "Google Satellite", 'wms')

        if layer.isValid():
            QgsProject.instance().addMapLayer(layer)
        else:
            print("Layer failed to load!")

    def getConfig(self, key):
        """Load config file and get value of key"""
        data = None
        with open(self.workDir + 'config.json') as json_file:
            ob = json.load(json_file)
            data = ob[key]
            json_file.close()
        return data

    def setConfig(self, key, value):
        """Write config in config file"""
        ob = None
        with open(self.workDir + 'config.json', 'r') as json_file:
            ob = json.load(json_file)
            json_file.close()

        with open(self.workDir + 'config.json', 'w') as outfile:
            ob[key] = value
            json.dump(ob, outfile)
            outfile.close()

    def configTiles(self):
    
        tile = self.tiles[self.currentTileIndex]
        self.dockwidget.tileInfo.setText(f"Tile {self.currentTileIndex + 1} of {len(self.tiles)}")
        self.dockwidget.btnClearSelection.setVisible(False)

        request = QgsFeatureRequest().setFilterFids([ tile[0] ])
        tilesFeatures = list(self.tilesLayer.getFeatures(request))
        geom = tilesFeatures[0].geometry()
        self.canvas.waitWhileRendering()
        self.canvas.setExtent(geom.boundingBox())
        self.canvas.refresh()
      
        self.inspectionController.createPointsLayer(tile)
        self.loadClasses()
   
            
    def loadTiles(self):
        """Load tiles from layer"""
        instance = QgsProject.instance()

        openLayers = [layer for layer in instance.mapLayers().values()]
        for layer in openLayers:
            if (layer.name() == 'tiles'):
                self.tiles = [f.attributes() for f in layer.getFeatures()]

    def openTilesFile(self, fromConfig=False):
        """Open Tiles file Dialog"""
        QgsProject.instance().setCrs(QgsCoordinateReferenceSystem(5880))
       
        if (fromConfig):
            layerPath = self.getConfig('filePath')
        else:
            layerPath = str(
                QFileDialog.getOpenFileName(
                    caption='Escolha o arquivo com os tiles',
                    filter='Geopackage (*gpkg)'
                )[0]
            )

        if (layerPath != ""):
            self.tilesLayer = QgsVectorLayer(layerPath, 'tiles', 'ogr')
            symbol = QgsFillSymbol.createSimple({'color': '0,0,0,0', 'color_border': 'red', 'width_border': '0.5', 'style': 'dashed'})
            self.tilesLayer.renderer().setSymbol(symbol)
            self.dockwidget.fieldFileName.setText(layerPath)
            QgsProject.instance().addMapLayer(self.tilesLayer)
            self.iface.setActiveLayer(self.tilesLayer);
            self.iface.zoomToActiveLayer();
            self.loadTiles()
            self.setConfig(key='filePath', value=layerPath)

    def openPolygonsFile(self, fromConfig=False):
        """Open Polygons file Dialog"""
       
        if (fromConfig):
            layerPath = self.getConfig('polygonsFilePath')
            self.dockwidget.tabWidget.setCurrentIndex(1)
        else:
            layerPath = str(
                QFileDialog.getOpenFileName(
                    caption='Escolha o arquivo com os polygons',
                    filter='Geopackage (*gpkg)'
                )[0]
            )
        if (layerPath != ""):
            self.polygonsLayer = QgsVectorLayer(layerPath, 'deforestation_polygons', 'ogr')
            symbol = QgsFillSymbol.createSimple({'color': '0,0,0,0', 'color_border': 'orange', 'width_border': '0.5', 'style': 'dashed_line'})
            self.polygonsLayer.renderer().setSymbol(symbol)
            self.dockwidget.polygonsFileName.setText(layerPath)
            QgsProject.instance().addMapLayer(self.polygonsLayer)
            self.setConfig(key='polygonsFilePath', value=layerPath)      
               


    def getDirPath(self, fromConfig=False):
        if (fromConfig):
            dir = self.getConfig('workingDirectory')
        else:
            dir = QFileDialog.getExistingDirectory(
                self.dockwidget,
                "Select Directory",
                expanduser("~"),
                QFileDialog.ShowDirsOnly
            )
            self.dockwidget.btnInitInspections.setVisible(True)
        self.dockwidget.fieldWorkingDirectory.setText(dir)
        self.setConfig(key='workingDirectory', value=dir)


    def loadClasses(self):
        self.dockwidget.labelClass.setVisible(True)
        self.dockwidget.selectedClass.setVisible(True)
        self.inspectionController.initInspectionTile()
         

    def initInspections(self):
        interpreterName =  self.dockwidget.interpreterName.text()
        if(interpreterName != ""): 
            self.configTiles()
            self.dockwidget.tabWidget.setTabEnabled(1, True)
            self.dockwidget.tabWidget.setCurrentIndex(1)
            self.dockwidget.btnInitInspections.setVisible(False)
            self.setTileInfoVisible(visible=True)
            self.setConfig(key='interpreterName', value=interpreterName.upper())
            self.dockwidget.interpreterName.setEnabled(False)
        else: 
            self.iface.messageBar().pushMessage("", f"The name of interpreter is required!", level=Qgis.Critical, duration=5)    


    def setTileInfoVisible(self, visible):
        self.dockwidget.tileInfo.setVisible(visible)
        self.dockwidget.btnNext.setVisible(visible)


    def run(self):
        """Run method that loads and starts the plugin"""

        if not self.pluginIsActive:
            self.pluginIsActive = True

            #print "** STARTING AlertsInspection"

            # dockwidget may not exist if:
            #    first run of plugin
            #    removed on close (see self.onClosePlugin method)
            if self.dockwidget == None:
                # Create the dockwidget (after translation) and keep reference
                self.dockwidget = AlertsInspectionDockWidget()
            
            self.dockwidget.btnClearSelection.setIcon(QIcon(os.path.dirname(__file__) + "/img/delete.png"))
            self.dockwidget.logo.setPixmap(QPixmap(os.path.dirname(__file__) + "/img/logo-plugin.png"))
            self.dockwidget.btnNext.setIcon(QIcon(os.path.dirname(__file__) + "/img/save.png"))
            self.dockwidget.btnBack.setEnabled(False)
            self.dockwidget.btnNext.setEnabled(False)
            self.iface.actionPan().trigger() 
           
            connections.xyz(self)
            self.inspectionController = InspectionController(self)
            self.workDir = str.split(__file__, "alerts_inspection.py")[0]
            self.pluginIsActive = True
            self.canvas = self.iface.mapCanvas()
            QgsProject.instance().clear()
           

            # QgsProject.instance().clear()
            # Check if config file exists, if not create
            if not os.path.exists(self.workDir + 'config.json'):
                with open(self.workDir + 'config.json', 'w') as file:
                    config = {"currentTileIndex": 0, "interpreterName": "", "filePath": "", "polygonsFilePath": "", "deforestationPointsPath": "", "workingDirectory": ""}
                    json.dump(config, file, sort_keys=True)
                    file.close()
            
            
            self.setTileInfoVisible(visible=False)
            self.dockwidget.btnInitInspections.setVisible(False)
            self.dockwidget.btnClearSelection.setVisible(False)
            self.dockwidget.tabWidget.setTabEnabled(1, False)
            self.dockwidget.labelClass.setVisible(False)
            self.dockwidget.selectedClass.setVisible(False)
            self.dockwidget.interpreterName.setEnabled(True)

            file = self.getConfig('filePath')

            if (file != ""):
                msg = QMessageBox()
                msg.setIcon(QMessageBox.Question)
                msg.setText("Do you want to start a new inspection?")
                msg.setWindowTitle("ALERTS INSPECTION")
                msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                retval = msg.exec_()
                # 65536 -> No | 16384 -> Yes
                if (retval == 16384):
                    self.dockwidget.btnFile.setEnabled(True)
                    self.dockwidget.btnPolygons.setEnabled(True)
                    self.dockwidget.btnWorkingDirectory.setEnabled(True)
                    self.dockwidget.interpreterName.setEnabled(True)
                    self.dockwidget.tabWidget.setCurrentIndex(0)
                    self.setConfig(key='polygonsFilePath', value="")
                    self.setConfig(key='currentTileIndex', value=0)
                    self.setConfig(key='filePath', value="")
                    self.setConfig(key='deforestationPointsPath', value="")
                    self.setConfig(key='workingDirectory', value="")
                    self.setConfig(key='interpreterName', value="")
                    
                else:
                    self.currentTileIndex = self.getConfig('currentTileIndex')
                    self.getDirPath(fromConfig=True)
                    self.openTilesFile(fromConfig=True)
                    self.openPolygonsFile(fromConfig=True)
                    self.dockwidget.interpreterName.setText(self.getConfig('interpreterName').upper())
                    self.dockwidget.tabWidget.setTabEnabled(1, True)
                    self.dockwidget.interpreterName.setEnabled(False)
                    self.dockwidget.btnFile.setEnabled(False)
                    self.dockwidget.btnPolygons.setEnabled(False)
                    self.dockwidget.btnWorkingDirectory.setEnabled(False)
                    self.dockwidget.btnInitInspections.setVisible(False)
                    self.setTileInfoVisible(visible=True)
                    self.configTiles()  

            self.dockwidget.btnFile.clicked.connect(self.openTilesFile)
            self.dockwidget.btnPolygons.clicked.connect(self.openPolygonsFile)
            self.dockwidget.btnWorkingDirectory.clicked.connect(self.getDirPath)
            self.dockwidget.btnClearSelection.clicked.connect(self.inspectionController.removeSelection)
            self.dockwidget.btnInitInspections.clicked.connect(self.initInspections)

            # connect to provide cleanup on closing of dockwidget
            self.dockwidget.closingPlugin.connect(self.onClosePlugin)
           
            # show the dockwidget
            # TODO: fix to allow choice of dock location
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dockwidget)
            self.dockwidget.show()
