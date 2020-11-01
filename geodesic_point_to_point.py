# -*- coding: utf-8 -*-

"""
***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

import math
from qgis.PyQt.QtCore import (QCoreApplication, QVariant)
from qgis.core import (QgsPointXY, QgsGeometry, QgsFeature,
        QgsField, QgsFields, QgsWkbTypes, QgsProject, QgsUnitTypes,
        QgsCoordinateReferenceSystem, QgsCoordinateTransform)
from qgis.core import (QgsProcessing,
                       QgsFeatureSink,
                       QgsProcessingException,
                       QgsProcessingAlgorithm,
                       QgsProcessingParameterDefinition,
                       QgsProcessingParameterPoint,
                       QgsProcessingParameterDistance,
                       QgsProcessingParameterFeatureSink)
from qgis import processing


class GeodesicPointToPointAlgorithm(QgsProcessingAlgorithm):
    """
    Algorithm to generate a geodesic line (point to point).
    """

    # 各パラメータの ID
    POINT1 = 'POINT1'
    POINT2 = 'POINT2'
    SEGMENT_DIST = 'SEGMENT_DIST'
    OUTPUT = 'OUTPUT'

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return GeodesicPointToPointAlgorithm()

    def name(self):
        # アルゴリズムの ID
        return 'geodesic_point_to_point'

    def displayName(self):
        # アルゴリズムが表示されるときの名称
        return self.tr('Geodesic (point to point)')

    """
    def group(self):
        # アルゴリズムが属するグループ
        return self.tr('Geodesic')

    def groupId(self):
        # グループ ID
        return 'geodesic'
    """

    def shortHelpString(self):
        # アルゴリズムのヘルプとして表示される文章
        return self.tr("Generates a geodesic (point to point)")

    def initAlgorithm(self, config=None):
        # パラメータの定義を行う

        # QgsProcessingParameterFooBar クラスがたくさん用意されている
        # パラメータオブジェクトを self.addParameter(param) すると
        # 自動的にウィジェットが設定される

        self.addParameter(
            QgsProcessingParameterPoint(
                self.POINT1,
                self.tr('Start point')
            )
        )

        self.addParameter(
            QgsProcessingParameterPoint(
                self.POINT2,
                self.tr('End point')
            )
        )

        segdist_param = QgsProcessingParameterDistance(
            self.SEGMENT_DIST,
            self.tr('Segment Distance'),
            defaultValue=100,
            # パラメータ定義時の minValue は単位に関わらず適用されるため
            # 最低値のチェック及び適用はあとで行う
            # とはいえウィジットレベルで最低0以上の制約は行う
            minValue=0
        )
        segdist_param.setDefaultUnit(QgsUnitTypes.DistanceKilometers)
        # 高度なパラメータフラグ
        segdist_param.setFlags(QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(segdist_param)

        # 結果の出力
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                self.tr('Output layer')
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        # 実行される処理を記述する

        # self.parameterAsFoo でパラメータを参照できる
        # 詳しくは QgsProcessingAlgorithm クラスのドキュメント参照

        crs4326 = QgsCoordinateReferenceSystem('EPSG:4326')

        # パラメータの値を参照する
        point1 = self.parameterAsPoint(
            parameters,
            self.POINT1,
            context,
            crs4326
        )
        if point1 is None:
            raise QgsProcessingException(
                'Error: failed to get coordnates of POINT1')
        # 実行時のログ欄に出力
        feedback.pushInfo('point1 ({}, {})'.format(point1.x(), point1.y()))

        point2 = self.parameterAsPoint(
            parameters,
            self.POINT2,
            context,
            crs4326
        )
        if point2 is None:
            raise QgsProcessingException(
                'Error: failed to get coordnates of POINT2')
        feedback.pushInfo('point2 ({}, {})'.format(point2.x(), point2.y()))

        # QgsProcessingParameterDistance の場合は、デフォルトの単位に
        # 変換された数値が得られる？
        segment_dist = self.parameterAsDouble(
            parameters,
            self.SEGMENT_DIST,
            context
        )
        # メートルになおす
        # addParameter 時の minValue は単位に関わらず適用されるので
        # 最低値等をここで設定する
        segment_dist = max((10, segment_dist)) * 1000.0
        feedback.pushInfo('segment dist: {}'.format(segment_dist))

        # 出力レイヤの属性の定義を行う
        fields = QgsFields()
        fields.append(QgsField('lat_1', QVariant.Double))
        fields.append(QgsField('lng_1', QVariant.Double))
        fields.append(QgsField('lat_2', QVariant.Double))
        fields.append(QgsField('lng_2', QVariant.Double))
        fields.append(QgsField('dist', QVariant.Double))

        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            fields,
            QgsWkbTypes.LineString,
            crs4326
        )

        if sink is None:
            raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT))


        # 点1を中心とした正距方位図法の投影法を定義する
        crs_aeqd = QgsCoordinateReferenceSystem()
        crs_aeqd.createFromProj4(
            '+proj=aeqd +lat_0={} +lon_0={} +datum=WGS84'.format(
                point1.y(), point1.x()))
        if not crs_aeqd.isValid():
            raise QgsProcessingException('Invalid CRS')
        
        trans = QgsCoordinateTransform(crs4326, crs_aeqd,
            QgsProject.instance())
        if not trans.isValid():
            raise QgsProcessingException('Invalid coordinate transformer')

        # 点2を、点1中心正距方位図法への座標変換を行う
        p2_aeqd = trans.transform(point2)

        # 正距方位図法における中心点との距離は測地線長
        dist = p2_aeqd.distance(0.0, 0.0)

        # 測地線の折れ線を作るための点群
        points = [point1]

        # セグメントに分割することで曲線のような折れ線を作る
        num_segments = math.floor(dist / segment_dist) + 1
        for i in range(1, num_segments):
            # 点1中心正距方位図法における、点1-点2を結ぶ線上の点を
            # EPSG:4326 に逆変換を行う
            x = i * segment_dist / dist * p2_aeqd.x()
            y = i * segment_dist / dist * p2_aeqd.y()
            p_4326 = trans.transform(QgsPointXY(x, y),
                QgsCoordinateTransform.ReverseTransform)
            points.append(p_4326)
        points.append(point2)

        # 折れ線の測地線のジオメトリを作る
        geom = QgsGeometry().fromPolylineXY(points)

        # 折れ線の測地線のジオメトリを持つ地物を作る
        feat = QgsFeature(fields)
        feat.setGeometry(geom)
        feat.setAttribute('lat_1', point1.y())
        feat.setAttribute('lng_1', point1.x())
        feat.setAttribute('lat_2', point2.y())
        feat.setAttribute('lng_2', point2.x())
        feat.setAttribute('dist', dist)

        # 地物を出力レイヤ (sink) に追加する
        sink.addFeature(feat, QgsFeatureSink.FastInsert)

        # アルゴリズムの結果を返す
        # このアルゴリズムでは出力 sink のひとつのみ
        return {self.OUTPUT: dest_id}



