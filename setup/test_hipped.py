from style import StyleStore

from parse.osm.relation.building import Building as BuildingRelation

from building.manager import BuildingParts, BuildingRelations

from manager.logging import Logger

from building2.manager import RealisticBuildingManager
from building2.renderer import BuildingRendererNew, Building

from item.footprint import Footprint

# item renderers
from item_renderer.test import\
    GeometryRenderer, GeometryRendererRoofWithSides, GeometryRendererFacade, GeometryRendererRoofFlat

from action.terrain import Terrain
from action.offset import Offset
from action.volume import Volume


import bpy

#
# augment BuildingRendererNew.render(..)
#
import math
from parse.osm.way import Way

_render = BuildingRendererNew.render
def render(self, buildingP, data):
    projection = data.projection
    element = buildingP.outline
    if isinstance(element, Way):
        node = data.nodes[element.nodes[0]]
    else:
        # the case of OSM relation
        node = data.nodes[
            next( (element.ls[0] if isinstance(element.ls, list) else element.ls).nodeIds(data) )
        ]
    
    projection.lat = node.lat
    projection.lon = node.lon
    projection.latInRadians = math.radians(projection.lat)
    _render(self, buildingP, data)

BuildingRendererNew.render = render


#
# augment App.clean(..)
#
from app import App

_clean = App.clean
def clean(self):
    self.log.close()
    _clean(self)

App.clean = clean


#
# redefine Node.getData(..) (never cache the projected coordinates)
#
from parse.osm.node import Node

def getData(self, osm):
    """
    Get projected coordinates
    """
    return osm.projection.fromGeographic(self.lat, self.lon)
Node.getData = getData


def setup(app, data):
    # prevent extent calculation
    bpy.context.scene["lat"] = 0.
    bpy.context.scene["lon"] = 0.
    # create a log
    app.log = open("D://tmp/log.txt", 'w')
    
    styleStore = StyleStore(app, styles=None)

    # comment the next line if logging isn't needed
    Logger(app, data)
    
    if app.buildings:
        buildingParts = BuildingParts()
        buildingRelations = BuildingRelations()
        buildings = RealisticBuildingManager(data, buildingParts)
        
        # Important: <buildingRelation> beform <building>,
        # since there may be a tag building=* in an OSM relation of the type 'building'
        data.addCondition(
            lambda tags, e: isinstance(e, BuildingRelation),
            None,
            buildingRelations
        )
        data.addCondition(
            lambda tags, e: "building" in tags or "building:part" in tags,
            "buildings",
            buildings
        )
        
        # deal with item renderers
        itemRenderers = dict(
            Facade = GeometryRendererFacade(),
            Div = GeometryRenderer(),
            Level = GeometryRenderer(),
            CurtainWall = GeometryRenderer(),
            Bottom = GeometryRenderer(),
            Door = GeometryRenderer(),
            RoofFlat = GeometryRendererRoofFlat(),
            RoofFlatMulti = GeometryRenderer(),
            RoofProfile = GeometryRenderer(),
            RoofDome = GeometryRenderer(),
            RoofHalfDome = GeometryRenderer(),
            RoofOnion = GeometryRenderer(),
            RoofPyramidal = GeometryRenderer(),
            RoofHipped = GeometryRendererRoofWithSides()
        )
        
        br = BuildingRendererNew(app, styleStore, itemRenderers, getStyle=getStyle)
        
        Building.actions = []
        # <app.terrain> isn't yet set at this pooint, so we use the string <app.terrainObject> instead
        if app.terrainObject:
            Building.actions.append( Terrain(app, data, br.itemStore, br.itemFactory) )
        if not app.singleObject:
            Building.actions.append( Offset(app, data, br.itemStore, br.itemFactory) )
        
        volumeAction = Volume(app, data, br.itemStore, br.itemFactory, itemRenderers)
        Footprint.actions = (volumeAction,)
        # <br> stands for "building renderer"
        buildings.setRenderer(br)
        app.managers.append(buildings)


def getStyle(building, app):
    #return "mid rise apartments zaandam"
    #return "high rise mirrored glass"
    buildingTag = building["building"]
    
    if buildingTag in ("commercial", "office"):
        return "high rise"
    
    if buildingTag in ("house", "detached"):
        return "single family house"
    
    if buildingTag in ("residential", "apartments", "house", "detached"):
        return "residential"
    
    if building["amenity"] == "place_of_worship":
        return "place of worship"
    
    if building["man_made"] or building["barrier"] or buildingTag=="wall":
        return "man made"
    
    buildingArea = building.area()
    
    if buildingArea < 20.:
        return "small structure"
    elif buildingArea < 200.:
        return "single family house"
    
    return "high rise"