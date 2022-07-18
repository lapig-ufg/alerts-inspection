import datetime
import time
from os import path, remove
from glob import glob
from PyQt5.QtWidgets import QPushButton
from qgis.PyQt.QtCore import QVariant
from PyQt5 import QtCore
from qgis.PyQt.QtWidgets import QMessageBox
from qgis.PyQt.QtGui import QColor, QCursor
from qgis.core import Qgis, QgsWkbTypes, QgsProject, QgsVectorLayer, QgsSymbol, QgsRuleBasedRenderer, QgsFillSymbol, QgsRectangle, QgsField, QgsFeatureRequest
from .tools import ToolPointer, ClipboardPointer
from .export import Writer
import unicodedata
class InspectionController:
    """QGIS Plugin Implementation."""

    def __init__(self, parent):
        self.parent = parent
        self.selectedClassObject = None
        self.layer = None
        self.inspectionStartDatetime = None
        self.parent.dockwidget.btnNext.clicked.connect(self.nextTile)
        self.tile = None
        self.classes = [    
            {
                "class": "DEFORESTED ",
                "value": 1,
                "color": "#009933",
                "type": "point",
                "selected": True,
                "rgb": "0,153,51,255"
            },
            {
                "class": "NOT DEFORESTED",
                "value": 0,
                "color": "#ff9900",
                "type": "point",
                "selected": False,
                "rgb": "255,153,0,255"
            }
        ]
        
    def dialog(self, title, text, info, type):
        obType = None

        if(type == 'Critical'):
            obType = QMessageBox.Critical
        elif(type == 'Information'):
            obType = QMessageBox.Information
        elif(type == 'Question'):
            obType = QMessageBox.Question
        elif(type == 'Warning'):
            obType = QMessageBox.Warning
            
        msg = QMessageBox()
        msg.setIcon(obType)
        msg.setText(text)

        if(info):
            msg.setInformativeText(info)

        msg.setWindowTitle(title)
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        return msg.exec_()

    def getPoint(self):
        canvas = self.parent.iface.mapCanvas()
        tool = ClipboardPointer(self.parent.iface, self)
        canvas.setMapTool(tool)
       
    def normalize(self, text):
        text = (
            unicodedata.normalize('NFD', text)
            .encode('ascii', 'ignore')
            .decode('utf-8')
        )
        return str(text).lower().replace(" ", "_")

    def setFeatureColor(self):
        # symbol = QgsFillSymbol.createSimple({'color':'0,0,0,0','color_border':'#404040','width_border':'0.1'})
        symbol = QgsSymbol.defaultSymbol(self.layer.geometryType())
        renderer = QgsRuleBasedRenderer(symbol)
        
        rules = []

        for type in self.classes:
            rgb = type['rgb'].split(",")
            rules.append([type['class'], f""""deforested" = {type['value']}""", QColor(int(rgb[0]), int(rgb[1]), int(rgb[2]), int(rgb[3]))])

        def rule_based_symbology(layer, renderer, label, expression, color):
            root_rule = renderer.rootRule()
            rule = root_rule.children()[0].clone()
            rule.setLabel(label)
            rule.setFilterExpression(expression)
            rule.symbol().setColor(QColor(color))
            root_rule.appendChild(rule)
            layer.setRenderer(renderer)
            layer.triggerRepaint()

        for rule in rules:
            rule_based_symbology(self.layer, renderer, rule[0], rule[1], rule[2])

        renderer.rootRule().removeChildAt(0)
        self.parent.iface.layerTreeView().refreshLayerSymbology(self.layer.id())

    def getFeature(self, featureId):
        feature = None
        allFeatures = self.layer.getFeatures();
        for feat in allFeatures:
            if(feat.id() == featureId): 
                feature = feat
        return feature

    def removePoints(self, selectedFeatures):
        
        self.parent.polygonsLayer.removeSelection()

        request = QgsFeatureRequest()
        request.setFilterFids(selectedFeatures)
        allFeatures = list(self.layer.getFeatures(request));
    
        self.layer.startEditing()
      
        for feature in allFeatures:

            self.layer.deleteFeature(feature.id())
         
        self.layer.commitChanges()
        canvas = self.parent.iface.mapCanvas()
        tool = ToolPointer(self.parent.iface, self.layer, self)
        canvas.setMapTool(tool)

    def addClassToFeature(self, selectedFeatures):
        request = QgsFeatureRequest()
        request.setFilterFids(selectedFeatures)
        rgb = self.selectedClassObject['rgb'].split(",")
        self.parent.iface.mapCanvas().setSelectionColor( QColor(int(rgb[0]), int(rgb[1]), int(rgb[2]), 135) )

                  
    def createPointsLayer(self, tile):
        if self.layer: 
            QgsProject().instance().removeMapLayer(self.layer)

        self.layer = None
        self.tile = None
        zoomRectangle = None
        tilesFeatures = None
        geom = None
        request = None
        self.inspectionStartDatetime = datetime.datetime.now()
        name = self.parent.getConfig('interpreterName')

        self.tile = tile
        if name is "":
            name = self.parent.dockwidget.interpreterName.text()
        
        self.interpreterName = self.normalize(name)

        filename =  self.parent.getConfig('deforestationPointsPath')

        if not path.exists(filename):
           
            uri = "point?crs=epsg:5880"
            self.layer = QgsVectorLayer(uri, f"deforestation_points_{self.interpreterName}", "memory")
        else:
            self.layer = QgsVectorLayer(filename, f"deforestation_points_{self.interpreterName}", 'ogr')

        dataProvider = self.layer.dataProvider()
        # Enter editing mode
        self.layer.startEditing()

        # add fields
        dataProvider.addAttributes( [ QgsField("deforested", QVariant.Int), QgsField("tile_id", QVariant.Int) ] )

        self.layer.commitChanges()        
        request = QgsFeatureRequest().setFilterFids([tile[0]])
        tilesFeatures = list(self.parent.tilesLayer.getFeatures(request))
        geom = tilesFeatures[0].geometry()
        zoomRectangle = QgsRectangle(geom.boundingBox())

        self.layer.selectionChanged.connect(self.removePoints)

        QgsProject().instance().addMapLayer(self.layer)
        self.parent.canvas.setExtent(zoomRectangle)

        self.setFeatureColor()
    
    def setDefaultClass(self, layer):
        layer.startEditing()
        allFeatures = layer.getFeatures();
        deforested_idx = layer.fields().indexOf('deforested')
        for feature in allFeatures:
            layer.changeAttributeValue(feature.id(), deforested_idx, 0)
        layer.commitChanges()

    def clearButtons(self, layout):
        for i in reversed(range(layout.count())): 
            layout.itemAt(i).widget().setParent(None)
   
    def removeSelection(self):
        self.parent.selectedClass = None
        self.parent.iface.actionSelectFreehand().trigger() 
    

    def onClickClass(self, item):
        """Write config in config file"""
        self.parent.dockwidget.selectedClass.setText(f"Selected class:  {item['class'].upper()}")
        self.parent.dockwidget.selectedClass.setStyleSheet(f"background-color: {item['color']}; border-radius :5px; padding :5px")
        self.parent.selectedClass = item['value']
        self.selectedClassObject = item
        canvas = self.parent.iface.mapCanvas()
        tool = ToolPointer(self.parent.iface, self.layer, self)
        canvas.setMapTool(tool)

    def initInspectionTile(self):
        """Load all class of type inspection"""
        self.clearButtons(self.parent.dockwidget.layoutClasses)
        self.parent.dockwidget.btnNext.setEnabled(True)
         
        for type in self.classes:
            if(type['selected']):
                self.onClickClass(type)

            button = QPushButton(type['class'].upper(), checkable=True)
            button.setStyleSheet(f"background-color: {type['color']}")
            button.setCursor(QCursor(QtCore.Qt.PointingHandCursor))
            button.clicked.connect(lambda checked, value = type : self.onClickClass(value))
            self.parent.dockwidget.layoutClasses.addWidget(button)
            
                
        self.parent.dockwidget.btnClearSelection.setVisible(True)

    def clearContainerClasses(self, finished=False):
        if(self.parent.dockwidget):
            self.parent.dockwidget.selectedClass.setVisible(False)
            self.parent.dockwidget.btnClearSelection.setVisible(False)
            self.clearButtons(self.parent.dockwidget.layoutClasses)

            if(finished):
                self.parent.dockwidget.btnNext.setVisible(False)
            else:
                self.parent.dockwidget.labelClass.setVisible(False)

            for i in reversed(range(self.parent.dockwidget.layoutClasses.count())): 
                self.parent.dockwidget.layoutClasses.itemAt(i).widget().setParent(None)

    def layerIsEmpty(self, layer):
        request = QgsFeatureRequest().setFilterExpression(' "class" is NULL AND "image_date" is NULL ')
        resultFeatures = layer.getFeatures(request);

        if(layer.featureCount() == len(list(resultFeatures))):
            return True
        else:
            return False

    
    def sendInspections(self):
        workingDirectory = self.parent.getConfig('workingDirectory')
        # layer.saveSldStyle(path.join(workingDirectory, f"{self.parent.typeInspection['_id']}.sld"))
        # types = (path.join(workingDirectory, f"*_{self.parent.typeInspection['_id']}.gpkg"), f"*_{self.parent.typeInspection['_id']}.sld")
        files = glob(path.join(workingDirectory, f"*_{self.parent.typeInspection['_id']}.gpkg"))
           

    def nextTile(self):
        layer = None
        index = self.parent.currentTileIndex + 1
        tilesLength = len(self.parent.tiles)

        layer = self.layer
              
        if(layer):
            if( index <= tilesLength):
                endTime = datetime.datetime.now()
                name = self.parent.getConfig('interpreterName')

                if name is "":
                    name = self.parent.dockwidget.interpreterName.text()
                filename =  self.parent.getConfig('deforestationPointsPath');
                if not path.exists(filename):
                    Writer(self, layer).gpkg()

                if(index < tilesLength):
                    self.parent.currentTileIndex = index
                    self.parent.setConfig(key='currentTileIndex', value= index)
                    # QgsProject.instance().removeMapLayer(layer.id())
                    self.parent.configTiles()

            # self.clearContainerClasses()

            if(index == tilesLength):
                self.parent.iface.messageBar().pushMessage("", "Inspection FINISHED!", level=Qgis.Info, duration=15)

                if(self.parent.dockwidget):
                    self.parent.dockwidget.tileInfo.setText(f"INSPECTION FINISHED!")
                    self.parent.dockwidget.labelClass.setVisible(False)
                    self.clearContainerClasses(finished=True)

                self.parent.currentTileIndex = 0
                time.sleep(2)
                remove(self.parent.workDir + 'config.json')
                self.parent.onClosePlugin();
            
                
                # button = QPushButton("Send Inpections to Drive", checkable=True)
                # button.setCursor(QCursor(QtCore.Qt.PointingHandCursor))
                # button.clicked.connect(self.sendInspections)
                # self.parent.dockwidget.layoutClasses.addWidget(button)
        else: 
            self.parent.iface.messageBar().pushMessage("", "Something went wrong with the layer, Please close the plugin and try again", level=Qgis.Critical, duration=10)  
        
        layer = None
        
