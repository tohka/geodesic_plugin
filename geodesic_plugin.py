from qgis.core import QgsApplication
from .geodesic_plugin_provider import GeodesicPluginProvider

class GeodesicPlugin:

    def __init__(self):
        self.provider = None

    def initProcessing(self):
        self.provider = GeodesicPluginProvider()
        QgsApplication.processingRegistry().addProvider(self.provider)

    def initGui(self):
        self.initProcessing()

    def unload(self):
        QgsApplication.processingRegistry().removeProvider(self.provider)

