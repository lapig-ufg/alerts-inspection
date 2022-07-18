from PyQt5.QtWidgets import (QMessageBox)
# from qgis import processing
from qgis.core import QgsProject, QgsCoordinateReferenceSystem, QgsVectorFileWriter, QgsCoordinateTransformContext, QgsFields
from os import path
class Writer:
    def __init__(self, controller, layer):
        self.layer  = layer
        self.controller = controller
        return None

    def gpkg(self):
        writer = None
        try:
            writer = QgsVectorFileWriter
            filename = path.normpath(f"{self.controller.parent.dockwidget.fieldWorkingDirectory.text()}/{self.layer.name()}.gpkg")
            coordinateTransformContext = QgsProject.instance().transformContext()
            options = QgsVectorFileWriter.SaveVectorOptions()
            options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile        
            options.fileEncoding = "UTF-8"
            options.driverName = "GPKG"
            options.layerName = self.layer.name() 
            # options.layerOptions = self.metadata
          
            writer.writeAsVectorFormatV3(
                self.layer,
                filename,
                coordinateTransformContext,
                options
            )
            # layers = [self.layer,]
            # processing.run("native:package", {'LAYERS': layers, 'OUTPUT': filename, 'OVERWRITE': True, 'SAVE_STYLES': False})
            self.controller.parent.setConfig(key='deforestationPointsPath', value=filename)
            writer = None
            return True
        except Exception as e:
            QMessageBox.warning(self.controller.parent.dockwidget, "BulkVectorExport",f"Failed to export: {self.layer.name()}. Msg: {e.message}")
            writer = None
            return False

    def createGpkgLayer(gpkg_path: str, layerNname: str, geometry: int, crs: str, schema: QgsFields, append: bool = False):
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = "GPKG"
        options.layerName = layerNname
        if append:
            options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer

        writer = QgsVectorFileWriter.create(
            gpkg_path,
            schema,
            geometry,
            QgsCoordinateReferenceSystem(crs),
            QgsCoordinateTransformContext(),
            options)
        del writer

        return True
 