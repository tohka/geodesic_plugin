from qgis.core import QgsProcessingProvider
from .geodesic_point_to_point import GeodesicPointToPointAlgorithm

class GeodesicPluginProvider(QgsProcessingProvider):

    def __init__(self):
        super().__init__()

    def unload(self):
        super().unload()

    def loadAlgorithms(self):
        self.addAlgorithm(GeodesicPointToPointAlgorithm())

    def id(self):
        return 'geodesic_plugin'

    def name(self):
        return self.tr('Geodesic Plugin')

    def longName(self):
        return self.name()

    def icon(self):
        return QgsProcessingProvider.icon(self)

